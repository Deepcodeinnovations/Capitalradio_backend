from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Integer, Numeric
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, between, or_, asc, desc
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any

class Event(Base):
    __tablename__ = "events"
    
    # Basic event information
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    slug = Column(String(255), nullable=True, unique=True, index=True)
    
    # Event timing
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    start_time = Column(String(10), nullable=True)  # Format: "HH:MM"
    end_time = Column(String(10), nullable=True)    # Format: "HH:MM"
    
    # Location information
    venue_name = Column(String(255), nullable=True)
    venue_address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    is_virtual = Column(Boolean, default=False)
    virtual_link = Column(String(500), nullable=True)
    
    # Event details
    category = Column(String(100), nullable=True)  # concert, interview, show, etc.
    event_type = Column(String(50), nullable=True)  # public, private, vip
    currency = Column(String(10), nullable=True, default="UGX")
    
    # Media
    featured_image_path = Column(String(500), nullable=True)
    featured_image_url = Column(String(500), nullable=True)
    
    # Event settings
    is_featured = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    
    # Tracking
    views_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    created_by = Column(String(36), ForeignKey('users.id'), nullable=True)
    updated_by = Column(String(36), ForeignKey('users.id'), nullable=True)

    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'slug': self.slug,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'venue_name': self.venue_name,
            'venue_address': self.venue_address,
            'city': self.city,
            'country': self.country,
            'is_virtual': self.is_virtual,
            'virtual_link': self.virtual_link,
            'category': self.category,
            'event_type': self.event_type,
            'currency': self.currency,
            'featured_image_path': self.featured_image_path,
            'featured_image_url': self.featured_image_url,
            'is_featured': self.is_featured,
            'is_published': self.is_published,
            'views_count': self.views_count,
            'shares_count': self.shares_count,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.refresh(self)
            data = await self.to_dict()
            
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert event to dictionary with relations: {str(e)}")
    
    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.execute(delete(Event).where(Event.id == self.id))
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete event with relations: {str(e)}")
    
    @classmethod
    async def get_published_events(cls, db: AsyncSession, limit: int = 50):
        stmt = select(cls).where(
            and_(
                cls.is_published == True,
                cls.status == True,
                cls.state == True
            )
        ).order_by(asc(cls.start_date)).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @classmethod
    async def get_upcoming_events(cls, db: AsyncSession, limit: int = 10):
        now = datetime.utcnow()
        stmt = select(cls).where(
            and_(
                cls.is_published == True,
                cls.start_date >= now,
                cls.status == True,
                cls.state == True
            )
        ).order_by(asc(cls.start_date)).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @classmethod
    async def get_featured_events(cls, db: AsyncSession, limit: int = 5):
        stmt = select(cls).where(
            and_(
                cls.is_published == True,
                cls.is_featured == True,
                cls.status == True,
                cls.state == True
            )
        ).order_by(desc(cls.created_at)).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def increment_views(self, db: AsyncSession):
        self.views_count = self.views_count + 1
        await db.commit()
    
    async def increment_shares(self, db: AsyncSession):
        self.shares_count = self.shares_count + 1
        await db.commit()