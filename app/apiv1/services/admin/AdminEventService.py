from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy import and_, desc, or_
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.EventModel import Event
from slugify import slugify
from app.utils.file_upload import save_upload_file, remove_file
from app.utils.advanced_paginator import paginate_query
import math
import os
import uuid
from pathlib import Path

async def get_event_by_id(db: AsyncSession, event_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Event).where(and_(Event.id == event_id, Event.state == True, Event.status == True)))
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        
        return await event.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def create_new_event(db: AsyncSession, event_data: Dict[str, Any], admin_id: str) -> Dict[str, Any]:
    try:
        existing_event = await db.execute(select(Event).where(and_(Event.title == event_data["title"], Event.state == True)))
        if existing_event.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event with this title already exists")
        
        # Generate slug
        slug = slugify(event_data["title"])
        
        # Check if slug already exists
        existing_slug = await db.execute(select(Event).where(and_(Event.slug == slug, Event.state == True)))
        if existing_slug.scalar_one_or_none():
            slug = f"{slug}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        # Parse dates
        try:
            start_date = datetime.fromisoformat(event_data.get("start_date"))
            end_date = datetime.fromisoformat(event_data.get("end_date"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format")

        # Validate date logic
        if end_date < start_date:
            raise HTTPException(status_code=400, detail="End date cannot be before start date")

        # Handle featured image
        image_url = None
        image_path = None
        featured_image = event_data.get("featured_image")
        if featured_image and hasattr(featured_image, 'filename'):
           image_path, image_url = await save_upload_file(featured_image, "events/images")

        # Create new event
        new_event = Event(
            title=event_data["title"],
            slug=slug,
            description=event_data.get("description", ""),
            start_date=start_date,
            end_date=end_date,
            start_time=event_data.get("start_time"),
            end_time=event_data.get("end_time"),
            venue_name=event_data.get("venue_name", ""),
            venue_address=event_data.get("venue_address", ""),
            city=event_data.get("city", ""),
            country=event_data.get("country", ""),
            is_virtual=event_data.get("is_virtual") == "true" if isinstance(event_data.get("is_virtual"), str) else event_data.get("is_virtual", False),
            virtual_link=event_data.get("virtual_link", ""),
            category=event_data.get("category", ""),
            event_type=event_data.get("event_type", "public"),
            currency=event_data.get("currency", "UGX"),
            featured_image_url=image_url,
            featured_image_path=image_path,
            is_featured=event_data.get("is_featured") == "true" if isinstance(event_data.get("is_featured"), str) else event_data.get("is_featured", False),
            is_published=event_data.get("is_published") == "true" if isinstance(event_data.get("is_published"), str) else event_data.get("is_published", False),
            views_count=0,
            shares_count=0,
            created_by=admin_id,
            status=True,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_event)
        await db.commit()
        await db.refresh(new_event)
        
        return await new_event.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create event: {str(e)}")

async def update_event_data(db: AsyncSession, event_id: str, update_data: Dict[str, Any], admin_id: str = None) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Event).where(and_(Event.id == event_id, Event.state == True, Event.status == True)))
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        
        # Check if title already exists (excluding current event)
        if update_data.get("title") and update_data["title"] != event.title:
            existing_title = await db.execute(select(Event).where(and_(Event.title == update_data["title"], Event.id != event_id, Event.state == True)))
            if existing_title.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event with this title already exists")

        # Handle dates if provided
        if update_data.get("start_date"):
            try:
                update_data["start_date"] = datetime.fromisoformat(update_data["start_date"])
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start date format")
        
        if update_data.get("end_date"):
            try:
                update_data["end_date"] = datetime.fromisoformat(update_data["end_date"])
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end date format")

        # Handle featured image
        featured_image = update_data.get("featured_image")
        if featured_image and hasattr(featured_image, 'filename'):
            if event.featured_image_path:
                remove_file(event.featured_image_path)
            image_path, image_url = await save_upload_file(featured_image, "events/images")
            update_data["featured_image_url"] = image_url
            update_data["featured_image_path"] = image_path
        
        # Update event fields
        for key, value in update_data.items():
            if hasattr(event, key) and key != "featured_image":
                if key in ["is_virtual", "is_featured", "is_published"]:
                    setattr(event, key, value == "true" if isinstance(value, str) else value)
                else:
                    setattr(event, key, value)
        
        # Update slug if title changed
        if update_data.get("title"):
            event.slug = slugify(update_data["title"])
        
        event.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(event)
        
        return await event.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update event: {str(e)}")

async def delete_event_by_id(db: AsyncSession, event_id: str) -> bool:
    try:
        result = await db.execute(select(Event).where(and_(Event.id == event_id)))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        await event.delete_with_relations(db)
        return True
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete event: {str(e)}")

async def toggle_event_status(db: AsyncSession, event_id: str, admin_id: str = None) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Event).where(and_(Event.id == event_id, Event.state == True)))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        
        if event.status:
            event.status = False
        else:
            event.status = True
        event.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(event)
        
        return await event.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update event status: {str(e)}")

async def toggle_event_featured(db: AsyncSession, event_id: str, admin_id: str = None) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Event).where(and_(Event.id == event_id, Event.state == True)))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        
        event.is_featured = not event.is_featured
        event.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(event)
        
        return await event.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to toggle featured status: {str(e)}")

async def toggle_event_publish(db: AsyncSession, event_id: str, admin_id: str = None) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Event).where(and_(Event.id == event_id, Event.state == True)))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        
        if event.is_published:
            event.is_published = False
        else:
            event.is_published = True
        event.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(event)
        
        return await event.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update event status: {str(e)}")


async def get_all_events(db: AsyncSession, page: int = 1, per_page: int = 20, search: str = None, category: str = None, status_filter: str = None) -> Dict[str, Any]:
    try:
        query = select(Event).where(Event.state == True)
        
        if search:
            search_pattern = f"%{search}%"
            search_condition = or_(
                Event.title.ilike(search_pattern),
                Event.description.ilike(search_pattern),
                Event.venue_name.ilike(search_pattern),
                Event.city.ilike(search_pattern)
            )
            query = query.where(search_condition)
        
        if category:
            query = query.where(Event.category == category)
        
        if status_filter:
            if status_filter == "published":
                query = query.where(Event.is_published == True)
            elif status_filter == "draft":
                query = query.where(Event.is_published == False)
            elif status_filter == "featured":
                query = query.where(Event.is_featured == True)
        
        query = query.order_by(desc(Event.created_at))
        
        async def transform_event(item, db_session): 
            return await item.to_dict_with_relations(db_session)
            
        return await paginate_query(db=db, query=query, page=page, per_page=per_page, transform_func=transform_event, include_total=True)
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get events: {str(e)}")


async def duplicate_event(db: AsyncSession, event_id: str, admin_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Event).where(and_(Event.id == event_id, Event.state == True)))
        original_event = result.scalar_one_or_none()
        
        if not original_event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        
        event_data = {
            "title": f"Copy of {original_event.title}",
            "description": original_event.description,
            "start_date": original_event.start_date.isoformat() if original_event.start_date else None,
            "end_date": original_event.end_date.isoformat() if original_event.end_date else None,
            "start_time": original_event.start_time,
            "end_time": original_event.end_time,
            "venue_name": original_event.venue_name,
            "venue_address": original_event.venue_address,
            "city": original_event.city,
            "country": original_event.country,
            "is_virtual": False,
            "virtual_link": original_event.virtual_link,
            "category": original_event.category,
            "event_type": original_event.event_type,
            "currency": original_event.currency,
            "is_featured": False,
            "is_published": False
        }
        
        return await create_new_event(db, event_data, admin_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to duplicate event: {str(e)}")

