from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, or_
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.AdvertModel import Advert
from app.utils.returns_data import returnsdata
from app.utils.constants import SUCCESS, ERROR
from app.utils.file_upload import save_upload_file, remove_file
import os
import uuid


async def get_adverts(db: AsyncSession, page: int = 1, per_page: int = 10, filters: Dict[str, Any] = None) -> List[Advert]:
    try:
        offset = (page - 1) * per_page
        
        # Build query with filters
        conditions = [Advert.state == True]
        
        if filters:
            if filters.get("station_id"):
                conditions.append(Advert.station_id == filters["station_id"])
            
            if filters.get("status") is not None:
                if isinstance(filters["status"], str):
                    status_value = filters["status"].lower() in ['true', '1', 'active', 'enabled']
                else:
                    status_value = bool(filters["status"])
                conditions.append(Advert.status == status_value)
        
        stmt = select(Advert).where(and_(*conditions)).order_by(desc(Advert.created_at)).offset(offset).limit(per_page)
        
        result = await db.execute(stmt)
        adverts = result.scalars().all()
        return adverts
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch adverts: {str(e)}")


async def get_advert_by_id(db: AsyncSession, advert_id: str) -> Dict[str, Any]:
    try:
        stmt = select(Advert).where(and_(Advert.id == advert_id, Advert.state == True))
        result = await db.execute(stmt)
        advert = result.scalar_one_or_none()
        
        if not advert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advert not found")
            
        return await advert.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch advert: {str(e)}")


async def create_new_advert(db: AsyncSession, advert_data: Dict[str, Any], admin_id: str, image: Optional[UploadFile] = None) -> Advert:
    try:
        # Handle image upload
        image_path = None
        image_url = None
        
        if image and image.filename:
            image_path, image_url = await save_upload_file(image, "adverts")
        
        # Convert status to boolean if it's a string
        status_value = advert_data.get("status", True)
        if isinstance(status_value, str):
            status_value = status_value.lower() in ['true', '1', 'active', 'enabled']
        
        new_advert = Advert(
            title=advert_data.get("title"),
            description=advert_data.get("description"),
            station_id=advert_data.get("station_id"),
            target_url=advert_data.get("target_url"),
            button_title=advert_data.get("button_title"),
            image_path=image_path,
            image_url=image_url,
            created_by=admin_id,
            status=status_value,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_advert)
        await db.commit()
        await db.refresh(new_advert)
        return new_advert
        
    except Exception as e:
        await db.rollback()
        # Clean up uploaded image if database operation fails
        if 'image_path' in locals() and image_path:
            remove_file(image_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create advert: {str(e)}")


async def update_advert_data(db: AsyncSession, advert_id: str, update_data: Dict[str, Any], image: Optional[UploadFile] = None) -> Dict[str, Any]:
    try:
        stmt = select(Advert).where(and_(Advert.id == advert_id, Advert.state == True))
        result = await db.execute(stmt)
        advert = result.scalar_one_or_none()
        
        if not advert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advert not found")
        
        # Handle image upload
        old_image_path = advert.image_path
        if image and image.filename:
            image_path, image_url = await save_upload_file(image, "adverts")
            update_data["image_path"] = image_path
            update_data["image_url"] = image_url
        
        # Update fields
        for key, value in update_data.items():
            if hasattr(advert, key) and value is not None:
                if key == "status" and isinstance(value, str):
                    setattr(advert, key, value.lower() in ['true', '1', 'active', 'enabled'])
                else:
                    setattr(advert, key, value)
        
        advert.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(advert)
        
        # Delete old image if new one was uploaded
        if image and image.filename and old_image_path:
            remove_file(old_image_path)
        
        return await advert.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        # Clean up uploaded image if database operation fails
        if image and image.filename and 'image_path' in locals():
            remove_file(locals()['image_path'])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update advert: {str(e)}")


async def update_advert_status(db: AsyncSession, advert_id: str, status_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        stmt = select(Advert).where(and_(Advert.id == advert_id, Advert.state == True))
        result = await db.execute(stmt)
        advert = result.scalar_one_or_none()
        
        if not advert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advert not found")
        
        status_value = status_data.get("status")
        if isinstance(status_value, str):
            advert.status = status_value.lower() in ['true', '1', 'active', 'enabled']
        else:
            advert.status = bool(status_value)
        
        advert.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(advert)
        return await advert.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update advert status: {str(e)}")


async def delete_advert_by_id(db: AsyncSession, advert_id: str) -> bool:
    try:
        stmt = select(Advert).where(and_(Advert.id == advert_id, Advert.state == True))
        result = await db.execute(stmt)
        advert = result.scalar_one_or_none()
        
        if not advert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advert not found")
        
        # Store image path for deletion
        image_path = advert.image_path
        
        # Soft delete
        advert.state = False
        advert.updated_at = datetime.utcnow()
        
        await db.commit()
        
        # Delete image file after successful database operation
        if image_path:
            remove_file(image_path)
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete advert: {str(e)}")


async def get_adverts_by_station(db: AsyncSession, station_id: str, page: int = 1, per_page: int = 10) -> List[Advert]:
    try:
        offset = (page - 1) * per_page
        
        stmt = select(Advert).where(
            and_(Advert.station_id == station_id, Advert.state == True, Advert.status == True)
        ).order_by(desc(Advert.created_at)).offset(offset).limit(per_page)
        
        result = await db.execute(stmt)
        adverts = result.scalars().all()
        return adverts
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch station adverts: {str(e)}")


async def search_adverts(db: AsyncSession, search_term: str, page: int = 1, per_page: int = 10) -> List[Advert]:
    try:
        offset = (page - 1) * per_page
        
        stmt = select(Advert).where(
            and_(
                Advert.state == True,
                or_(
                    Advert.title.ilike(f"%{search_term}%"),
                    Advert.description.ilike(f"%{search_term}%")
                )
            )
        ).order_by(desc(Advert.created_at)).offset(offset).limit(per_page)
        
        result = await db.execute(stmt)
        adverts = result.scalars().all()
        return adverts
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to search adverts: {str(e)}")