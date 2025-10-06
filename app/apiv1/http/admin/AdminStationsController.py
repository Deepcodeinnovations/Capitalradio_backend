from fastapi import APIRouter, Request, status, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from typing import Optional, Dict, Any
from app.utils.security import get_current_user_details
from app.apiv1.services.admin.AdminStationService import (
    get_stations,
    get_station_by_id,
    create_new_station,
    update_station_data,
    delete_station_by_id,
    toggle_station_streaming_status,
    toggle_station_radio_access
)

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
async def fetch_stations(request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        page = int(request.query_params.get("page", 1))
        per_page = int(body_data.get("per_page", 10))
        stations_results = await get_stations(db, page=page, per_page=per_page)
        stations_data = [await station.to_dict_with_relations(db) for station in stations_results]
        return returnsdata.success(data=stations_data, msg="Stations fetched successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch stations: {str(e)}", ERROR)


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_station(request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        name = body_data.get("name")
        frequency = body_data.get("frequency")
        
        if not name:
            return returnsdata.error_msg("Station name is required", ERROR)
        if not frequency:
            return returnsdata.error_msg("Station frequency is required", ERROR)
        
        station_data = {
            "name": name,
            "frequency": frequency,
            "tagline": body_data.get("tagline", ""),
            "access_link": body_data.get("access_link", ""),
            "streaming_link": body_data.get("streaming_link", ""),
            "about": body_data.get("about", ""),
            "streaming_status": body_data.get("streaming_status", "offline"),
            "radio_access_status": body_data.get("radio_access_status") == "true"
        }
        
        await create_new_station(db, station_data, current_user.get('id'))
        return await fetch_stations(request,db,current_user)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create station: {str(e)}", ERROR)


@router.post("/{station_id}", status_code=status.HTTP_200_OK)
async def fetch_station(station_id: str,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        station_data = await get_station_by_id(db, station_id)
        return returnsdata.success(data=station_data, msg="Station fetched successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch station: {str(e)}", ERROR)






@router.post("/update/{station_id}", status_code=status.HTTP_200_OK)
async def update_station(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        name = body_data.get("name")
        frequency = body_data.get("frequency")
        
        if not name:
            return returnsdata.error_msg("Station name is required", ERROR)
        if not frequency:
            return returnsdata.error_msg("Station frequency is required", ERROR)
        
        update_data = {
            "name": name,
            "frequency": frequency,
            "tagline": body_data.get("tagline", ""),
            "access_link": body_data.get("access_link", ""),
            "streaming_link": body_data.get("streaming_link", ""),
            "about": body_data.get("about", ""),
            "streaming_status": body_data.get("streaming_status", "offline"),
            "radio_access_status": body_data.get("radio_access_status") == "true"
        }
        
        updated_station = await update_station_data(db, station_id, update_data)
        return returnsdata.success(data=updated_station, msg="Station updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update station: {str(e)}", ERROR)



@router.post("/delete/{station_id}", status_code=status.HTTP_200_OK)
async def delete_station(station_id: str,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        await delete_station_by_id(db, station_id)
        return returnsdata.success_msg(msg="Station deleted successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete station: {str(e)}", ERROR)



@router.post("/streaming_status/{station_id}", status_code=status.HTTP_200_OK)
async def toggle_streaming_status(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        streaming_status = body_data.get("streaming_status")
        
        if not streaming_status:
            return returnsdata.error_msg("Streaming status is required", ERROR)
        
        updated_station = await toggle_station_streaming_status(db, station_id, streaming_status)
        return returnsdata.success(data=updated_station, msg="Streaming status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update streaming status: {str(e)}", ERROR)

@router.post("/radio_access/{station_id}", status_code=status.HTTP_200_OK)
async def toggle_radio_access(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        radio_access_status = body_data.get("radio_access_status") == "true"
        updated_station = await toggle_station_radio_access(db, station_id, radio_access_status)
        return returnsdata.success(data=updated_station, msg="Radio access status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update radio access status: {str(e)}", ERROR)