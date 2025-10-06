from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any, List

class Host(Base):
    __tablename__ = "hosts"
    
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    # Basic Information
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(100), nullable=False, unique=True)
    role = Column(String(500), nullable=True)
    phone = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    
    # Links and Access
    social_media = Column(String(500), nullable=True)
    experience_years = Column(String(500), nullable=True)
    on_air_status = Column(Boolean, default=True)
    image_url = Column(String(500), nullable=True)
    image_path = Column(String(500), nullable=True)
    
    # Meta Information
    created_by = Column(String(36), ForeignKey('users.id'), nullable=True)
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'email': self.email,
            'role': self.role,
            'phone': self.phone,
            'bio': self.bio,
            'social_media': self.social_media,
            'experience_years': self.experience_years,
            'on_air_status': self.on_air_status,
            'image_url': self.image_url,
            'image_path': self.image_path,
            'user_id': self.user_id,
            'created_by': self.created_by,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession, include_programs: bool = False) -> Dict[str, Any]:
        try:
            await db.refresh(self)
            data = await self.to_dict()

            if include_programs:
                programs = await self.get_host_programs(db)
                if programs:
                    data['programs'] = programs
                else:
                    data['programs'] = []
        
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert station to dictionary with relations: {str(e)}")


    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.execute(delete(Host).where(Host.id == self.id))
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete station with relations: {str(e)}")


    async def get_host_programs(self, db: AsyncSession) -> List[Dict[str, Any]]:
        try:
            from app.models.RadioProgramModel import RadioProgram
            
            # Get all programs and filter in Python since hosts is JSON
            stmt = select(RadioProgram).where(
                and_(
                    RadioProgram.state == True,
                    RadioProgram.status == True,
                    RadioProgram.hosts.isnot(None)
                )
            )
            result = await db.execute(stmt)
            all_programs = result.scalars().all()
            
            # Filter programs that contain this host
            host_programs = []
            for program in all_programs:
                if program.hosts:
                    for host in program.hosts:
                        if isinstance(host, dict) and host.get('id') == self.id:
                            host_programs.append(program)
                            break
            
            return [await program.to_dict() for program in host_programs]
            
        except Exception as e:
            raise Exception(f"Failed to get host programs: {str(e)}")