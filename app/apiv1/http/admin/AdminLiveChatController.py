from fastapi import APIRouter, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from app.utils.security import get_current_user_details
from app.apiv1.services.admin.AdminLiveChatService import get_station_livechat_messages, create_livechat_message, delete_station_livechat_message

import json

router = APIRouter()

@router.post("/livechatmessages",  status_code=status.HTTP_201_CREATED)
async def get_station_livechat_messages_endpoint(request: Request, db: AsyncSession = Depends(get_database), authuser = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        limit = form_data.get("limit",200)
        offset = form_data.get("offset",0)
        data = await get_station_livechat_messages(db, limit, offset)
        return  returnsdata.success(data=data,msg="Station livechat message retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Logout failed: {str(e)}", ERROR )

@router.post("/create",  status_code=status.HTTP_201_CREATED)
async def create_station_livechat_message(request: Request, db: AsyncSession = Depends(get_database), authuser = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        station_id = form_data.get("station_id")
        message = form_data.get("message")
        user_id = authuser.get("id")
        message_type = form_data.get("message_type",'User')
        metadata = form_data.get("metadata")
        if not station_id or not message:
            return  returnsdata.error_msg("Station ID and message are required", ERROR)
        data = await create_livechat_message(db, station_id, message, user_id, message_type, metadata)
        return  returnsdata.success(data=data,msg="Station livechat message created successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Logout failed: {str(e)}", ERROR )


@router.post("/delete",  status_code=status.HTTP_201_CREATED)
async def delete_station_livechat_message_endpoint(request: Request, db: AsyncSession = Depends(get_database), authuser = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        message_id = form_data.get("message_id")
        if not message_id:
            return  returnsdata.error_msg("Message ID is required", ERROR)
        await delete_station_livechat_message(db, message_id)
        return  returnsdata.success_msg(msg="Station livechat message deleted successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Logout failed: {str(e)}", ERROR )