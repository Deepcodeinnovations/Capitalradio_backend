from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc
from datetime import datetime
from slugify import slugify
from typing import List, Dict, Any, Optional
from app.models.ForumModel import Forum
from app.models.ForumCommentModel import ForumComment
from app.utils.returns_data import returnsdata
from app.utils.constants import SUCCESS, ERROR


async def get_forums(db: AsyncSession, page: int = 1, per_page: int = 10) -> List[Forum]:
    try:
        offset = (page - 1) * per_page
        
        stmt = select(Forum).where(and_(Forum.state == True)).order_by(desc(Forum.created_at)).offset(offset).limit(per_page)     
        result = await db.execute(stmt)
        forums = result.scalars().all()
        return forums
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch forums: {str(e)}")


async def get_forum_by_id(db: AsyncSession, forum_id: str) -> Dict[str, Any]:
    try:
        stmt = select(Forum).where(and_(Forum.id == forum_id, Forum.state == True))
        result = await db.execute(stmt)
        forum = result.scalar_one_or_none()
        
        if not forum:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum not found")
            
        return await forum.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch forum: {str(e)}")


async def create_new_forum(db: AsyncSession, forum_data: Dict[str, Any], admin_id: str) -> Forum:
    try:
        slug = slugify(forum_data.get("title"))
        new_forum = Forum(
            title=forum_data.get("title"),
            body=forum_data.get("body"),
            station_id=forum_data.get("station_id"),
            created_by=admin_id,
            slug=slug,
            is_pinned=forum_data.get("is_pinned", False),
            is_published=forum_data.get("is_published", False),
            status=True,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_forum)
        await db.commit()
        await db.refresh(new_forum)
        return new_forum
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create forum: {str(e)}")


async def update_forum_data(db: AsyncSession, forum_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        stmt = select(Forum).where(and_(Forum.id == forum_id, Forum.state == True))
        result = await db.execute(stmt)
        forum = result.scalar_one_or_none()
        
        if not forum:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum not found")
        if update_data.get("title"):
            forum.slug = slugify(update_data.get("title"))
        for key, value in update_data.items():
            if hasattr(forum, key) and value is not None:
                setattr(forum, key, value)
        
        forum.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(forum)
        return await forum.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update forum: {str(e)}")


async def update_forum_status(db: AsyncSession, forum_id: str, status_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        stmt = select(Forum).where(and_(Forum.id == forum_id, Forum.state == True))
        result = await db.execute(stmt)
        forum = result.scalar_one_or_none()
        
        if not forum:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum not found")
        
        status_value = status_data.get("status")
        if isinstance(status_value, str):
            forum.status = status_value.lower() in ['true', '1', 'active', 'enabled']
        else:
            forum.status = bool(status_value)
        
        forum.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(forum)
        return await forum.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update forum status: {str(e)}")


async def delete_forum_by_id(db: AsyncSession, forum_id: str) -> bool:
    try:
        stmt = select(Forum).where(and_(Forum.id == forum_id, Forum.state == True))
        result = await db.execute(stmt)
        forum = result.scalar_one_or_none()
        
        if not forum:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum not found")
        await forum.delete_with_relations(db)
        await db.commit()
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete forum: {str(e)}")


# Comment Service Functions
async def get_forum_comments(db: AsyncSession, forum_id: str, page: int = 1, per_page: int = 10) -> List[ForumComment]:
    try:
        offset = (page - 1) * per_page
        
        stmt = select(ForumComment).where(
            and_(ForumComment.forum_id == forum_id, ForumComment.state == True)
        ).order_by(desc(ForumComment.created_at)).offset(offset).limit(per_page)
        
        result = await db.execute(stmt)
        comments = result.scalars().all()
        return comments
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch comments: {str(e)}")


async def create_forum_comment(db: AsyncSession, comment_data: Dict[str, Any], user_id: str) -> ForumComment:
    try:
        # Convert status to boolean if it's a string
        status_value = comment_data.get("status", True)
        if isinstance(status_value, str):
            status_value = status_value.lower() in ['true', '1', 'active', 'enabled']
        
        new_comment = ForumComment(
            content=comment_data.get("content"),
            forum_id=comment_data.get("forum_id"),
            created_by=user_id,
            status=status_value,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_comment)
        await db.commit()
        await db.refresh(new_comment)
        return new_comment
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create comment: {str(e)}")


async def update_forum_comment(db: AsyncSession, comment_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        stmt = select(ForumComment).where(and_(ForumComment.id == comment_id, ForumComment.state == True))
        result = await db.execute(stmt)
        comment = result.scalar_one_or_none()
        
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        
        for key, value in update_data.items():
            if hasattr(comment, key) and value is not None:
                if key == "status" and isinstance(value, str):
                    setattr(comment, key, value.lower() in ['true', '1', 'active', 'enabled'])
                else:
                    setattr(comment, key, value)
        
        comment.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(comment)
        return await comment.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update comment: {str(e)}")


async def delete_forum_comment(db: AsyncSession, comment_id: str) -> bool:
    try:
        stmt = select(ForumComment).where(and_(ForumComment.id == comment_id, ForumComment.state == True))
        result = await db.execute(stmt)
        comment = result.scalar_one_or_none()
        
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        
        comment.state = False
        comment.updated_at = datetime.utcnow()
        
        await db.commit()
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete comment: {str(e)}")