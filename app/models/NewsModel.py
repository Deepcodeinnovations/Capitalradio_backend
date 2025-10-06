from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Integer, DECIMAL
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, between, or_, asc, desc
from sqlalchemy.orm import relationship, backref
from app.models.BaseModel import Base
from datetime import datetime
from typing import Optional, Dict, Any, List

class News(Base):
    __tablename__ = "news"
    
    title = Column(String(500), nullable=False)
    slug = Column(String(500), nullable=False, unique=True, index=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    excerpt = Column(String(500), nullable=True)
    
    # Media
    featured_image_path = Column(String(500), nullable=True)
    featured_image_url = Column(String(500), nullable=True)
    gallery_images = Column(JSON, nullable=True)  # Array of image objects
    
    # SEO
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(String(500), nullable=True)
    meta_keywords = Column(String(500), nullable=True)
    
    # Publishing
    published_at = Column(DateTime, nullable=True)
    is_published = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    is_breaking = Column(Boolean, default=False)
    
    # Content Organization
    category_id = Column(String(36), ForeignKey('news_categories.id'), nullable=True)
    station_id = Column(String(36), ForeignKey('stations.id'), nullable=True)
    author_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    
    # Engagement
    views_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    
    # Additional fields
    tags = Column(JSON, nullable=True)  # Array of tag strings
    reading_time = Column(Integer, nullable=True)  # Minutes
    source = Column(String(255), nullable=True)
    source_url = Column(String(500), nullable=True)
    priority = Column(Integer, default=0)  # For ordering
    
    # Relationships
    category = relationship("NewsCategory", backref=backref("news_articles", lazy="selectin"))
    station = relationship("Station", backref=backref("news_articles", lazy="selectin"))
    author = relationship("User", backref=backref("authored_news", lazy="selectin"))
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'summary': self.summary,
            'content': self.content,
            'excerpt': self.excerpt,
            'featured_image_path': self.featured_image_path,
            'featured_image_url': self.featured_image_url,
            'gallery_images': self.gallery_images,
            'meta_title': self.meta_title,
            'meta_description': self.meta_description,
            'meta_keywords': self.meta_keywords,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'is_published': self.is_published,
            'is_featured': self.is_featured,
            'is_breaking': self.is_breaking,
            'category_id': self.category_id,
            'station_id': self.station_id,
            'author_id': self.author_id,
            'views_count': self.views_count,
            'likes_count': self.likes_count,
            'shares_count': self.shares_count,
            'comments_count': self.comments_count,
            'tags': self.tags,
            'reading_time': self.reading_time,
            'source': self.source,
            'source_url': self.source_url,
            'priority': self.priority,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.refresh(self, ['category', 'station', 'author'])
            data = await self.to_dict()
            
            if self.category:
                data['category'] = await self.category.to_dict()
            if self.station:
                data['station'] = await self.station.to_dict()
            if self.author:
                data['author'] = await self.author.to_dict()
                
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert news to dictionary with relations: {str(e)}")


    async def delete_with_relations(self, db: AsyncSession) -> bool:
        try:
            await db.delete(self)
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete livechat message with relations: {str(e)}")


    

class NewsCategory(Base):
    __tablename__ = "news_categories"
    
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color
    icon = Column(String(100), nullable=True)
    parent_id = Column(String(36), ForeignKey('news_categories.id'), nullable=True)
    sort_order = Column(Integer, default=0)
    
    # Relationships
    parent = relationship("NewsCategory", remote_side="NewsCategory.id", backref="children")
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'color': self.color,
            'icon': self.icon,
            'parent_id': self.parent_id,
            'sort_order': self.sort_order,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class NewsComment(Base):
    __tablename__ = "news_comments"
    
    news_id = Column(String(36), ForeignKey('news.id'), nullable=False)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    parent_id = Column(String(36), ForeignKey('news_comments.id'), nullable=True)
    
    author_name = Column(String(255), nullable=True)
    author_email = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=False)
    likes_count = Column(Integer, default=0)
    
    # Relationships
    news = relationship("News", backref=backref("comments", lazy="selectin"))
    user = relationship("User", backref=backref("news_comments", lazy="selectin"))
    parent = relationship("NewsComment", remote_side="NewsComment.id", backref="replies")
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'news_id': self.news_id,
            'user_id': self.user_id,
            'parent_id': self.parent_id,
            'author_name': self.author_name,
            'author_email': self.author_email,
            'content': self.content,
            'is_approved': self.is_approved,
            'likes_count': self.likes_count,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }