from fastapi import APIRouter, Request, status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.pagination import paginate_data
from app.utils.returns_data import returnsdata
from app.utils.file_upload import base64_to_upload_file
from typing import Optional, Dict, Any
from fastapi.encoders import jsonable_encoder
from app.utils.security import get_current_user_details
from app.apiv1.services.admin.AdminEventService import (
    create_new_event,
    get_all_events,
    get_event_by_id,
    update_event_data,
    delete_event_by_id,
    toggle_event_status,
    toggle_event_featured,
    toggle_event_publish,
    duplicate_event
)

router = APIRouter()


@router.post("", status_code=status.HTTP_200_OK)
async def fetch_events(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 1000))
        search = request.query_params.get("search")
        category = request.query_params.get("category")
        status_filter = request.query_params.get("status_filter")
        
        events_data = await get_all_events(db=db, page=page, per_page=per_page, search=search, category=category, status_filter=status_filter)
        return returnsdata.success(data=events_data, msg="Events fetched successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch events: {str(e)}", ERROR)


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_new_event_endpoint(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        if hasattr(current_user, 'status_code'):
            import json
            current_user = json.loads(current_user.body.decode())
            
        body_data = await request.form()
        data = dict(body_data)
        
        title = data.get("title")
        if not title:
            return returnsdata.error_msg("Event title is required", ERROR)
            
        user_id = current_user.get('id')
        await create_new_event(db, data, user_id)
        return await fetch_events(request, db, current_user)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create event: {str(e)}", ERROR)


@router.post("/details/{event_id}", status_code=status.HTTP_200_OK)
async def fetch_event(event_id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        event_data = await get_event_by_id(db, event_id)
        return returnsdata.success(data=event_data, msg="Event fetched successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch event: {str(e)}", ERROR)


@router.post("/update/{event_id}", status_code=status.HTTP_200_OK)
async def update_existing_event_endpoint(event_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        if hasattr(current_user, 'status_code'):
            import json
            current_user = json.loads(current_user.body.decode())
            
        body_data = await request.form()
        data = dict(body_data)
        title = data.get("title")
        if not title:
            return returnsdata.error_msg("Event title is required", ERROR)
        user_id = current_user.get('id')
        await update_event_data(db, event_id, data, user_id)
        return await fetch_event(event_id, db, current_user)
        
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update event: {str(e)}", ERROR)


@router.post("/delete/{event_id}", status_code=status.HTTP_200_OK)
async def delete_existing_event(event_id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        await delete_event_by_id(db, event_id)
        return returnsdata.success_msg(msg="Event deleted successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete event: {str(e)}", ERROR)


@router.post("/status/{event_id}", status_code=status.HTTP_200_OK)
async def toggle_event_status_endpoint(event_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        user_id = current_user.get('id')
        updated_event = await toggle_event_status(db, event_id, user_id)
        return returnsdata.success(data=updated_event, msg="Event status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update event status: {str(e)}", ERROR)


@router.post("/featured/{event_id}", status_code=status.HTTP_200_OK)
async def toggle_event_featured_endpoint(event_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        user_id = current_user.get('id')
        updated_event = await toggle_event_featured(db, event_id, user_id)
        return returnsdata.success(data=updated_event, msg="Event featured status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to toggle featured status: {str(e)}", ERROR)

@router.post("/publish/{event_id}", status_code=status.HTTP_200_OK)
async def toggle_event_publish_endpoint(event_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        user_id = current_user.get('id')
        updated_event = await toggle_event_publish(db, event_id, user_id)
        return returnsdata.success(data=updated_event, msg="Event publish status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to toggle featured status: {str(e)}", ERROR)

@router.post("/duplicate/{event_id}", status_code=status.HTTP_201_CREATED)
async def duplicate_existing_event(event_id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        user_id = current_user.get('id')
        duplicated_event = await duplicate_event(db, event_id, user_id)
        return returnsdata.success(data=duplicated_event, msg="Event duplicated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to duplicate event: {str(e)}", ERROR)


