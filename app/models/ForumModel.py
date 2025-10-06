from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import relationship, backref
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any

class Forum(Base):
    __tablename__ = "forums"
    
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    station_id = Column(String(36), ForeignKey('stations.id'), nullable=False)
    created_by = Column(String(36), ForeignKey('users.id'), nullable=False)
    slug = Column(String(500), nullable=False, unique=True, default=func.lower(func.concat('forum_', func.md5(func.concat('forum_', func.now())))))
    is_pinned = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    views = Column(JSON, default={})
    # Relationships
    station = relationship("Station", backref=backref("forums", lazy="selectin"))
    creator = relationship("User", backref=backref("created_forums", lazy="selectin"))
    comments = relationship("ForumComment", back_populates="forum", lazy="selectin", cascade="all, delete-orphan")

    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'body': self.body,
            'slug': self.slug,
            'is_pinned': self.is_pinned,
            'is_published': self.is_published,
            'station_id': self.station_id,
            'created_by': self.created_by,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.refresh(self, ['station', 'creator', 'comments'])
            data = await self.to_dict()
            
            # Add related entities data
            if self.station:
                data['station'] = await self.station.to_dict()
            
            if self.creator:
                data['creator'] = {
                    'id': self.creator.id,
                    'name': self.creator.name,
                    'email': self.creator.email,
                    'image_url': self.creator.image_url
                }
            
            # Add comments count (only active comments)
            if self.comments:
                active_comments = [c for c in self.comments if c.state == True]
                data['comments_count'] = len(active_comments)
            else:
                data['comments_count'] = 0

            if self.views:
                data['views_count'] = len(self.views)
            else:
                data['views_count'] = 0    
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert forum to dictionary with relations: {str(e)}")
    
    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.refresh(self, ['comments'])
            
            if self.comments:
                from app.models.ForumCommentModel import ForumComment
                for comment in self.comments:
                    comment_query = select(ForumComment).where(ForumComment.id == comment.id)
                    comm = await db.execute(comment_query)
                    comment_obj = comm.scalar_one_or_none()
                    if comment_obj:
                        await comment_obj.delete_with_relations(db)
            
            await db.execute(delete(Forum).where(Forum.id == self.id))
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete forum with relations: {str(e)}")
