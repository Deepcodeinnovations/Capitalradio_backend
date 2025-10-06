from fastapi import APIRouter, Request, status, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from typing import Optional, Dict, Any
from app.utils.security import get_current_user_details, decode_and_validate_token, extract_token_from_header
from app.apiv1.services.user.UserAuthService import authenticate_or_create_open_user, update_user_information, get_user_by_id
from app.apiv1.services.user.UserStationService import get_station_by_initial_access_link, get_station_by_access_link
import json

router = APIRouter()


#admin
@router.post("/login",  status_code=status.HTTP_201_CREATED)
async def login_user(request: Request,  db: AsyncSession = Depends(get_database)):
    try:
        body_data = await request.form()
        device_fingerprint = body_data.get("device_fingerprint")
        station_access_link = body_data.get("access_link")
        station_data = await get_station_by_initial_access_link(db, station_access_link)
        if not station_data:
            return  returnsdata.error_msg("Station not found", ERROR)
        station_id = station_data.get("id")
        if not device_fingerprint:
            return  returnsdata.error_msg("Device fingerprint is required", ERROR)
        if not station_id:
            return  returnsdata.error_msg("Station ID is required", ERROR)
        
        user_data = await authenticate_or_create_open_user(db, device_fingerprint, station_id)
        
        return  returnsdata.success(data=user_data,msg="Login successful",status="Success")
    except Exception as e:
        return returnsdata.error_msg( f"Login failed: {str(e)}", ERROR )




@router.post("/update_profile",  status_code=status.HTTP_201_CREATED)
async def update_user_information_endpoint(request: Request,  db: AsyncSession = Depends(get_database), authuser = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        name = body_data.get("name")
        email = body_data.get("email")
        user_id = authuser.get("id")
        if not name or not email or not user_id:
            return  returnsdata.error_msg("Name, email and user id are required", ERROR)
        user_data = await update_user_information(db, name, email, user_id)
        return  returnsdata.success(data=user_data,msg="User information updated successfully",status="Success")
    except Exception as e:
        return returnsdata.error_msg( f"Update profile failed: {str(e)}", ERROR )