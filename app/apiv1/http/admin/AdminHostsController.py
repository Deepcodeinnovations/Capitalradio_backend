from fastapi import APIRouter, Request, status, HTTPException, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.pagination import paginate_data
from app.utils.returns_data import returnsdata
from app.utils.file_upload import base64_to_upload_file
from typing import Optional, Dict, Any
from fastapi.encoders import jsonable_encoder
from app.utils.security import get_current_user_details
from app.apiv1.services.admin.AdminHostsService import (
    get_hosts,
    get_host_by_id,
    create_new_host,
    update_host_data,
    delete_host_by_id,
    toggle_host_status,
    update_host_profile_image
)

router = APIRouter()


@router.post("", status_code=status.HTTP_200_OK)
async def fetch_hosts(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 100))
        hosts_results = await get_hosts(db, page=page, per_page=per_page)
        hosts= [await host.to_dict_with_relations(db) for host in hosts_results]
        return paginate_data(jsonable_encoder(hosts), page=page, per_page=per_page)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch hosts: {str(e)}", ERROR)


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_host(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
   try:
       # Convert JSONResponse to dict if needed
       if hasattr(current_user, 'status_code'):
           import json
           current_user = json.loads(current_user.body.decode())
           
       body_data = await request.form()
       data = dict(body_data)
       name = data.get("name")
       if not name:
           return returnsdata.error_msg("Host name is required", ERROR)
               
       host_data = {
           "name": name,
           "role": data.get("role", ""),
           "email": data.get("email", ""),
           "phone": data.get("phone", ""),
           "bio": data.get("bio", ""),
           "social_media": data.get("social_media", ""),
           "experience_years": int(data.get("experience_years", 0)),
           "status": data.get("status") == "true",
           "on_air_status": data.get("on_air_status") == "true",
       }
       image_file = data.get("image_url")
       upload_file = None
       if image_file and hasattr(image_file, 'filename'):
           upload_file = image_file
       elif image_file and image_file.startswith("data:image"):
           upload_file = base64_to_upload_file(image_file)

       user_id = current_user.get('id')
       await create_new_host(db, host_data, upload_file, user_id)
       return await fetch_hosts(request, db, current_user)
   except Exception as e:
       return returnsdata.error_msg(f"Failed to create host: {str(e)}", ERROR)


@router.post("/{host_id}", status_code=status.HTTP_200_OK)
async def fetch_host(host_id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        host_data = await get_host_by_id(db, host_id)
        return returnsdata.success(data=host_data, msg="Host fetched successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch host: {str(e)}", ERROR)





@router.post("/update/{host_id}", status_code=status.HTTP_200_OK)
async def update_host(host_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        if hasattr(current_user, 'status_code'):
           import json
           current_user = json.loads(current_user.body.decode())
        body_data = await request.form()
        data = dict(body_data)
        name = data.get("name")

        if not name:
         return returnsdata.error_msg("Host name is required", ERROR)

        host_data = {
            "name": name,
            "role": data.get("role", ""),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "bio": data.get("bio", ""),
            "social_media": data.get("social_media", ""),
            "experience_years": int(data.get("experience_years", 0)),
            "status": data.get("status") == "true",
            "on_air_status": data.get("on_air_status") == "true",
        }

        image_url = data.get("image_url")
        upload_file = None
        if image_url and hasattr(image_url, 'filename'):   
            upload_file = image_url
        elif image_url and image_url.startswith("data:image"):
            upload_file = base64_to_upload_file(image_url)

        user_id = current_user.get('id')
        await update_host_data(db, host_id, host_data, upload_file, user_id)

        return await fetch_host(host_id, db, current_user)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update host: {str(e)}", ERROR)


@router.post("/delete/{host_id}", status_code=status.HTTP_200_OK)
async def delete_host(host_id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        await delete_host_by_id(db, host_id)
        return returnsdata.success_msg(msg="Host deleted successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete host: {str(e)}", ERROR)



@router.post("/status/{host_id}", status_code=status.HTTP_200_OK)
async def toggle_host_status_endpoint(host_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        status_value = body_data.get("status") == "true"
        
        updated_host = await toggle_host_status(db, host_id, status_value)
        return returnsdata.success(data=updated_host, msg="Host status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update host status: {str(e)}", ERROR)



@router.post("/profile_image/{host_id}", status_code=status.HTTP_200_OK)
async def update_host_profile_image_endpoint(host_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        image = body_data.get("image")
        
        if not image:
            return returnsdata.error_msg("Image file is required", ERROR)
        
        updated_host = await update_host_profile_image(db, host_id, image)
        return returnsdata.success(data=updated_host, msg="Profile image updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update profile image: {str(e)}", ERROR)