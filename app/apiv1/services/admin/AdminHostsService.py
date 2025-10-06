from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy import and_, desc
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.HostModel import Host
from slugify import slugify
from app.utils.file_upload import save_upload_file, remove_file
import math
import os
import uuid
from pathlib import Path

async def get_hosts(db: AsyncSession, page: int = 1, per_page: int = 10) -> List[Host]:
    try:
        # Calculate offset
        offset = (page - 1) * per_page
        # Get hosts with pagination
        hosts_query = select(Host).where(and_(Host.state == True, Host.status == True)).order_by(desc(Host.created_at)).offset(offset)
        
        result = await db.execute(hosts_query)
        hosts = result.scalars().all()
        return hosts
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def get_host_by_id(db: AsyncSession, host_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Host).where(and_(Host.id == host_id, Host.state == True, Host.status == True)))
        host = result.scalar_one_or_none()
        
        if not host:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")
        
        return await host.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def create_new_host(db: AsyncSession, host_data: Dict[str, Any], image: UploadFile, admin_id: str) -> Dict[str, Any]:
    try:
        existing_host = await db.execute(select(Host).where(and_(Host.name == host_data["name"], Host.state == True)))
        if existing_host.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Host with this name already exists")
        if host_data.get("email"):
            existing_email = await db.execute(select(Host).where(and_(Host.email == host_data["email"], Host.state == True)))
            if existing_email.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Host with this email already exists")
        
        # Generate slug
        slug = slugify(host_data["name"])

        image_url = None
        image_path = None
        if image:
           image_path,image_url = await save_upload_file(image, "hosts/profile_images")

        # Create new host
        new_host = Host(
            name=host_data["name"],
            slug=slug,
            role=host_data.get("role", ""),
            email=host_data.get("email", ""),
            phone=host_data.get("phone", ""),
            bio=host_data.get("bio", ""),
            social_media=host_data.get("social_media", ""),
            experience_years=host_data.get("experience_years", 0),
            on_air_status=host_data.get("on_air_status", False),
            image_url=image_url,
            image_path=image_path,
            created_by=admin_id,
            status=True,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_host)
        await db.commit()
        await db.refresh(new_host)
        
        return await new_host.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create host: {str(e)}")



async def update_host_data(db: AsyncSession, host_id: str, update_data: Dict[str, Any], image: Optional[UploadFile] = None, admin_id: str = None) -> Dict[str, Any]:
    try:
        # Get existing host
        result = await db.execute(select(Host).where(and_(Host.id == host_id, Host.state == True, Host.status == True)))
        host = result.scalar_one_or_none()
        
        if not host:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")
        
        # Check if name already exists (excluding current host)
        if update_data.get("name") and update_data["name"] != host.name:
            existing_name = await db.execute(select(Host).where(and_(Host.name == update_data["name"], Host.id != host_id, Host.state == True)))
            if existing_name.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Host with this name already exists")
        
        # Check if email already exists (excluding current host)
        if update_data.get("email") and update_data["email"] != host.email:
            existing_email = await db.execute(select(Host).where(and_(Host.email == update_data["email"], Host.id != host_id, Host.state == True)))
            if existing_email.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Host with this email already exists")
        

        image_url = None
        image_path = None
        if image:
            if host.image_path:
                await remove_file(host.image_path)
            image_path,image_url = await save_upload_file(image, "hosts/profile_images")
            host['image_url'] = image_url
            host['image_path'] = image_path
        # Update host fields
        for key, value in update_data.items():
            if hasattr(host, key):
                setattr(host, key, value)
        
        # Update slug if name changed
        if update_data.get("name"):
            host.slug = slugify(update_data["name"])
        
        host.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(host)
        
        return host
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update host: {str(e)}")




async def delete_host_by_id(db: AsyncSession, host_id: str) -> bool:
    try:
        # Get existing host
        result = await db.execute(select(Host).where(and_(Host.id == host_id, Host.state == True, Host.status == True)))
        host = result.scalar_one_or_none()
        if not host:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")
        host.state = False
        host.updated_at = datetime.utcnow()
        
        await db.commit()
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete host: {str(e)}")


async def toggle_host_status(db: AsyncSession, host_id: str, status_value: bool) -> Dict[str, Any]:
    try:
        # Get existing host
        result = await db.execute(select(Host).where(and_(Host.id == host_id, Host.state == True)))
        host = result.scalar_one_or_none()
        if not host:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")
        
        # Update status
        host.status = status_value
        host.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(host)
        
        return await host.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update host status: {str(e)}")


async def update_host_profile_image(db: AsyncSession, host_id: str, image_file: UploadFile) -> Dict[str, Any]:
    try:
        # Get existing host
        result = await db.execute(select(Host).where(and_(Host.id == host_id, Host.state == True, Host.status == True)))
        host = result.scalar_one_or_none()
        if not host:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Host not found")
        
        if host.image_path:
            remove_file(host.image_path)
        image_path,image_url = await save_upload_file(image_file, "hosts/profile_images")
        host.image_url = image_url
        host.image_path = image_path
        host.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(host)
        
        return await host.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update profile image: {str(e)}")


async def get_active_hosts(db: AsyncSession) -> List[Dict[str, Any]]:
    try:
        result = await db.execute(select(Host).where(and_(Host.state == True, Host.status == True)).order_by(Host.name))
        hosts = result.scalars().all()
        hosts_data = []
        for host in hosts:
            host_dict = await host.to_dict()
            hosts_data.append(host_dict)
        
        return hosts_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



async def get_on_air_hosts(db: AsyncSession) -> List[Dict[str, Any]]:
    try:
        result = await db.execute(select(Host).where(and_(Host.state == True, Host.status == True, Host.on_air_status == True)).order_by(Host.name))
        hosts = result.scalars().all()
        hosts_data = []
        for host in hosts:
            host_dict = await host.to_dict()
            hosts_data.append(host_dict)
        
        return hosts_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))