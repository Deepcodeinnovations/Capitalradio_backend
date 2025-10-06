from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import relationship
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any, List

class LiveChatMessage(Base):
    __tablename__ = "livechat_messages"
    station_id = Column(String(36), ForeignKey('stations.id'), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    message = Column(Text, nullable=False)
    message_type = Column(String(20), default='user')  # user, system, moderator
    is_visible = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    station = relationship("Station", foreign_keys=[station_id])
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'station_id': self.station_id,
            'user_id': self.user_id,
            'message': self.message,
            'message_type': self.message_type,
            'is_visible': self.is_visible,
            'state': self.state,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.refresh(self,['user','station'])
            data = await self.to_dict()

            if self.user:
                data['user'] = await self.user.to_dict()
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert livechat message to dictionary with relations: {str(e)}")


    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.execute(delete(LiveChatMessage).where(LiveChatMessage.id == self.id))
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete livechat message with relations: {str(e)}")