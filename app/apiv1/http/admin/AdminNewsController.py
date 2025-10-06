from fastapi import APIRouter, Request, status, HTTPException, Depends, Header, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from app.utils.security import get_current_user_details, verify_admin_access
from typing import Optional, Dict, Any, List
from app.apiv1.services.admin.AdminNewsServivce import (
    create_news_article,
    update_news_article,
    get_news_article_by_id,
    get_news_article_by_slug,
    get_news_articles,
    delete_news_article,
    create_news_category,
    update_news_category,
    get_news_categories,
    update_article_engagement,
    get_trending_news,
    update_news_article_image,
    add_gallery_images,
    remove_gallery_image
)

router = APIRouter()
import json


@router.post("/list", status_code=status.HTTP_200_OK)
async def get_articles_list(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        body_data = await request.form()
        
        filters = {
            "page": int(body_data.get("page", 1)),
            "per_page": int(body_data.get("per_page", 100)),
            "is_published": body_data.get("is_published", "").lower() == "true" if body_data.get("is_published") else None,
            "is_featured": body_data.get("is_featured", "").lower() == "true" if body_data.get("is_featured") else None,
            "is_breaking": body_data.get("is_breaking", "").lower() == "true" if body_data.get("is_breaking") else None,
            "category_id": body_data.get("category_id"),
            "station_id": body_data.get("station_id"),
            "author_id": body_data.get("author_id"),
            "search": body_data.get("search"),
            "order_by": body_data.get("order_by")
        }
        
        articles_data = await get_news_articles(db, filters)
        return returnsdata.success(data=articles_data, msg="Articles retrieved successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get articles: {str(e)}", ERROR)

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_article(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        author_id = None
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
           author_id = current_user.get("id")
        else:
            author_id = current_user.get("id")
        if not author_id:
            return returnsdata.error_msg(f"Author ID is required for creating an article {author_id}", ERROR)

        body_data = await request.form()
        
        if not body_data.get("title"):
            return returnsdata.error_msg("Title is required", ERROR)
        
        if not body_data.get("content"):
            return returnsdata.error_msg("Content is required", ERROR)
        
        data = {
            "title": body_data.get("title"),
            "content": body_data.get("content"),
            "summary": body_data.get("summary"),
            "excerpt": body_data.get("excerpt"),
            "meta_title": body_data.get("meta_title"),
            "meta_description": body_data.get("meta_description"),
            "meta_keywords": body_data.get("meta_keywords"),
            "is_published": body_data.get("is_published", "false").lower() == "true",
            "is_featured": body_data.get("is_featured", "false").lower() == "true",
            "is_breaking": body_data.get("is_breaking", "false").lower() == "true",
            "category_id": body_data.get("category_id"),
            "station_id": body_data.get("station_id"),
            "author_id": author_id,
            "source": body_data.get("source"),
            "source_url": body_data.get("source_url"),
            "priority": int(body_data.get("priority", 0)),
           
        }
        
        tags_json = body_data.get("tags")
        if tags_json:
            try:
                data["tags"] = json.loads(tags_json)
            except json.JSONDecodeError:
                return returnsdata.error_msg("Invalid JSON format for tags", ERROR)
        
        featured_image = body_data.get("featured_image")
        gallery_images_files = []
        
        for key, value in body_data.items():
            if key.startswith("gallery_image_"):
                gallery_images_files.append(value)
        
        article_data = await create_news_article(
            db=db,
            data=data,
            author_id=author_id,
            featured_image=featured_image,
            gallery_images=gallery_images_files if gallery_images_files else None
        )
        
        return returnsdata.success(data=article_data, msg="News article created successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create article: {str(e)}", ERROR)




@router.post("/update/{article_id}", status_code=status.HTTP_200_OK)
async def update_article(article_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        body_data = await request.form()
        
        data = {}
        optional_fields = ["title", "content", "summary", "excerpt", "meta_title", "meta_description", "meta_keywords", "category_id", "station_id", "source", "source_url"]
        for field in optional_fields:
            if body_data.get(field) is not None:
                data[field] = body_data.get(field)
        
        if body_data.get("is_published") is not None:
            data["is_published"] = body_data.get("is_published", "false").lower() == "true"
        
        if body_data.get("is_featured") is not None:
            data["is_featured"] = body_data.get("is_featured", "false").lower() == "true"
        
        if body_data.get("is_breaking") is not None:
            data["is_breaking"] = body_data.get("is_breaking", "false").lower() == "true"
        
        if body_data.get("priority") is not None:
            data["priority"] = int(body_data.get("priority", 0))
        
        tags_json = body_data.get("tags")
        if tags_json:
            try:
                data["tags"] = json.loads(tags_json)
            except json.JSONDecodeError:
                return returnsdata.error_msg("Invalid JSON format for tags", ERROR)
        
        featured_image = body_data.get("featured_image")
        gallery_images_files = []
        
        # Handle multiple gallery images
        for key, value in body_data.items():
            if key.startswith("gallery_image_"):
                gallery_images_files.append(value)
        
        article_data = await update_news_article(
            db=db,
            article_id=article_id,
            data=data,
            featured_image=featured_image,
            gallery_images=gallery_images_files if gallery_images_files else None
        )
        
        return returnsdata.success(data=article_data, msg="News article updated successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update article: {str(e)}", ERROR)



@router.post("/get/{article_id}", status_code=status.HTTP_200_OK)
async def get_article_by_id(article_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        article_data = await get_news_article_by_id(db, article_id)
        return returnsdata.success(data=article_data, msg="Article retrieved successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get article: {str(e)}", ERROR)


@router.post("/delete/{article_id}", status_code=status.HTTP_200_OK)
async def delete_article_endpoint(article_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        success = await delete_news_article(db, article_id)
        return returnsdata.success_msg(msg="Article deleted successfully with Precision", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete article: {str(e)}", ERROR)

@router.post("/update_image/{article_id}", status_code=status.HTTP_200_OK)
async def update_article_image(article_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        body_data = await request.form()
        featured_image = body_data.get("featured_image")
        
        if not featured_image:
            return returnsdata.error_msg("Featured image is required", ERROR)
        
        article_data = await update_news_article_image(db, article_id, featured_image)
        return returnsdata.success(data=article_data, msg="Article image updated successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update article image: {str(e)}", ERROR)



@router.post("/add_gallery/{article_id}", status_code=status.HTTP_200_OK)
async def add_article_gallery_images(article_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        body_data = await request.form()
        gallery_images_files = []
        
        # Handle multiple gallery images
        for key, value in body_data.items():
            if key.startswith("gallery_image_"):
                gallery_images_files.append(value)
        
        if not gallery_images_files:
            return returnsdata.error_msg("At least one gallery image is required", ERROR)
        
        article_data = await add_gallery_images(db, article_id, gallery_images_files)
        return returnsdata.success(data=article_data, msg="Gallery images added successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to add gallery images: {str(e)}", ERROR)

@router.post("/remove_gallery/{article_id}/{image_id}", status_code=status.HTTP_200_OK)
async def remove_article_gallery_image(article_id: str, image_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        article_data = await remove_gallery_image(db, article_id, image_id)
        return returnsdata.success(data=article_data, msg="Gallery image removed successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to remove gallery image: {str(e)}", ERROR)


@router.post("/slug/{slug}", status_code=status.HTTP_200_OK)
async def get_article_by_slug(slug: str, request: Request, db: AsyncSession = Depends(get_database)):
    try:
        article_data = await get_news_article_by_slug(db, slug)
        return returnsdata.success(data=article_data, msg="Article retrieved successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get article: {str(e)}", ERROR)







@router.post("/public/list", status_code=status.HTTP_200_OK)
async def get_public_articles_list(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        body_data = await request.form()
        
        filters = {
            "page": int(body_data.get("page", 1)),
            "per_page": int(body_data.get("per_page", 20)),
            "is_published": True,  # Only published articles for public
            "is_featured": body_data.get("is_featured", "").lower() == "true" if body_data.get("is_featured") else None,
            "is_breaking": body_data.get("is_breaking", "").lower() == "true" if body_data.get("is_breaking") else None,
            "category_id": body_data.get("category_id"),
            "station_id": body_data.get("station_id"),
            "search": body_data.get("search"),
            "order_by": body_data.get("order_by")
        }
        
        articles_data = await get_news_articles(db, filters)
        return returnsdata.success(data=articles_data, msg="Articles retrieved successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get articles: {str(e)}", ERROR)






@router.post("/engagement/{article_id}", status_code=status.HTTP_200_OK)
async def update_engagement(article_id: str, request: Request, db: AsyncSession = Depends(get_database)):
    try:
        body_data = await request.form()
        action = body_data.get("action")
        
        if action not in ["like", "share", "view"]:
            return returnsdata.error_msg("Invalid action. Must be 'like', 'share', or 'view'", ERROR)
        
        article_data = await update_article_engagement(db, article_id, action)
        return returnsdata.success(data=article_data, msg=f"Article {action} updated successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update engagement: {str(e)}", ERROR)



@router.post("/trending", status_code=status.HTTP_200_OK)
async def get_trending_articles(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        body_data = await request.form()
        limit = int(body_data.get("limit", 10))
        
        articles_data = await get_trending_news(db, limit)
        return returnsdata.success(data=articles_data, msg="Trending articles retrieved successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get trending articles: {str(e)}", ERROR)






# Category endpoints
@router.post("/categories/create", status_code=status.HTTP_201_CREATED)
async def create_category(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        body_data = await request.form()
        
        if not body_data.get("name"):
            return returnsdata.error_msg("Category name is required", ERROR)
        
        data = {
            "name": body_data.get("name"),
            "description": body_data.get("description"),
            "color": body_data.get("color"),
            "icon": body_data.get("icon"),
            "parent_id": body_data.get("parent_id"),
            "sort_order": int(body_data.get("sort_order", 0))
        }
        
        category_data = await create_news_category(db, data)
        return returnsdata.success(data=category_data, msg="News category created successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create category: {str(e)}", ERROR)


@router.post("/categories/list", status_code=status.HTTP_200_OK)
async def get_categories_list(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        categories_data = await get_news_categories(db)
        return returnsdata.success(data=categories_data, msg="Categories retrieved successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get categories: {str(e)}", ERROR)

@router.post("/categories/update/{category_id}", status_code=status.HTTP_201_CREATED)
async def update_category(category_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        body_data = await request.form()
        
        if not body_data.get("name"):
            return returnsdata.error_msg("Category name is required", ERROR)
        
        data = {
            "name": body_data.get("name"),
            "description": body_data.get("description"),
            "color": body_data.get("color"),
            "icon": body_data.get("icon"),
            "parent_id": body_data.get("parent_id"),
            "sort_order": int(body_data.get("sort_order", 0))
        }
        
        category_data = await update_news_category(db, category_id, data)
        return returnsdata.success(data=category_data, msg="News category updated successfully", status=SUCCESS)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update category: {str(e)}", ERROR)