from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import relationship, backref
from app.models.BaseModel import Base
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import urllib.parse

class Station(Base):
    __tablename__ = "stations"
    
    # Basic Information
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    frequency = Column(String(100), nullable=False, unique=True)
    tagline = Column(String(500), nullable=True)
    about = Column(Text, nullable=True)
    
    # Links and Access
    access_link = Column(String(500), nullable=True)
    streaming_link = Column(String(500), nullable=True)
    backup_streaming_link = Column(String(500), nullable=True)
    # Streaming Information
    streaming_status = Column(String(50), default="offline")  # live, offline, maintenance
    radio_access_status = Column(Boolean, default=True)
    
    # Media
    logo_path = Column(String(500), nullable=True)
    logo_url = Column(String(500), nullable=True)
    banner_path = Column(String(500), nullable=True)
    banner_url = Column(String(500), nullable=True)
    
    # Meta Information
    created_by = Column(String(36), ForeignKey('users.id'), nullable=True)
    programs = relationship("RadioProgram", back_populates="station")
    schedule = relationship("StationSchedule", back_populates="station", uselist=False)
    
    def get_secure_streaming_url(self) -> Optional[str]:
        """Get streaming URL that works with HTTPS"""
        if not self.streaming_link:
            return None
        
        # If it's already HTTPS, return as is
        if self.streaming_link.startswith('https://'):
            return self.streaming_link
        
        # If it's HTTP, create proxy URL
        if self.streaming_link.startswith('http://'):
            from app.utils.constants import BASE_URL
            encoded_url = urllib.parse.quote(self.streaming_link, safe='')
            return f"{BASE_URL}api/v1/user/streaming/proxy?url={encoded_url}"
        
        return self.streaming_link
    
    def get_secure_backup_streaming_url(self) -> Optional[str]:
        """Get backup streaming URL that works with HTTPS"""
        if not self.backup_streaming_link:
            return None
        
        # If it's already HTTPS, return as is
        if self.backup_streaming_link.startswith('https://'):
            return self.backup_streaming_link
        
        # If it's HTTP, create proxy URL
        if self.backup_streaming_link.startswith('http://'):
            from app.utils.constants import BASE_URL
            encoded_url = urllib.parse.quote(self.backup_streaming_link, safe='')
            return f"{BASE_URL}api/v1/user/streaming/proxy?url={encoded_url}"
        
        return self.backup_streaming_link
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'frequency': self.frequency,
            'tagline': self.tagline,
            'about': self.about,
            'access_link': self.access_link,
            'streaming_link': self.get_secure_streaming_url(),  # Always return secure URL
            'streaming_link_original': self.streaming_link,  # Keep original for admin reference
            'backup_streaming_link': self.get_secure_backup_streaming_url(),
            'backup_streaming_link_original': self.backup_streaming_link,
            'streaming_status': self.streaming_status,
            'radio_access_status': self.radio_access_status,
            'logo_path': self.logo_path,
            'logo_url': self.logo_url,
            'banner_path': self.banner_path,
            'banner_url': self.banner_url,
            'created_by': self.created_by,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession, include_programs: bool = False, include_schedule: bool = False) -> Dict[str, Any]:
        try:
            await db.refresh(self, ['programs','schedule'])
            data = await self.to_dict()
            
            if self.created_by:
                from app.models.UserModel import User
                creator_result = await db.execute(select(User).where(User.id == self.created_by))
                creator = creator_result.scalar_one_or_none()
                if creator:
                    data['creator'] = {
                        'id': creator.id,
                        'name': creator.name,
                        'email': creator.email,
                        'role': creator.role,
                        'created_at': creator.created_at.isoformat() if creator.created_at else None,
                        'updated_at': creator.updated_at.isoformat() if creator.updated_at else None
                    }
                else:
                    data['creator'] = None
            else:
                data['creator'] = None
            
            listeners = await self.get_listeners(db)
            data['listeners'] = listeners if listeners else 0
            
            data['stats'] = {
                'total_listeners': listeners if listeners else 0,
                'is_streaming': self.streaming_status == 'live',
                'is_accessible': self.radio_access_status and self.status and self.state
            }
            
            if include_programs:
                if self.programs:
                    data['programs'] = [await program.to_dict_with_relations(db) for program in self.programs if program]
                else:
                    data['programs'] = []
            
            if include_schedule:
                if self.schedule:
                    data['schedule'] = await self.schedule.to_dict_with_relations(db)
                else:
                    data['schedule'] = None
            
            return data
                    
        except Exception as e:
            raise Exception(f"Failed to convert station to dictionary with relations: {str(e)}")

    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            self.state = False
            self.status = False
            self.updated_at = datetime.utcnow()
            
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete station with relations: {str(e)}")

    async def get_listeners(self, db: AsyncSession) -> int:
        from app.models.StationListenersModel import StationListeners
        try:
            result = await db.execute(select(func.count(StationListeners.id)).where(StationListeners.station_id == self.id).where(StationListeners.last_seen > datetime.now() - timedelta(hours=24)))
            return result.scalar_one_or_none()
        except Exception as e:
            raise Exception(f"Failed to get listeners: {str(e)}")