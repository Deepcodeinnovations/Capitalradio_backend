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

async def create_news_article(db: AsyncSession, data: dict, author_id: str, featured_image: Optional[UploadFile] = None, gallery_images: List[UploadFile] = None) -> Dict[str, Any]:
    try:
        if not data.get("title"):
            raise HTTPException(status_code=400, detail="Title is required")
        
        if not data.get("content"):
            raise HTTPException(status_code=400, detail="Content is required")
        
        if not data.get("category_id"):
            raise HTTPException(status_code=400, detail="Category ID is required")
        
        if not data.get("station_id"):
            raise HTTPException(status_code=400, detail="Station ID is required")
        
        if not data.get("author_id"):
            raise HTTPException(status_code=400, detail="Author ID is required")
        
        # Generate slug from title
        slug = slugify(data.get("title"))
        
        # Check if slug already exists
        existing_article = await db.execute(select(News).where(News.slug == slug))
        if existing_article.scalar_one_or_none():
            slug = f"{slug}-{random.randint(1000, 9999)}"

        # Calculate reading time (approximately 200 words per minute)
        word_count = len(data.get("content", "").split())
        reading_time = max(1, round(word_count / 200))

        # Handle featured image upload
        featured_image_path = None
        featured_image_url = None
        if featured_image:
            featured_image_path, featured_image_url = await save_upload_file(featured_image, "news")

        # Handle gallery images upload
        gallery_images_data = []
        if gallery_images:
            for i, image in enumerate(gallery_images):
                if image:
                    image_path, image_url = await save_upload_file(image, "news/gallery")
                    gallery_images_data.append({
                        "id": str(uuid.uuid4()),
                        "path": image_path,
                        "url": image_url,
                        "order": i + 1,
                        "alt": f"Gallery image {i + 1}",
                        "caption": ""
                    })

        new_article = News(
            title=data.get("title"),
            slug=slug,
            summary=data.get("summary"),
            content=data.get("content"),
            excerpt=data.get("excerpt"),
            featured_image_path=featured_image_path,
            featured_image_url=featured_image_url,
            gallery_images=gallery_images_data if gallery_images_data else None,
            meta_title=data.get("meta_title") or data.get("title"),
            meta_description=data.get("meta_description") or data.get("summary"),
            meta_keywords=data.get("meta_keywords"),
            published_at=datetime.utcnow() if data.get("is_published") else None,
            is_published=data.get("is_published", False),
            is_featured=data.get("is_featured", False),
            is_breaking=data.get("is_breaking", False),
            category_id=data.get("category_id"),
            station_id=data.get("station_id"),
            author_id=author_id,
            tags=data.get("tags"),
            reading_time=reading_time,
            source=data.get("source"),
            source_url=data.get("source_url"),
            priority=data.get("priority", 0),
            status=True,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_article)
        await db.commit()
        await db.refresh(new_article)
        return await new_article.to_dict_with_relations(db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create news article: {str(e)}")



async def update_news_article(db: AsyncSession, article_id: str, data: dict, featured_image: Optional[UploadFile] = None, gallery_images: List[UploadFile] = None) -> Dict[str, Any]:
    try:
        result = await db.execute(select(News).where(and_(News.id == article_id, News.state == True)))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="News article not found")

        # Update slug if title changed
        if data.get("title") and data.get("title") != article.title:
            new_slug = slugify(data.get("title"))
            existing_article = await db.execute(select(News).where(and_(News.slug == new_slug, News.id != article_id)))
            if existing_article.scalar_one_or_none():
                new_slug = f"{new_slug}-{random.randint(1000, 9999)}"
            article.slug = new_slug

        # Handle featured image upload
        if featured_image:
            if article.featured_image_path:
                remove_file(article.featured_image_path)
            featured_image_path, featured_image_url = await save_upload_file(featured_image, "news")
            article.featured_image_path = featured_image_path
            article.featured_image_url = featured_image_url

        # Handle gallery images upload
        if gallery_images:
            # Remove old gallery images
            if article.gallery_images:
                for old_image in article.gallery_images:
                    if old_image.get("path"):
                        remove_file(old_image.get("path"))
            
            # Upload new gallery images
            gallery_images_data = []
            for i, image in enumerate(gallery_images):
                if image:
                    image_path, image_url = await save_upload_file(image, "news/gallery")
                    gallery_images_data.append({
                        "id": str(uuid.uuid4()),
                        "path": image_path,
                        "url": image_url,
                        "order": i + 1,
                        "alt": f"Gallery image {i + 1}",
                        "caption": ""
                    })
            article.gallery_images = gallery_images_data if gallery_images_data else None

        # Update fields
        for field, value in data.items():
            if hasattr(article, field) and value is not None:
                setattr(article, field, value)

        # Update reading time if content changed
        if data.get("content"):

            word_count = len(data.get("content").split())
            article.reading_time = max(1, round(word_count / 200))
            article.content = data.get("content", article.content)

        # Update published_at if publishing status changed
        if data.get("is_published") and not article.published_at:
            article.published_at = datetime.utcnow()
        elif not data.get("is_published"):
            article.published_at = None
        
        article.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(article)
        return await article.to_dict_with_relations(db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update news article: {str(e)}")

async def get_news_article_by_id(db: AsyncSession, article_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(News).where(and_(News.id == article_id, News.state == True)))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="News article not found")
            
        return await article.to_dict_with_relations(db)
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get news article: {str(e)}")

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

async def get_news_articles(db: AsyncSession, filters: dict = None) -> Dict[str, Any]:
    try:
        query = select(News).where(News.state == True)
        
        if filters:
            if filters.get("is_published"):
                query = query.where(News.is_published == True)
            if filters.get("is_featured"):
                query = query.where(News.is_featured == True)
            if filters.get("is_breaking"):
                query = query.where(News.is_breaking == True)
            if filters.get("category_id"):
                query = query.where(News.category_id == filters.get("category_id"))
            if filters.get("station_id"):
                query = query.where(News.station_id == filters.get("station_id"))
            if filters.get("author_id"):
                query = query.where(News.author_id == filters.get("author_id"))
            if filters.get("search"):
                search_term = f"%{filters.get('search')}%"
                query = query.where(or_(
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
        page = filters.get("page", 1) if filters else 1
        per_page = filters.get("per_page", 20) if filters else 20
        offset = (page - 1) * per_page
        
        query = query.offset(offset).limit(per_page)
        
        result = await db.execute(query)
        articles = result.scalars().all()
        
        # Get total count
        count_query = select(func.count(News.id)).where(News.state == True)
        if filters:
            if filters.get("is_published"):
                count_query = count_query.where(News.is_published == True)
            if filters.get("category_id"):
                count_query = count_query.where(News.category_id == filters.get("category_id"))
            if filters.get("station_id"):
                count_query = count_query.where(News.station_id == filters.get("station_id"))
        
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

async def delete_news_article(db: AsyncSession, article_id: str) -> bool:
    try:
        result = await db.execute(select(News).where(and_(News.id == article_id, News.state == True)))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="News article not found")

        success = await article.delete_with_relations(db)
        return success
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete news article: {str(e)}")

async def create_news_category(db: AsyncSession, data: dict) -> Dict[str, Any]:
    try:
        if not data.get("name"):
            raise HTTPException(status_code=400, detail="Category name is required")

        slug = slugify(data.get("name"))
        
        # Check if slug already exists
        existing_category = await db.execute(select(NewsCategory).where(NewsCategory.slug == slug))
        if existing_category.scalar_one_or_none():
            slug = f"{slug}-{random.randint(1000, 9999)}"

        new_category = NewsCategory(
            name=data.get("name"),
            slug=slug,
            description=data.get("description"),
            color=data.get("color"),
            icon=data.get("icon"),
            parent_id=data.get("parent_id"),
            sort_order=data.get("sort_order", 0),
            status=True,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)
        return await new_category.to_dict()
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create news category: {str(e)}")

async def update_news_category(db: AsyncSession, category_id: str, data: dict) -> Dict[str, Any]:
    try:
        result = await db.execute(select(NewsCategory).where(and_(NewsCategory.id == category_id, NewsCategory.state == True)))
        category = result.scalar_one_or_none()
        
        if not category:
            raise HTTPException(status_code=404, detail="News category not found")
        
        for field, value in data.items():
            if hasattr(category, field) and value is not None:
                setattr(category, field, value)
        
        category.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(category)
        return await category.to_dict()
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update news category: {str(e)}")

async def get_news_categories(db: AsyncSession) -> List[Dict[str, Any]]:
    try:
        result = await db.execute(select(NewsCategory).where(NewsCategory.state == True).order_by(NewsCategory.sort_order))
        categories = result.scalars().all()
        
        categories_data = []
        for category in categories:
            categories_data.append(await category.to_dict())
        
        return categories_data
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get news categories: {str(e)}")

async def update_article_engagement(db: AsyncSession, article_id: str, action: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(News).where(and_(News.id == article_id, News.state == True)))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="News article not found")
        
        if action == "like":
            article.likes_count += 1
        elif action == "share":
            article.shares_count += 1
        elif action == "view":
            article.views_count += 1
        
        await db.commit()
        await db.refresh(article)
        return await article.to_dict()
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update article engagement: {str(e)}")

async def get_trending_news(db: AsyncSession, limit: int = 10) -> List[Dict[str, Any]]:
    try:
        # Get articles from last 7 days ordered by views and engagement
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        query = select(News).where(
            and_(
                News.state == True,
                News.is_published == True,
                News.published_at >= week_ago
            )
        ).order_by(
            desc(News.views_count + News.likes_count + News.shares_count)
        ).limit(limit)
        
        result = await db.execute(query)
        articles = result.scalars().all()
        
        articles_data = []
        for article in articles:
            articles_data.append(await article.to_dict_with_relations(db))
        
        return articles_data
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get trending news: {str(e)}")



async def update_news_article_image(db: AsyncSession, article_id: str, featured_image: UploadFile) -> Dict[str, Any]:
    try:
        result = await db.execute(select(News).where(and_(News.id == article_id, News.state == True)))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="News article not found")
        
        # Remove old image
        if article.featured_image_path:
            remove_file(article.featured_image_path)
        
        # Upload new image
        featured_image_path, featured_image_url = await save_upload_file(featured_image, "news")
        article.featured_image_path = featured_image_path
        article.featured_image_url = featured_image_url
        article.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(article)
        return await article.to_dict_with_relations(db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update article image: {str(e)}")



async def add_gallery_images(db: AsyncSession, article_id: str, gallery_images: List[UploadFile]) -> Dict[str, Any]:
    try:
        result = await db.execute(select(News).where(and_(News.id == article_id, News.state == True)))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="News article not found")
        
        existing_gallery = article.gallery_images or []
        new_gallery_images = []
        
        for i, image in enumerate(gallery_images):
            if image:
                image_path, image_url = await save_upload_file(image, "news/gallery")
                new_gallery_images.append({
                    "id": str(uuid.uuid4()),
                    "path": image_path,
                    "url": image_url,
                    "order": len(existing_gallery) + i + 1,
                    "alt": f"Gallery image {len(existing_gallery) + i + 1}",
                    "caption": ""
                })
        
        article.gallery_images = existing_gallery + new_gallery_images
        article.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(article)
        return await article.to_dict_with_relations(db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add gallery images: {str(e)}")




async def remove_gallery_image(db: AsyncSession, article_id: str, image_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(News).where(and_(News.id == article_id, News.state == True)))
        article = result.scalar_one_or_none()
        
        if not article:
            raise HTTPException(status_code=404, detail="News article not found")
        
        if not article.gallery_images:
            raise HTTPException(status_code=404, detail="No gallery images found")
        
        updated_gallery = []
        image_found = False
        
        for image in article.gallery_images:
            if image.get("id") == image_id:
                image_found = True
                if image.get("path"):
                    remove_file(image.get("path"))
            else:
                updated_gallery.append(image)
        
        if not image_found:
            raise HTTPException(status_code=404, detail="Gallery image not found")
        
        article.gallery_images = updated_gallery if updated_gallery else None
        article.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(article)
        return await article.to_dict_with_relations(db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to remove gallery image: {str(e)}")