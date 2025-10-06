from fastapi import APIRouter, Request, status, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from typing import Optional, Dict, Any
from app.utils.security import get_current_user_details
from app.utils.pagination import paginate_data
from fastapi.encoders import jsonable_encoder
from app.apiv1.services.admin.AdminAdvertService import (
    get_adverts,
    get_advert_by_id,
    create_new_advert,
    update_advert_data,
    delete_advert_by_id,
    update_advert_status
)

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
async def fetch_adverts(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        page = int(request.query_params.get("page", 1))
        per_page = int(body_data.get("per_page", 1000))
        station_id = body_data.get("station_id")
        status_filter = body_data.get("status")
        
        filters = {}
        if station_id:
            filters["station_id"] = station_id
        if status_filter:
            filters["status"] = status_filter
            
        adverts_results = await get_adverts(db, page=page, per_page=per_page, filters=filters)
        adverts_data = [await advert.to_dict_with_relations(db) for advert in adverts_results]
        return paginate_data(jsonable_encoder(adverts_data), page=page, per_page=per_page)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch adverts: {str(e)}", ERROR)

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_advert(
    request: Request,
    db: AsyncSession = Depends(get_database),
    current_user = Depends(get_current_user_details),
    image: Optional[UploadFile] = File(None)
):
    try:
        body_data = await request.form()
        title = body_data.get("title")
        description = body_data.get("description")
        station_id = body_data.get("station_id")
        target_url = body_data.get("target_url")
        button_title = body_data.get("button_title")
        status_value = body_data.get("status", True)
        
        if not title:
            return returnsdata.error_msg("Advert title is required", ERROR)
        if not description:
            return returnsdata.error_msg("Advert description is required", ERROR)
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        
        advert_data = {
            "title": title,
            "description": description,
            "station_id": station_id,
            "target_url": target_url,
            "button_title": button_title,
            "status": status_value
        }
        
        new_advert = await create_new_advert(db, advert_data, current_user.get('id'), image)
        advert_dict = await new_advert.to_dict_with_relations(db)
        return returnsdata.success(data=advert_dict, msg="Advert created successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create advert: {str(e)}", ERROR)

@router.post("/{id}", status_code=status.HTTP_200_OK)
async def fetch_advert(id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        advert_data = await get_advert_by_id(db, id)
        return returnsdata.success(data=advert_data, msg="Advert fetched successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch advert: {str(e)}", ERROR)

@router.post("/update/{id}", status_code=status.HTTP_200_OK)
async def update_advert(
    id: str,
    request: Request,
    db: AsyncSession = Depends(get_database),
    current_user = Depends(get_current_user_details),
    image: Optional[UploadFile] = File(None)
):
    try:
        body_data = await request.form()
        title = body_data.get("title")
        description = body_data.get("description")
        station_id = body_data.get("station_id")
        target_url = body_data.get("target_url")
        button_title = body_data.get("button_title")
        status_value = body_data.get("status")
        
        update_data = {}
        if title:
            update_data["title"] = title
        if description:
            update_data["description"] = description
        if station_id:
            update_data["station_id"] = station_id
        if target_url is not None:  # Allow empty string
            update_data["target_url"] = target_url
        if button_title is not None:  # Allow empty string
            update_data["button_title"] = button_title
        if status_value is not None:
            update_data["status"] = status_value
            
        if not update_data and not image:
            return returnsdata.error_msg("No data provided for update", ERROR)
        
        updated_advert = await update_advert_data(db, id, update_data, image)
        return returnsdata.success(data=updated_advert, msg="Advert updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update advert: {str(e)}", ERROR)

@router.post("/status/{id}", status_code=status.HTTP_200_OK)
async def update_advert_status_route(id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        status_value = body_data.get("status")
        
        if status_value is None:
            return returnsdata.error_msg("Advert status is required", ERROR)
        
        updated_advert = await update_advert_status(db, id, {"status": status_value})
        return returnsdata.success(data=updated_advert, msg="Advert status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update advert status: {str(e)}", ERROR)

@router.post("/delete/{id}", status_code=status.HTTP_200_OK)
async def delete_advert(id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        await delete_advert_by_id(db, id)
        return returnsdata.success_msg(msg="Advert deleted successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete advert: {str(e)}", ERROR)