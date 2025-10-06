from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import relationship, backref
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any

class ForumComment(Base):
    __tablename__ = "forum_comments"
    
    content = Column(Text, nullable=False)
    forum_id = Column(String(36), ForeignKey('forums.id'), nullable=False)
    reply_to = Column(String(36), ForeignKey('forum_comments.id'), nullable=True)
    created_by = Column(String(36), ForeignKey('users.id'), nullable=False)
    
    # Relationships
    forum = relationship("Forum", back_populates="comments", lazy="selectin")
    creator = relationship("User", backref=backref("forum_comments", lazy="selectin"))
    
    # Self-referencing relationship - fixed
    reply_to_comment = relationship("ForumComment", remote_side="ForumComment.id", back_populates="replies", lazy="selectin")
    replies = relationship("ForumComment", back_populates="reply_to_comment", lazy="selectin")

    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content': self.content,
            'forum_id': self.forum_id,
            'reply_to': self.reply_to,
            'created_by': self.created_by,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.refresh(self, ['forum', 'creator', 'reply_to_comment', 'replies'])
            data = await self.to_dict()
            
            if self.forum:
                data['forum'] = {
                    'id': self.forum.id,
                    'title': self.forum.title,
                    'status': self.forum.status,
                    'state': self.forum.state,
                    'created_at': self.forum.created_at.isoformat() if self.forum.created_at else None,
                    'updated_at': self.forum.updated_at.isoformat() if self.forum.updated_at else None
                }
            
            if self.creator:
                data['creator'] = {
                    'id': self.creator.id,
                    'name': self.creator.name,
                    'email': self.creator.email,
                    'image_url': self.creator.image_url
                }
                
            if self.reply_to_comment:
                data['reply_to_comment'] = {
                    'id': self.reply_to_comment.id,
                    'content': self.reply_to_comment.content,
                    'forum_id': self.reply_to_comment.forum_id,
                    'reply_to': self.reply_to_comment.reply_to,
                    'created_by': self.reply_to_comment.created_by,
                    'status': self.reply_to_comment.status,
                    'state': self.reply_to_comment.state,
                    'created_at': self.reply_to_comment.created_at.isoformat() if self.reply_to_comment.created_at else None,
                    'updated_at': self.reply_to_comment.updated_at.isoformat() if self.reply_to_comment.updated_at else None
                }
                
            if self.replies:
                data['replies'] = []
                for reply in self.replies:
                    await db.refresh(reply, ['creator'])
                    reply_data = {
                        'id': reply.id,
                        'content': reply.content,
                        'forum_id': reply.forum_id,
                        'reply_to': reply.reply_to,
                        'created_by': reply.created_by,
                        'status': reply.status,
                        'state': reply.state,
                        'created_at': reply.created_at.isoformat() if reply.created_at else None,
                        'updated_at': reply.updated_at.isoformat() if reply.updated_at else None
                    }
                    
                    if reply.creator:
                        reply_data['creator'] = {
                            'id': reply.creator.id,
                            'name': reply.creator.name,
                            'email': reply.creator.email,
                            'image_url': reply.creator.image_url
                        }
                    
                    data['replies'].append(reply_data)
                
                data['replies_count'] = len(self.replies)
            else:
                data['replies_count'] = 0
                
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert forum comment to dictionary with relations: {str(e)}")
    
    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.refresh(self, ['replies'])
            if self.replies:
                for reply in self.replies:
                    await db.execute(delete(ForumComment).where(ForumComment.id == reply.id))
            await db.execute(delete(ForumComment).where(ForumComment.id == self.id))
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete forum comment with relations: {str(e)}")