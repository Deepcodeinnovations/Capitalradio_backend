from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.RadioProgramModel import RadioProgram
from app.models.UserModel import User
from app.models.StationModel import Station
from app.models.HostModel import Host
import json
from app.utils.file_upload import save_upload_file, remove_file
from datetime import datetime
from typing import Optional, List
import uuid
import logging

logger = logging.getLogger(__name__)


async def get_programs(db: AsyncSession, page: int = 1, per_page: int = 100) -> List[RadioProgram]:
    try:
        offset = (page - 1) * per_page
        
        stmt = (select(RadioProgram).options(selectinload(RadioProgram.station),selectinload(RadioProgram.creator)).where(RadioProgram.state == True).order_by(RadioProgram.created_at.desc()).offset(offset).limit(per_page))
        
        result = await db.execute(stmt)
        programs = result.scalars().all()
        return programs
        
    except Exception as e:
        logger.error(f"Error fetching programs: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch programs")



async def get_program_by_id(db: AsyncSession, program_id: str) -> dict:
    try:
        stmt = (
            select(RadioProgram)
            .options(
                selectinload(RadioProgram.station),
                selectinload(RadioProgram.creator)
            )
            .where(RadioProgram.id == program_id)
            .where(RadioProgram.state == True)
        )
        
        result = await db.execute(stmt)
        program = result.scalar_one_or_none()
        
        if not program:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
            
        return await program.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching program {program_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch program")


async def create_new_program(db: AsyncSession, program_data: dict, image_file: Optional[UploadFile] = None, user_id: str = None) -> RadioProgram:
    try:
        # Validate required fields
        if not program_data.get("title"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Program title is required")
            
        if not program_data.get("station_id"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station is required")
        
        # Verify station exists
        station_stmt = select(Station).where(Station.id == program_data["station_id"])
        station_result = await db.execute(station_stmt)
        station = station_result.scalar_one_or_none()
        
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        # Handle image upload
        if image_file:
            image_path,image_url = await save_upload_file(image_file, "programs")
        
        # Create new program
        new_program = RadioProgram(
            title=program_data["title"],
            station_id=program_data["station_id"],
            description=program_data['description'],
            duration=program_data.get("duration", 60),
            studio=program_data.get("studio", "A"),
            type=program_data.get("type", "live_show"),
            image_path=image_path,
            image_url=image_url,
            created_by=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_program)
        await db.flush()  # Flush to get the ID
        
        # Handle host associations
        host_ids = program_data.get("host_ids", [])
        if host_ids:
            await associate_hosts_to_program(db, new_program.id, host_ids)
        
        await db.commit()
        await db.refresh(new_program)
        
        return new_program
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating program: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create program {str(e)}")


async def update_program_data(db: AsyncSession, program_id: str, program_data: dict, image_file: Optional[UploadFile] = None, user_id: str = None) -> RadioProgram:
    try:
        # Get existing program
        stmt = select(RadioProgram).where(RadioProgram.id == program_id).where(RadioProgram.state == True)
        result = await db.execute(stmt)
        program = result.scalar_one_or_none()
        
        if not program:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
        if program_data.get("station_id") and program_data["station_id"] != program.station_id:
            station_stmt = select(Station).where(Station.id == program_data["station_id"])
            station_result = await db.execute(station_stmt)
            station = station_result.scalar_one_or_none()
            if not station:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        if image_file:
            if program.image_path:
                remove_file(program.image_path)
            image_path,image_url = await save_upload_file(image_file, "programs")
            program.image_url = image_url
            program.image_path = image_path
        
        # Update program fields
        program.title = program_data.get("title", program.title)
        program.station_id = program_data.get("station_id", program.station_id)
        program.duration = program_data.get("duration", program.duration)
        program.studio = program_data.get("studio", program.studio)
        program.type = program_data.get("type", program.type)
        program.description = program_data.get("description", program.description)
        program.updated_at = datetime.utcnow()
        
        # Handle host associations
        host_ids = program_data.get("host_ids")
        if host_ids is not None:  # Allow empty list to remove all hosts
            await associate_hosts_to_program(db, program_id, host_ids)
        
        await db.commit()
        await db.refresh(program)
        
        return program
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating program {program_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update program {str(e)}")




async def delete_program_by_id(db: AsyncSession, program_id: str) -> bool:
    try:
        stmt = select(RadioProgram).where(RadioProgram.id == program_id).where(RadioProgram.state == True)
        result = await db.execute(stmt)
        program = result.scalar_one_or_none()
        
        if not program:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
        
        # Soft delete
        program.state = False
        program.status_value = False
        program.updated_at = datetime.utcnow()
        
        await db.commit()
        return True
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting program {program_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete program")



async def toggle_program_status(db: AsyncSession, program_id: str, status_value: bool) -> RadioProgram:
    try:
        stmt = select(RadioProgram).where(RadioProgram.id == program_id).where(RadioProgram.state == True)
        result = await db.execute(stmt)
        program = result.scalar_one_or_none()
        
        if not program:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
        
        # Update status
        program.status = True if status_value else False
        program.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(program)
        
        return program
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error toggling program status {program_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update program status {str(e)}")



async def update_program_image(db: AsyncSession, program_id: str, image_file: UploadFile) -> RadioProgram:
    try:
        stmt = select(RadioProgram).where(RadioProgram.id == program_id).where(RadioProgram.state == True)
        result = await db.execute(stmt)
        program = result.scalar_one_or_none()
        
        if not program:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
        
        # Upload new image
        if image_file:
            if program.image_path:
                remove_file(program.image_path)
            image_path,image_url = await save_upload_file(image_file, "programs")
            program.image_url = image_url
            program.image_path = image_path
            program.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(program)
        
        return program
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating program image {program_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update program image")




async def associate_hosts_to_program(db: AsyncSession, program_id: str, host_ids: List[str]):
    try:
        program_stmt = select(RadioProgram).where(RadioProgram.id == program_id)
        program_result = await db.execute(program_stmt)
        program = program_result.scalar_one_or_none()
        if not program:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
        
        hosts_data = []
        
        if host_ids:
            host_stmt = select(Host).where(Host.id.in_(host_ids)).where(Host.state == True)
            host_result = await db.execute(host_stmt)
            hosts = host_result.scalars().all()
            
            if len(hosts) != len(host_ids):
                found_ids = [host.id for host in hosts]
                missing_ids = [hid for hid in host_ids if hid not in found_ids]
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail=f"Hosts not found: {missing_ids}"
                )

            for host in hosts:
                hosts_data.append({
                    "id": host.id,
                    "name": host.name,
                    "role": host.role,
                    "email": host.email,
                    "phone": host.phone,
                    "image_url": host.image_url,
                    "on_air_status": host.on_air_status
                })
        
        program.hosts = hosts_data
        await db.flush()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error associating hosts to program {program_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to associate hosts {str(e)}")