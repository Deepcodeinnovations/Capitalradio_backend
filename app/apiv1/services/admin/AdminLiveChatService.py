from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy import and_, desc, asc
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.StationModel import Station
from slugify import slugify
from app.utils.file_upload import save_upload_file, remove_file
import math
from app.models.LiveChatMessageModel import LiveChatMessage
from app.utils.websocket_manager import websocket_manager
from sqlalchemy.orm import selectinload


async def get_station_livechat_messages(db: AsyncSession,  limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    try:
        limit = min(limit, 200)  # Enforce 200 message limit
        
        query = select(LiveChatMessage).options(selectinload(LiveChatMessage.user),selectinload(LiveChatMessage.station)).where(and_(LiveChatMessage.is_visible == True,LiveChatMessage.state == True,LiveChatMessage.status == True)).order_by(asc(LiveChatMessage.created_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return [await message.to_dict_with_relations(db=db) for message in messages]
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



async def delete_station_livechat_message(db: AsyncSession, message_id: str) -> bool:
    try:
        messages_data = {}
        message_query = await db.execute(select(LiveChatMessage).where(LiveChatMessage.id == message_id))
        messages_data = message_query.scalar_one_or_none()
        station_id = messages_data.station_id

        message_dict = await messages_data.to_dict_with_relations(db=db)
        await messages_data.delete_with_relations(db)
        await websocket_manager.broadcast_to_station(
                db=db,
                station_id=station_id,
                data={"message": message_dict},
                message_type="deleted_message",
                message="Deleted chat message"
            )
        return True
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def create_livechat_message(db: AsyncSession,station_id: str, message: str,user_id: Optional[str] = None,message_type: str = "user",metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        # Verify station exists
        station_result = await db.execute(select(Station).where(and_(Station.id == station_id, Station.state == True, Station.status == True)))
        station = station_result.scalar_one_or_none()
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        chat_message = LiveChatMessage(
            station_id=station_id,
            user_id=user_id,
            message=message,
            message_type=message_type,
        )
        
        db.add(chat_message)
        await db.commit()
        await db.refresh(chat_message)
        
        message_dict = await chat_message.to_dict_with_relations(db=db)

        if user_id:
            await websocket_manager.broadcast_to_station(
                db=db,
                station_id=station_id,
                data={"message": message_dict},
                message_type="livechat_message",
                message="New chat message"
            )
        return message_dict
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
