from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, between, or_, asc, desc
from sqlalchemy.future import select
from sqlalchemy.orm import relationship
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any, List


class RadioProgram(Base):
    __tablename__ = "radio_programs"
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=False, default='live_show')  # live_show, interview, podcast, news, music, talk_show, sports, special
    duration = Column(Integer, nullable=False, default=60)  # Duration in minutes
    station_id = Column(String(36), ForeignKey('stations.id'), nullable=False, index=True)
    studio = Column(String(10), nullable=False, default='A')  # A, B, C, D
    hosts = Column(JSON, nullable=True, default=list)  # JSON array of host objects
    image_path = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)
    created_by = Column(String(36), ForeignKey('users.id'), nullable=True)
    listener_favorite = Column(Boolean, default=False)  # JSON array of listener favorite objects


    creator = relationship("User", foreign_keys=[created_by])
    station = relationship("Station", back_populates="programs")
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'type': self.type,
            'duration': self.duration,
            'station_id': self.station_id,
            'studio': self.studio,
            'hosts': self.hosts,
            'image_path': self.image_path,
            'image_url': self.image_url,
            'created_by': self.created_by,
            'state': self.state,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.refresh(self, ['station', 'creator'])
            data = await self.to_dict()
            if self.station:
                data['station'] = {
                    'id': self.station.id,
                    'name': self.station.name,
                    'frequency': self.station.frequency,
                    'tagline': self.station.tagline,
                    'access_link': self.station.access_link,
                    'streaming_link': self.station.streaming_link,
                    'streaming_status': self.station.streaming_status,
                    'radio_access_status': self.station.radio_access_status
                }
            hosts = await self.get_program_hosts(db, self.hosts)
            if hosts:
                data['hosts'] = hosts
            else:
                data['hosts'] = []
            
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert radio program to dictionary with relations: {str(e)}")
    
  

    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.execute(delete(RadioProgram).where(RadioProgram.id == self.id))
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete radio program with relations: {str(e)}")
    

    async def get_program_hosts(self, db: AsyncSession, hosts_json: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            from app.models.HostModel import Host
            hosts_ids = [host['id'] for host in hosts_json]
            stmt = select(Host).where(Host.id.in_(hosts_ids))
            result = await db.execute(stmt)
            hosts = result.scalars().all()
            return [await host.to_dict() for host in hosts]
        except Exception as e:
            raise Exception(f"Failed to get program hosts: {str(e)}")