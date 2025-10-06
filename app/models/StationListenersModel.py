from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import relationship, backref

class StationListeners(Base):
    __tablename__ = "station_listeners"
    
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    # Basic Information
    station_id = Column(String(36), ForeignKey('stations.id'), nullable=True)
    last_seen = Column(DateTime, nullable=True)
    # Meta Information
    user = relationship("User", backref=backref("station_listeners", lazy="selectin"))
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'station_id': self.station_id,
            'user_id': self.user_id,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.execute(delete(StationListeners).where(StationListeners.id == self.id))
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete station listeners with relations: {str(e)}")


    @staticmethod
    async def create_station_listener(db: AsyncSession, user_id: str, station_id: str) -> bool:
        try:
            result = await db.execute(select(StationListeners).where(and_(StationListeners.station_id == station_id, (user_id is None or StationListeners.user_id == user_id))))
            if user := result.scalars().first():
                user.last_seen = datetime.now()
                await db.commit()
                return True
            else:
                user = StationListeners(station_id=station_id, user_id=user_id, last_seen=datetime.now())
                db.add(user)
                await db.commit()
                return True
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to create station listeners with relations: {str(e)}")
    