from fastapi import APIRouter, Request, status, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from typing import Optional, Dict, Any
from app.utils.security import get_current_user_details, decode_and_validate_token, extract_token_from_header
from app.apiv1.services.user.UserStationService import get_station_by_access_link, create_livechat_message, get_station_livechat_messages, delete_station_livechat_message, get_user_hosts_by_station, get_user_radio_sessions, get_user_radio_events
from app.apiv1.services.user.UserNewsService import get_user_news, get_user_news_breaking, get_news_article_by_slug
from app.apiv1.services.user.UserForumService import get_user_forums, get_forum_by_slug, get_forum_comments, create_forum_comment, delete_forum_comment
from app.apiv1.services.user.UserAdvertService import get_user_adverts_by_station
import json

router = APIRouter()


@router.post("/station",  status_code=status.HTTP_201_CREATED)
async def get_access_station(request: Request, db: AsyncSession = Depends(get_database), authuser = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        access_link = form_data.get("access_link")
        user_id = authuser.get("id")
        print("======================================================================================================")
        print(user_id)
        if not access_link:
            return  returnsdata.error_msg("Station Access Link is required", ERROR)
        data = await get_station_by_access_link(db, access_link, user_id)
        return  returnsdata.success(data=data,msg="Station data retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Station data retrieval failed: {str(e)}", ERROR )


##news
@router.post("/news", status_code=status.HTTP_201_CREATED)
async def get_user_news_endpoint(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        per_page = int(form_data.get("per_page", 1))
        page = int(form_data.get("page", 1))
        station_id = form_data.get("station_id")
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        data = await get_user_news(db, station_id=station_id, filters=form_data, per_page=per_page, page=page)
        return returnsdata.success(data=data, msg="News retrieved successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to retrieve news: {str(e)}", ERROR)

@router.post("/adverts", status_code=status.HTTP_201_CREATED)
async def get_user_adverts_endpoint(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        per_page = int(form_data.get("per_page", 10))
        page = int(form_data.get("page", 1))
        station_id = form_data.get("station_id")
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        data = await get_user_adverts_by_station(db, station_id=station_id, per_page=per_page, page=page)
        return data
    except Exception as e:
        return returnsdata.error_msg(f"Failed to retrieve adverts: {str(e)}", ERROR)

@router.post("/hosts", status_code=status.HTTP_201_CREATED)
async def get_user_hosts_endpoint(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        per_page = int(form_data.get("per_page", 10))
        page = int(form_data.get("page", 1))
        station_id = form_data.get("station_id")
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        data = await get_user_hosts_by_station(db, station_id=station_id, per_page=per_page, page=page)
        return data
    except Exception as e:
        return returnsdata.error_msg(f"Failed to retrieve hosts: {str(e)}", ERROR)

@router.post("/radio_sessions")
async def get_radio_sessions_endpoint(request: Request,db: AsyncSession = Depends(get_database)):
    try:
        data = dict(await request.form())
        page = int(data.get("page", 1))
        per_page = int(data.get("per_page", 10))
        station_id = data.get("station_id")
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        radio_sessions = await get_user_radio_sessions(db,station_id=station_id, data=data, page=page, per_page=per_page)
        return returnsdata.success(data=radio_sessions, msg="Radio sessions retrieved successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get radio sessions: {str(e)}", ERROR)

@router.post("/events")
async def get_radio_events_endpoint(request: Request,db: AsyncSession = Depends(get_database)):
    try:
        data = dict(await request.form())
        page = int(data.get("page", 1))
        per_page = int(data.get("per_page", 50))
        radio_sessions = await get_user_radio_events(db,data=data, page=page, per_page=per_page)
        return returnsdata.success(data=radio_sessions, msg="Radio sessions retrieved successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get radio sessions: {str(e)}", ERROR)

##news breaking
@router.post("/news/breaking",  status_code=status.HTTP_201_CREATED)
async def get_user_news_breaking_endpoint(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        station_id = form_data.get("station_id")
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        limit = int(form_data.get("limit",10))
        offset = int(form_data.get("offset",0))
        data = await get_user_news_breaking(db, station_id=station_id, limit=limit, offset=offset)
        return  returnsdata.success(data=data,msg="News retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Logout failed: {str(e)}", ERROR )


@router.post("/news/details",  status_code=status.HTTP_201_CREATED)
async def get_user_news_details_endpoint(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        slug = form_data.get("slug")
        if not slug:
            return  returnsdata.error_msg("News slug is required", ERROR)
        data = await get_news_article_by_slug(db, slug)
        return  returnsdata.success(data=data,msg="News retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Logout failed: {str(e)}", ERROR )


@router.post("/station/livechat",  status_code=status.HTTP_201_CREATED)
async def get_station_livechat_messages_endpoint(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        station_id = form_data.get("station_id")
        limit = int(form_data.get("limit",200))
        offset = int(form_data.get("offset",0))
        if not station_id:
            return  returnsdata.error_msg("Station ID is required", ERROR)
        data = await get_station_livechat_messages(db, station_id, limit, offset)
        return  returnsdata.success(data=data,msg="Station livechat message retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Logout failed: {str(e)}", ERROR )

@router.post("/station/livechat/create",  status_code=status.HTTP_201_CREATED)
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


@router.post("/station/livechat/delete",  status_code=status.HTTP_201_CREATED)
async def delete_station_livechat_message(request: Request, db: AsyncSession = Depends(get_database), authuser = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        message_id = form_data.get("message_id")
        if not message_id:
            return  returnsdata.error_msg("Message ID is required", ERROR)
        data = await delete_station_livechat_message(db, message_id)
        return  returnsdata.success(data=data,msg="Station livechat message deleted successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Logout failed: {str(e)}", ERROR )




##forums
@router.post("/forums", status_code=status.HTTP_201_CREATED)
async def get_user_forums_endpoint(request: Request, db: AsyncSession = Depends(get_database)):
    try:
        form_data = await request.form()
        per_page = int(form_data.get("per_page", 1))
        page = int(form_data.get("page", 1))
        station_id = form_data.get("station_id")
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        data = await get_user_forums(db, station_id, filters=form_data, per_page=per_page, page=page)
        return returnsdata.success(data=data, msg="News retrieved successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to retrieve news: {str(e)}", ERROR)



@router.post("/forums/details",  status_code=status.HTTP_201_CREATED)
async def get_user_forums_details_endpoint(request: Request, db: AsyncSession = Depends(get_database), authuser = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        slug = form_data.get("slug")
        if not slug:
            return  returnsdata.error_msg("News slug is required", ERROR)
        data = await get_forum_by_slug(db, slug, authuser.get("id"))
        return  returnsdata.success(data=data,msg="News retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg( f"Logout failed: {str(e)}", ERROR )



@router.post("/forums/comments", status_code=status.HTTP_201_CREATED)
async def get_forum_comments_endpoint(request: Request, db: AsyncSession = Depends(get_database), authuser = Depends(get_current_user_details)):
    try:
        form_data = await request.form()
        forum_id = form_data.get("forum_id")
        per_page = int(form_data.get("per_page", 10))
        page = int(form_data.get("page", 1))
        
        if not forum_id:
            return returnsdata.error_msg("Forum ID is required", ERROR)
            
        data = await get_forum_comments(db, forum_id, page=page, per_page=per_page)
        return returnsdata.success(data=data, msg="Comments retrieved successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to retrieve comments: {str(e)}", ERROR)



@router.post("/forums/comments/create", status_code=status.HTTP_201_CREATED)
async def create_comment(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        content = body_data.get("content")
        status_value = body_data.get("status", True)
        forum_id = body_data.get("forum_id")
        reply_to = body_data.get("reply_to")
        
        if not forum_id:
            return returnsdata.error_msg("Forum ID is required", ERROR)
        if reply_to:
            comment_data = {
                "content": content,
                "status": status_value,
                "forum_id": forum_id,
                "reply_to": reply_to
            }
        else:
            comment_data = {
                "content": content,
                "status": status_value,
                "forum_id": forum_id
            }
        
        await create_forum_comment(db, comment_data, current_user.get('id'))
        return await get_forum_comments_endpoint(request, db, current_user)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create comment: {str(e)}", ERROR)


@router.post("/forums/comments/delete", status_code=status.HTTP_201_CREATED)
async def delete_comment(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        comment_id = body_data.get("comment_id")
        if not comment_id:
            return returnsdata.error_msg("Comment ID is required", ERROR)
        
        # Pass user_id for ownership validation
        await delete_forum_comment(db, comment_id, current_user.get('id'))
        return await get_forum_comments_endpoint(request, db, current_user) 
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete comment: {str(e)}", ERROR)


