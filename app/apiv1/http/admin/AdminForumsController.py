from fastapi import APIRouter, Request, status, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from typing import Optional, Dict, Any
from app.utils.security import get_current_user_details
from app.utils.pagination import paginate_data
from fastapi.encoders import jsonable_encoder
from app.apiv1.services.admin.AdminForumService import (
    get_forums,
    get_forum_by_id,
    create_new_forum,
    update_forum_data,
    delete_forum_by_id,
    update_forum_status,
    get_forum_comments,
    create_forum_comment,
    update_forum_comment,
    delete_forum_comment
)

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
async def fetch_forums(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        page = int(request.query_params.get("page", 1))
        per_page = int(body_data.get("per_page", 200))
        forums_results = await get_forums(db, page=page, per_page=per_page)
        forums_data = [await forum.to_dict_with_relations(db) for forum in forums_results]
        return paginate_data(jsonable_encoder(forums_data), page=page, per_page=per_page)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch forums: {str(e)}", ERROR)

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_forum(request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        title = body_data.get("title")
        body = body_data.get("body")
        station_id = body_data.get("station_id")
        
        if not title:
            return returnsdata.error_msg("Forum title is required", ERROR)
        if not body:
            return returnsdata.error_msg("Forum body is required", ERROR)
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        
        forum_data = {
            "title": title,
            "body": body,
            "station_id": station_id,
        }
        
        await create_new_forum(db, forum_data, current_user.get('id'))
        return await fetch_forums(request, db, current_user)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create forum: {str(e)}", ERROR)

@router.post("/{id}", status_code=status.HTTP_200_OK)
async def fetch_forum(id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        forum_data = await get_forum_by_id(db, id)
        return returnsdata.success(data=forum_data, msg="Forum fetched successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch forum: {str(e)}", ERROR)

@router.post("/update/{id}", status_code=status.HTTP_200_OK)
async def update_forum(id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        title = body_data.get("title")
        body = body_data.get("body")
        station_id = body_data.get("station_id")
        
        if not title:
            return returnsdata.error_msg("Forum title is required", ERROR)
        if not body:
            return returnsdata.error_msg("Forum body is required", ERROR)
        if not station_id:
            return returnsdata.error_msg("Station ID is required", ERROR)
        
        update_data = {
            "title": title,
            "body": body,
            "station_id": station_id
        }
        
        updated_forum = await update_forum_data(db, id, update_data)
        return returnsdata.success(data=updated_forum, msg="Forum updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update forum: {str(e)}", ERROR)

@router.post("/status/{id}", status_code=status.HTTP_200_OK)
async def update_forum_status_route(id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        status = body_data.get("status")
        
        if not status:
            return returnsdata.error_msg("Forum status is required", ERROR)
        
        updated_forum = await update_forum_status(db, id, {"status": status})
        return returnsdata.success(data=updated_forum, msg="Forum status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update forum status: {str(e)}", ERROR)

@router.post("/delete/{id}", status_code=status.HTTP_200_OK)
async def delete_forum(id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        await delete_forum_by_id(db, id)
        return returnsdata.success_msg(msg="Forum deleted successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete forum: {str(e)}", ERROR)

# Comment Routes
@router.post("/{forum_id}/comments", status_code=status.HTTP_200_OK)
async def fetch_comments(forum_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        page = int(request.query_params.get("page", 1))
        per_page = int(body_data.get("per_page", 10))
        comments_results = await get_forum_comments(db, forum_id, page=page, per_page=per_page)
        comments_data = [await comment.to_dict_with_relations(db) for comment in comments_results]
        return paginate_data(jsonable_encoder(comments_data), page=page, per_page=per_page)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to fetch comments: {str(e)}", ERROR)

@router.post("/{forum_id}/comments/create", status_code=status.HTTP_201_CREATED)
async def create_comment(forum_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        content = body_data.get("content")
        status_value = body_data.get("status", True)
        
        if not content:
            return returnsdata.error_msg("Comment content is required", ERROR)
        
        comment_data = {
            "content": content,
            "status": status_value,
            "forum_id": forum_id
        }
        
        new_comment = await create_forum_comment(db, comment_data, current_user.get('id'))
        comment_dict = await new_comment.to_dict_with_relations(db)
        return returnsdata.success(data=comment_dict, msg="Comment created successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create comment: {str(e)}", ERROR)

@router.post("/{forum_id}/comments/update/{comment_id}", status_code=status.HTTP_200_OK)
async def update_comment(forum_id: str, comment_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        body_data = await request.form()
        content = body_data.get("content")
        status_value = body_data.get("status")
        
        update_data = {}
        if content:
            update_data["content"] = content
        if status_value is not None:
            update_data["status"] = status_value
        
        if not update_data:
            return returnsdata.error_msg("No data provided for update", ERROR)
        
        updated_comment = await update_forum_comment(db, comment_id, update_data)
        return returnsdata.success(data=updated_comment, msg="Comment updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update comment: {str(e)}", ERROR)

@router.post("/{forum_id}/comments/delete/{comment_id}", status_code=status.HTTP_200_OK)
async def delete_comment(forum_id: str, comment_id: str, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        await delete_forum_comment(db, comment_id)
        return returnsdata.success_msg(msg="Comment deleted successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete comment: {str(e)}", ERROR)