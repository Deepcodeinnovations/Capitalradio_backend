from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy import and_, desc
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.StationModel import Station
from slugify import slugify
from app.utils.file_upload import save_upload_file, remove_file
import math

async def get_stations(db: AsyncSession, page: int = 1, per_page: int = 10) -> List[Station]:
    try:
        # Calculate offset
        offset = (page - 1) * per_page
        # Get stations with pagination
        stations_query = select(Station).where(and_(Station.state == True, Station.status == True)).order_by(desc(Station.created_at)).offset(offset)
        
        result = await db.execute(stations_query)
        stations = result.scalars().all()
        return stations
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def get_station_by_id(db: AsyncSession, station_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Station).where(and_(Station.id == station_id, Station.state == True, Station.status == True)))
        station = result.scalar_one_or_none()
        
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        return await station.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



async def create_new_station(db: AsyncSession, station_data: Dict[str, Any], admin_id: str) -> Dict[str, Any]:
    try:
        # Check if station name already exists
        existing_station = await db.execute(select(Station).where(and_(Station.name == station_data["name"], Station.state == True)))
        if existing_station.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station with this name already exists")
        
        # Check if frequency already exists
        existing_frequency = await db.execute(select(Station).where(and_(Station.frequency == station_data["frequency"], Station.state == True)))
        if existing_frequency.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station with this frequency already exists")
        
        # Generate slug
        slug = slugify(station_data["name"])

        logo_path = None
        logo_url = None
        logo_file = station_data.get("logo") if "logo" in station_data else None
        if logo_file:
            logo_path, logo_url = await save_upload_file(logo_file, "stations")

        banner_path = None
        banner_url = None
        banner_file = station_data.get("banner") if "banner" in station_data else None
        if banner_file:
            banner_path, banner_url = await save_upload_file(banner_file, "stations")

        logo_path = None
        logo_url = None
        logo_file = station_data.get("logo") if "logo" in station_data else None
        if logo_file:
            logo_path, logo_url = await save_upload_file(logo_file, "stations")
        
        # Create new station
        new_station = Station(
            name=station_data["name"],
            slug=slug,
            frequency=station_data["frequency"],
            tagline=station_data.get("tagline", ""),
            access_link=station_data.get("access_link", ""),
            streaming_link=station_data.get("streaming_link", ""),
            about=station_data.get("about", ""),
            streaming_status=station_data.get("streaming_status", "offline"),
            radio_access_status=station_data.get("radio_access_status", True),
            logo_url=logo_url,
            logo_path=logo_path,
            banner_url=banner_url,
            banner_path=banner_path,
            created_by=admin_id,
            status=True,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_station)
        await db.commit()
        await db.refresh(new_station)
        
        return await new_station.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create station: {str(e)}")



async def update_station_data(db: AsyncSession, station_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Get existing station
        result = await db.execute(select(Station).where(and_(Station.id == station_id, Station.state == True, Station.status == True)))
        station = result.scalar_one_or_none()
        
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        # Check if name already exists (excluding current station)
        if update_data.get("name") and update_data["name"] != station.name:
            existing_name = await db.execute(select(Station).where(and_(Station.name == update_data["name"], Station.id != station_id, Station.state == True)))
            if existing_name.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station with this name already exists")
        
        # Check if frequency already exists (excluding current station)
        if update_data.get("frequency") and update_data["frequency"] != station.frequency:
            existing_frequency = await db.execute(select(Station).where(and_(Station.frequency == update_data["frequency"], Station.id != station_id, Station.state == True)))
            if existing_frequency.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station with this frequency already exists")


        logo_path = None
        logo_url = None
        logo_file = update_data.get("logo") if "logo" in update_data else None
        if logo_file:
            if station.logo_path:
                remove_file(station.logo_path)
            logo_path, logo_url = await save_upload_file(logo_file, "stations")
            update_data["logo_url"] = logo_url
            update_data["logo_path"] = logo_path

        banner_path = None
        banner_url = None
        banner_file = update_data.get("banner") if "banner" in update_data else None
        if banner_file:
            if station.banner_path:
                remove_file(station.banner_path)
            banner_path, banner_url = await save_upload_file(banner_file, "stations")
            update_data["banner_url"] = banner_url
            update_data["banner_path"] = banner_path
        
        # Update station fields
        for key, value in update_data.items():
            if hasattr(station, key):
                setattr(station, key, value)
        
        # Update slug if name changed
        if update_data.get("name"):
            station.slug = slugify(update_data["name"])
        
        station.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(station)
        
        return await station.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update station: {str(e)}")



async def delete_station_by_id(db: AsyncSession, station_id: str) -> bool:
    try:
        # Get existing station
        result = await db.execute(select(Station).where(and_(Station.id == station_id, Station.state == True, Station.status == True)))
        station = result.scalar_one_or_none()
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        # Soft delete - set state to False
        station.state = False
        station.updated_at = datetime.utcnow()
        
        await db.commit()
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete station: {str(e)}")


async def toggle_station_streaming_status(db: AsyncSession, station_id: str, streaming_status: str) -> Dict[str, Any]:
    try:
        # Validate streaming status
        valid_statuses = ["live", "offline", "maintenance"]
        if streaming_status not in valid_statuses:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid streaming status")
        
        # Get existing station
        result = await db.execute(select(Station).where(and_(Station.id == station_id, Station.state == True, Station.status == True)))
        station = result.scalar_one_or_none()
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        # Update streaming status
        station.streaming_status = streaming_status
        station.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(station)
        
        return await station.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update streaming status: {str(e)}")


async def toggle_station_radio_access(db: AsyncSession, station_id: str, radio_access_status: bool) -> Dict[str, Any]:
    try:
        # Get existing station
        result = await db.execute(select(Station).where(and_(Station.id == station_id, Station.state == True, Station.status == True)))
        station = result.scalar_one_or_none()
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        # Update radio access status
        station.radio_access_status = radio_access_status
        station.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(station)  
        return await station.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update radio access status: {str(e)}")




async def get_active_stations(db: AsyncSession) -> List[Dict[str, Any]]:
    try:
        result = await db.execute(select(Station).where(and_(Station.state == True,Station.status == True,Station.radio_access_status == True)).order_by(Station.name))
        stations = result.scalars().all()
        stations_data = []
        for station in stations:
            station_dict = await station.to_dict()
            stations_data.append(station_dict)
        
        return stations_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))