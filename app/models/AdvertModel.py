from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import relationship, backref
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any


class Advert(Base):
    __tablename__ = "adverts"
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    target_url = Column(String(500), nullable=True)
    button_title = Column(String(100), nullable=True)
    image_path = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)
    station_id = Column(String(36), ForeignKey('stations.id'), nullable=False)
    created_by = Column(String(36), ForeignKey('users.id'), nullable=False)
    
    # Engagement metrics
    views_count = Column(String(36), default=0)
    clicks_count = Column(String(36), default=0)
    
    # Relationships
    station = relationship("Station", backref=backref("adverts", lazy="selectin"))
    creator = relationship("User", backref=backref("created_adverts", lazy="selectin"))

    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'target_url': self.target_url,
            'button_title': self.button_title,
            'image_path': self.image_path,
            'image_url': self.image_url,
            'station_id': self.station_id,
            'created_by': self.created_by,
            'views_count': self.views_count,
            'clicks_count': self.clicks_count,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.refresh(self, ['station', 'creator'])
            data = await self.to_dict()
            
            # Add related entities data
            if self.station:
                data['station'] = {
                    'id': self.station.id,
                    'name': self.station.name,
                    'slug': getattr(self.station, 'slug', None),
                    'status': self.station.status
                }
            
            if self.creator:
                data['creator'] = {
                    'id': self.creator.id,
                    'name': self.creator.name,
                    'email': self.creator.email
                }
                
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert advert to dictionary with relations: {str(e)}")
    
    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.execute(delete(Advert).where(Advert.id == self.id))
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete advert with relations: {str(e)}")
    
    async def increment_views(self, db: AsyncSession) -> bool:
        try:
            self.views_count += 1
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to increment views: {str(e)}")
    
    async def increment_clicks(self, db: AsyncSession) -> bool:
        try:
            self.clicks_count += 1
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to increment clicks: {str(e)}")
    
    @property
    def engagement_rate(self) -> float:
        """
        Calculate engagement rate (clicks/views)
        """
        if self.views_count == 0:
            return 0.0
        return (self.clicks_count / self.views_count) * 100
    
    def is_active(self) -> bool:
        """
        Check if advert is active and not deleted
        """
        return self.status and self.state