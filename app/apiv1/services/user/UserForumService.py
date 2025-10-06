from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func, asc, or_
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.ForumModel import Forum
from app.models.ForumCommentModel import ForumComment
from app.models.UserModel import User
from app.utils.returns_data import returnsdata
from app.utils.constants import SUCCESS, ERROR
from datetime import timedelta


async def get_forum_metrics(db: AsyncSession, station_id: str) -> Dict[str, Any]:
    try:
        # Get total topics (forums) for this station
        topics_stmt = select(func.count(Forum.id)).where(
            and_(Forum.state == True, Forum.status == True, Forum.station_id == station_id)
        )
        topics_result = await db.execute(topics_stmt)
        total_topics = topics_result.scalar() or 0
        
        # Get total comments for forums in this station
        comments_stmt = select(func.count(ForumComment.id)).join(Forum).where(
            and_(
                ForumComment.state == True,
                ForumComment.status == True,
                Forum.station_id == station_id,
                Forum.state == True
            )
        )
        comments_result = await db.execute(comments_stmt)
        total_comments = comments_result.scalar() or 0
        
        # Get total views for forums in this station (sum of all forum views)
        forums_stmt = select(Forum.views).where(
            and_(Forum.state == True, Forum.status == True, Forum.station_id == station_id)
        )
        forums_result = await db.execute(forums_stmt)
        forums_views = forums_result.scalars().all()
        
        total_views = 0
        for views_json in forums_views:
            if views_json and isinstance(views_json, list):
                # Count number of view entries in the JSON array
                total_views += len(views_json)
        
        # Get users online in last 30 minutes
        thirty_minutes_ago = datetime.utcnow() - timedelta(minutes=30)
        online_stmt = select(func.count(User.id)).where(
            and_(
                User.state == True,
                User.status == True,
                User.last_seen >= thirty_minutes_ago
            )
        )
        online_result = await db.execute(online_stmt)
        online_now = online_result.scalar() or 0
        
        return {
            "total_topics": total_topics,
            "total_comments": total_comments,
            "total_views": total_views,
            "online_now": online_now
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch forum metrics: {str(e)}")


async def get_user_forums(db: AsyncSession,station_id: str, filters: dict = None, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    try:
        offset = (page - 1) * per_page
        
        stmt = select(Forum).where(and_(Forum.state == True, Forum.status == True, Forum.station_id == station_id))
        
        # Add filters if provided
        if filters:
            if filters.get("search"):
                search_term = f"%{filters.get('search')}%"
                stmt = stmt.where(
                    or_(
                        Forum.title.ilike(search_term),
                        Forum.body.ilike(search_term)
                    )
                )
        
        # Get total count
        count_stmt = select(func.count(Forum.id)).where(and_(Forum.state == True, Forum.status == True))
        if filters and filters.get("search"):
            search_term = f"%{filters.get('search')}%"
            count_stmt = count_stmt.where(
                or_(
                    Forum.title.ilike(search_term),
                    Forum.body.ilike(search_term)
                )
            )
        
        total_result = await db.execute(count_stmt)
        total_count = total_result.scalar()
        
        # Get forums
        stmt = stmt.order_by(desc(Forum.created_at)).offset(offset).limit(per_page)
        result = await db.execute(stmt)
        forums = result.scalars().all()
        
        forums_data = []
        for forum in forums:
            forum_dict = await forum.to_dict_with_relations(db)
            forums_data.append(forum_dict)
        metrics = await get_forum_metrics(db, station_id)
        return {
            "data": forums_data,
            "current_page": page,
            "per_page": per_page,
            "total": total_count,
            "total_pages": (total_count + per_page - 1) // per_page,
            "metrics": metrics
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch forums: {str(e)}")



async def get_forum_by_slug(db: AsyncSession, forum_slug: str, user_id: str) -> Dict[str, Any]:
    try:
        stmt = select(Forum).where(and_(Forum.slug == forum_slug, Forum.state == True, Forum.status == True))
        result = await db.execute(stmt)
        forum = result.scalar_one_or_none()
        
        if not forum:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum not found")
        
        # Initialize views if None and handle user view tracking
        if user_id:
            if forum.views is None:
                forum.views = []
            
            # Check if user already viewed
            user_viewed = any(view.get("user_id") == user_id for view in forum.views)
            
            if not user_viewed:
                forum.views.append({
                    "user_id": user_id,
                    "viewed_at": datetime.utcnow().isoformat()
                })
                await db.commit()
                     
        return await forum.to_dict_with_relations(db)
             
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch forum: {str(e)}")


async def get_forum_comments(db: AsyncSession, forum_id: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    try:
        offset = (page - 1) * per_page
        
        # Get total count
        count_stmt = select(func.count(ForumComment.id)).where(
            and_(ForumComment.forum_id == forum_id, ForumComment.state == True, ForumComment.status == True)
        )
        total_result = await db.execute(count_stmt)
        total_count = total_result.scalar()
        
        # Get comments
        stmt = select(ForumComment).where(
            and_(ForumComment.forum_id == forum_id, ForumComment.state == True, ForumComment.status == True)
        ).order_by(asc(ForumComment.created_at)).offset(offset).limit(per_page)
        
        result = await db.execute(stmt)
        comments = result.scalars().all()
        
        comments_data = []
        for comment in comments:
            comment_dict = await comment.to_dict_with_relations(db)
            comments_data.append(comment_dict)
        
        return {
            "data": comments_data,
            "current_page": page,
            "per_page": per_page,
            "total": total_count,
            "total_pages": (total_count + per_page - 1) // per_page
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch comments: {str(e)}")


async def create_forum_comment(db: AsyncSession, comment_data: Dict[str, Any], user_id: str) -> ForumComment:
    try:
        # Get forum by slug
        stmt = select(Forum).where(and_(Forum.id == comment_data.get("forum_id"), Forum.state == True, Forum.status == True))
        result = await db.execute(stmt)
        forum = result.scalar_one_or_none()
        
        if not forum:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum not found")
        
        # Convert status to boolean if it's a string
        status_value = comment_data.get("status", True)
        if isinstance(status_value, str):
            status_value = status_value.lower() in ['true', '1', 'active', 'enabled']
        if comment_data.get("reply_to"):
            reply_to = comment_data.get("reply_to")
        else:
            reply_to = None
        new_comment = ForumComment(
            content=comment_data.get("content"),
            forum_id=forum.id,
            created_by=user_id,
            reply_to=reply_to,
            status=status_value,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_comment)
        await db.commit()
        await db.refresh(new_comment)
        return new_comment
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create comment: {str(e)}")


async def delete_forum_comment(db: AsyncSession, comment_id: str, user_id: str) -> bool:
    try:
        stmt = select(ForumComment).where(and_(ForumComment.id == comment_id, ForumComment.state == True))
        result = await db.execute(stmt)
        comment = result.scalar_one_or_none()
        
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        
        # Check ownership
        if comment.created_by != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own comments")
        
        await comment.delete_with_relations(db)
        
        await db.commit()
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete comment: {str(e)}")