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
from app.apiv1.services.admin.AdminRadioProgramsService import (
    get_programs,
    get_program_by_id,
    create_new_program,
    update_program_data,
    delete_program_by_id,
    toggle_program_status,
    update_program_image
)

router = APIRouter()


@router.post("", status_code=status.HTTP_200_OK)
async def fetch_programs(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 100))
        programs_results = await get_programs(db, page=page, per_page=per_page)
        programs = [await program.to_dict_with_relations(db) for program in programs_results]
        return paginate_data(jsonable_encoder(programs), page=page, per_page=per_page)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch programs: {str(e)}", ERROR)


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_program(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
   try:
       # Convert JSONResponse to dict if needed
       if hasattr(current_user, 'status_code'):
           import json
           current_user = json.loads(current_user.body.decode())
           
       body_data = await request.form()
       data = dict(body_data)
       title = data.get("title")
       station_id = data.get("station_id")
       
       if not title:
           return returnsdata.error_msg("Program title is required", ERROR)
       if not station_id:
           return returnsdata.error_msg("Station is required", ERROR)
               
       program_data = {
           "title": title,
           "station_id": station_id,
           "duration": int(data.get("duration", 60)),
           "studio": data.get("studio", "A"),
           "type": data.get("type", "live_show"),
           "description": data.get("description", ""),
           "status": data.get("status", "active"),
       }
       
       # Handle host_ids as JSON array
       host_ids = data.get("host_ids")
       if host_ids:
           import json
           program_data["host_ids"] = json.loads(host_ids) if isinstance(host_ids, str) else host_ids
       else:
           program_data["host_ids"] = []
       
       # Handle image file
       image_file = data.get("image")
       upload_file = None
       if image_file and hasattr(image_file, 'filename'):
           upload_file = image_file
       elif image_file and isinstance(image_file, str) and image_file.startswith("data:image"):
           upload_file = base64_to_upload_file(image_file)

       user_id = current_user.get('id')
       new_program = await create_new_program(db, program_data, upload_file, user_id)
       return returnsdata.success(data=await new_program.to_dict_with_relations(db), msg="Program created successfully", status=SUCCESS)
   except Exception as e:
       return returnsdata.error_msg(f"Failed to create program: {str(e)}", ERROR)


@router.post("/{program_id}", status_code=status.HTTP_200_OK)
async def fetch_program(program_id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        program_data = await get_program_by_id(db, program_id)
        return returnsdata.success(data=program_data, msg="Program fetched successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch program: {str(e)}", ERROR)


@router.post("/update/{program_id}", status_code=status.HTTP_200_OK)
async def update_program(program_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        if hasattr(current_user, 'status_code'):
           import json
           current_user = json.loads(current_user.body.decode())
           
        body_data = await request.form()
        data = dict(body_data)
        title = data.get("title")
        station_id = data.get("station_id")

        if not title:
            return returnsdata.error_msg("Program title is required", ERROR)
        if not station_id:
            return returnsdata.error_msg("Station is required", ERROR)

        program_data = {
            "title": title,
            "station_id": station_id,
            "duration": int(data.get("duration", 60)),
            "studio": data.get("studio", "A"),
            "type": data.get("type", "live_show"),
            "description": data.get("description", ""),
            "status": data.get("status", "active"),
        }
        
        # Handle host_ids as JSON array
        host_ids = data.get("host_ids")
        if host_ids:
            import json
            program_data["host_ids"] = json.loads(host_ids) if isinstance(host_ids, str) else host_ids
        else:
            program_data["host_ids"] = []

        # Handle image file
        image_file = data.get("image")
        upload_file = None
        if image_file and hasattr(image_file, 'filename'):   
            upload_file = image_file
        elif image_file and isinstance(image_file, str) and image_file.startswith("data:image"):
            upload_file = base64_to_upload_file(image_file)

        user_id = current_user.get('id')
        updated_program = await update_program_data(db, program_id, program_data, upload_file, user_id)

        return returnsdata.success(data=await updated_program.to_dict_with_relations(db), msg="Program updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update program: {str(e)}", ERROR)


@router.post("/delete/{program_id}", status_code=status.HTTP_200_OK)
async def delete_program(program_id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        await delete_program_by_id(db, program_id)
        return returnsdata.success_msg(msg="Program deleted successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete program: {str(e)}", ERROR)


@router.post("/status/{program_id}", status_code=status.HTTP_200_OK)
async def toggle_program_status_endpoint(program_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        status_value = body_data.get("status")
        
        # Handle both string and boolean values
        if isinstance(status_value, str):
            status_value = status_value.lower() in ["true", "active"]
        
        updated_program = await toggle_program_status(db, program_id, status_value)
        return returnsdata.success(data=await updated_program.to_dict_with_relations(db), msg="Program status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update program status: {str(e)}", ERROR)


@router.post("/image/{program_id}", status_code=status.HTTP_200_OK)
async def update_program_image_endpoint(program_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        image = body_data.get("image")
        
        if not image:
            return returnsdata.error_msg("Image file is required", ERROR)
        
        updated_program = await update_program_image(db, program_id, image)
        return returnsdata.success(data=await updated_program.to_dict_with_relations(db), msg="Program image updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update program image: {str(e)}", ERROR)