from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, between, or_, asc, desc
from slugify import slugify
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any, List
from app.database import get_database
from app.models.NewsModel import News, NewsCategory, NewsComment
from app.models.UserModel import User
from app.utils.returns_data import returnsdata
from app.utils.constants import SUCCESS, ERROR
from app.utils.file_upload import save_upload_file, remove_file
import re
import os
import random
import uuid

async def get_user_news(db: AsyncSession,station_id: str, filters: dict = None, per_page: int = 1, page: int = 1) -> Dict[str, Any]:
    try:
        query = select(News).where(News.state == True, News.is_published == True, News.station_id == station_id)
        
        if filters:
            if filters.get("is_featured"):
                query = query.where(News.is_featured == True)
            if filters.get("is_breaking"):
                query = query.where(News.is_breaking == True)
            if filters.get("category_id"):
                query = query.where(News.category_id == filters.get("category_id"))
            if filters.get("author_id"):
                query = query.where(News.author_id == filters.get("author_id"))
            if filters.get("search"):
                search_term = f"%{filters.get('search')}%"
                query = query.where(or_(
                    News.title.ilike(search_term),
                    News.content.ilike(search_term),
                    News.summary.ilike(search_term)
                ))

        # Base query for counting
        count_query = select(func.count(News.id)).where(News.state == True, News.is_published == True)
        
        # Apply same filters to count query
        if filters:
            if filters.get("is_featured"):
                count_query = count_query.where(News.is_featured == True)
            if filters.get("is_breaking"):
                count_query = count_query.where(News.is_breaking == True)
            if filters.get("category_id"):
                count_query = count_query.where(News.category_id == filters.get("category_id"))
            if filters.get("station_id"):
                count_query = count_query.where(News.station_id == filters.get("station_id"))
            if filters.get("author_id"):
                count_query = count_query.where(News.author_id == filters.get("author_id"))
            if filters.get("search"):
                search_term = f"%{filters.get('search')}%"
                count_query = count_query.where(or_(
                    News.title.ilike(search_term),
                    News.content.ilike(search_term),
                    News.summary.ilike(search_term)
                ))

        # Ordering
        if filters and filters.get("order_by"):
            if filters.get("order_by") == "published_at":
                query = query.order_by(desc(News.published_at))
            elif filters.get("order_by") == "views":
                query = query.order_by(desc(News.views_count))
            elif filters.get("order_by") == "priority":
                query = query.order_by(desc(News.priority))
            else:
                query = query.order_by(desc(News.created_at))
        else:
            query = query.order_by(desc(News.created_at))

        # Pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        # Execute queries
        result = await db.execute(query)
        articles = result.scalars().all()
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        articles_data = []
        for article in articles:
            articles_data.append(await article.to_dict_with_relations(db))
        
        return {
            "data": articles_data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get news articles: {str(e)}")


async def get_user_news_breaking(db: AsyncSession,station_id: str, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
    try:
        query = select(News).where(News.state == True, News.is_breaking == True, News.station_id == station_id)
        
        query = query.order_by(desc(News.created_at))

        # Pagination    
        page = 1
        per_page = limit
        offset = (page - 1) * per_page
        
        query = query.offset(offset).limit(per_page)
        
        result = await db.execute(query)
        articles = result.scalars().all()
        
        # Get total count
        count_query = select(func.count(News.id)).where(News.state == True)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        articles_data = []  
        for article in articles:
            articles_data.append(await article.to_dict_with_relations(db))
        
        return {
            "data": articles_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get news articles: {str(e)}")
        


async def get_news_article_by_slug(db: AsyncSession, slug: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(News).where(and_(News.slug == slug, News.state == True, News.is_published == True)))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="News article not found")
            
        # Increment views count
        article.views_count += 1
        await db.commit()
            
        return await article.to_dict_with_relations(db)
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get news article: {str(e)}")

