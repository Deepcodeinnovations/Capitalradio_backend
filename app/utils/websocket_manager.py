from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.security import decode_and_validate_token, get_user_from_token
from app.utils.returns_data import returnsdata
from app.models.StationListenersModel import StationListeners
from app.models.UserModel import User
from app.utils.constants import SUCCESS, ERROR
from typing import Dict, List, Optional, Any
from sqlalchemy import select, delete, and_
import json
import logging
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}  # user_id -> [websockets]
        self.connection_info: Dict[str, Dict[str, Any]] = {}      # connection_id -> connection_data
        self.user_info: Dict[str, Dict[str, Any]] = {}           # user_id -> user_data
        self.station_users: Dict[str, List[str]] = {}            # station_id -> [user_ids]

    async def authenticate_token(self, token: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        try:
            payload = await decode_and_validate_token(token, db)
            
            if not payload or (isinstance(payload, dict) and payload.get("status") == ERROR):
                return None
            user_data = await get_user_from_token(payload, db)
            
            if not user_data or (isinstance(user_data, dict) and user_data.get("status") == ERROR):
                return None
            
            return {
                "user_id": user_data.get("id"),
                "user_data": user_data,
                "payload": payload,
                "device_fingerprint": payload.get("device_fingerprint", ""),
                "email": user_data.get("email"),
                "current_station_id": user_data.get("current_station_id")
            }
            
        except Exception as e:
            logger.error(f"WebSocket authentication error: {str(e)}")
            return None

    async def connect_user(self, websocket: WebSocket, token: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        try:
            auth_info = await self.authenticate_token(token, db)
            if not auth_info:
                await websocket.close(code=4001, reason="Authentication failed")
                return None
            
            user_id = auth_info["user_id"]
            station_id = auth_info.get("current_station_id")
            
            await websocket.accept()
            
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            
            self.active_connections[user_id].append(websocket)
            self.user_info[user_id] = auth_info["user_data"]
            
            # Add user to station group
            if station_id:
                if station_id not in self.station_users:
                    self.station_users[station_id] = []
                if user_id not in self.station_users[station_id]:
                    self.station_users[station_id].append(user_id)
            
            connection_id = str(uuid.uuid4())
            self.connection_info[connection_id] = {
                "user_id": user_id,
                "websocket": websocket,
                "connected_at": datetime.utcnow(),
                "auth_info": auth_info,
                "last_activity": datetime.utcnow(),
                "station_id": station_id
            }
            
            logger.info(f"User {user_id} connected to station {station_id}. Total connections: {len(self.active_connections[user_id])}")
            
            # Send connection confirmation
            await self.send_to_user(
                user_id=user_id,
                data={
                    "connection_id": connection_id,
                    "user_id": user_id,
                    "station_id": station_id,
                    "connected_at": datetime.utcnow().isoformat(),
                    "total_connections": len(self.active_connections[user_id])
                },
                message_type="connection_established",
                message="Connected to event stream successfully"
            )
            
            return {
                "connection_id": connection_id,
                "user_id": user_id,
                "station_id": station_id,
                "auth_info": auth_info
            }
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            try:
                await websocket.close(code=4000, reason=f"Connection failed")
            except:
                pass
            return None

    def disconnect_user(self, websocket: WebSocket, user_id: str):
        try:
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(websocket)
                
                # Clean up empty user connections
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    if user_id in self.user_info:
                        del self.user_info[user_id]
            
            # Remove user from station groups if no more connections
            if user_id not in self.active_connections:
                for station_id, users in list(self.station_users.items()):
                    if user_id in users:
                        users.remove(user_id)
                        if not users:
                            del self.station_users[station_id]
            
            # Clean up connection info
            for conn_id, info in list(self.connection_info.items()):
                if info["websocket"] == websocket:
                    del self.connection_info[conn_id]
                    break
            
            logger.info(f"User {user_id} disconnected")
            
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")

    async def send_message_to_websocket(self, websocket: WebSocket, message: Dict[str, Any]) -> bool:
        try:
            message_str = json.dumps(message, default=str)
            await websocket.send_text(message_str)
            return True
        except WebSocketDisconnect:
            return False
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {str(e)}")
            return False

    async def send_to_user(self, user_id: str, data: Any, message_type: str = "data", message: str = "Data received") -> bool:
        try:
            if user_id not in self.active_connections:
                logger.warning(f"No active connections for user {user_id}")
                return False
            
            formatted_response = returnsdata.success(data=data, msg=message, status=SUCCESS)
            response_body = json.loads(formatted_response.body.decode())
            websocket_message = {
                "type": message_type,
                "response": {
                    "type": message_type,
                    "data": response_body,
                    "message": message,
                    "status": SUCCESS
                },
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
            }
            
            disconnected_sockets = []
            success_count = 0
            
            for websocket in self.active_connections[user_id]:
                if await self.send_message_to_websocket(websocket, websocket_message):
                    success_count += 1
                else:
                    disconnected_sockets.append(websocket)
            
            for ws in disconnected_sockets:
                self.disconnect_user(ws, user_id)
            
            if success_count > 0:
                logger.info(f"Message sent to user {user_id} - Type: {message_type} - Connections: {success_count}")
                return True
            else:
                logger.warning(f"Failed to send message to user {user_id} - No active connections")
                return False
                
        except Exception as e:
            logger.error(f"Error sending to user {user_id}: {str(e)}")
            return False

    async def broadcast_to_station(self, db: AsyncSession, station_id: str, data: Any, message_type: str = "station_broadcast", message: str = "Station broadcast") -> Dict[str, bool]:
        try:
            listeners = await db.execute(select(StationListeners).where(StationListeners.station_id == station_id).where(StationListeners.last_seen > datetime.now() - timedelta(hours=24)))
            listeners = listeners.scalars().all()

            for listener in listeners:
                if listener.user_id in self.active_connections:
                    await self.send_to_user(
                        user_id=listener.user_id,
                        data=data,
                        message_type=message_type,
                        message=message
                    )
            adminuser = await db.execute(select(User).where(User.role != 'user'))
            adminuser = adminuser.scalars().all()
            if adminuser:
                for admin in adminuser:
                    await self.send_to_user(
                        user_id=admin.id,
                        data=data,
                        message_type=message_type,
                        message=message
                )
        except Exception as e:
            logger.error(f"Error broadcasting to station {station_id}: {str(e)}")
            return False

    async def broadcast_websocket_data(self, user_id: str, data: Any, type: str = "data", message: str = "Data received") -> bool:
        return await self.send_to_user(user_id=user_id, data=data, message_type=type, message=message)

    async def send_error_to_user(self, user_id: str, error_message: str, error_data: Any = None) -> bool:
        try:
            if user_id not in self.active_connections:
                return False
            
            formatted_response = returnsdata.error_msg_data(data=error_data, msg=error_message, status=ERROR)
            response_body = json.loads(formatted_response.body.decode())
            
            websocket_message = {
                "type": "error",
                "response": response_body,
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id
            }
            
            disconnected_sockets = []
            success_count = 0
            
            for websocket in self.active_connections[user_id]:
                if await self.send_message_to_websocket(websocket, websocket_message):
                    success_count += 1
                else:
                    disconnected_sockets.append(websocket)
            
            for ws in disconnected_sockets:
                self.disconnect_user(ws, user_id)
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending error to user {user_id}: {str(e)}")
            return False

    async def broadcast_to_multiple_users(self, user_ids: List[str], data: Any, message_type: str = "broadcast", message: str = "Broadcast message") -> Dict[str, bool]:
        results = {}
        for user_id in user_ids:
            results[user_id] = await self.send_to_user(
                user_id=user_id,
                data=data,
                message_type=message_type,
                message=message
            )
        return results

    def get_connected_users(self) -> List[str]:
        return list(self.active_connections.keys())

    def get_station_users(self, station_id: str) -> List[str]:
        """Get all user IDs connected to a specific station"""
        return self.station_users.get(station_id, [])

    def get_user_connection_count(self, user_id: str) -> int:
        return len(self.active_connections.get(user_id, []))

    def is_user_connected(self, user_id: str) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    async def send_heartbeat(self, user_id: str) -> bool:
        return await self.send_to_user(
            user_id=user_id,
            data={"ping": True},
            message_type="heartbeat",
            message="Heartbeat"
        )

    def get_connection_stats(self) -> Dict[str, Any]:
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        station_stats = {
            station_id: len(users) 
            for station_id, users in self.station_users.items()
        }
        
        return {
            "total_users": len(self.active_connections),
            "total_connections": total_connections,
            "users_connected": list(self.active_connections.keys()),
            "connections_per_user": {
                user_id: len(connections) 
                for user_id, connections in self.active_connections.items()
            },
            "station_listeners": station_stats,
            "total_stations": len(self.station_users)
        }

websocket_manager = WebSocketManager()