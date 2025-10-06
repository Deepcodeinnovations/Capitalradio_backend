# routes/websockets_routes.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.websocket_manager import websocket_manager
import json
import logging

logger = logging.getLogger(__name__)
websockets_routes = APIRouter(prefix="/websockets",tags=["WebSocket Event Stream"],responses={404: {"description": "Not found"}})

@websockets_routes.websocket("/eventStream/connect")
async def websocket_endpoint(websocket: WebSocket, token: str, db: AsyncSession = Depends(get_database)):
   connection_info = None
   user_id = None
   try:
       connection_info = await websocket_manager.connect_user(websocket, token, db)
       if not connection_info:
           return
       user_id = connection_info["user_id"]
       logger.info(f"WebSocket connection established for user {user_id}")
       while True:
           try:
               data = await websocket.receive_text()
               logger.info(f"Received message from user {user_id}: {data}")
           except WebSocketDisconnect:
               logger.info(f"WebSocket connection closed for user {user_id}")
               break
   except WebSocketDisconnect:
       logger.info(f"WebSocket disconnected for user {user_id}")
   except Exception as e:
       logger.error(f"WebSocket connection error for user {user_id}: {str(e)}")
   finally:
       if user_id:
           websocket_manager.disconnect_user(websocket, user_id)