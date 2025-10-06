from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, Date
from sqlalchemy import and_, desc, asc, or_
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.StationModel import Station
from slugify import slugify
from app.utils.file_upload import save_upload_file, remove_file
import math
from app.models.LiveChatMessageModel import LiveChatMessage
from app.models.StationListenersModel import StationListeners
from app.models.RadioSessionRecordingModel import RadioSessionRecording
from app.utils.websocket_manager import websocket_manager
from app.models.HostModel import Host
from app.models.EventModel import Event
from app.models.RadioProgramModel import RadioProgram
from app.utils.pagination import paginate_data
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import selectinload
from app.utils.advanced_paginator import paginate_query, QueryOptimizer

async def get_station_by_initial_access_link(db: AsyncSession, access_link: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Station).where(and_(Station.access_link == access_link, Station.state == True, Station.status == True)).limit(1))
        station = result.scalar_one_or_none()
        
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        await db.commit()
        await db.refresh(station)
        return await station.to_dict_with_relations(db, include_programs=True, include_schedule=True)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def get_station_by_access_link(db: AsyncSession, access_link: str, user_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(Station).where(and_(Station.access_link == access_link, Station.state == True, Station.status == True)).limit(1))
        station = result.scalar_one_or_none()
        
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        await StationListeners.create_station_listener(db, user_id=user_id, station_id=station.id)
        await db.commit()
        await db.refresh(station)
        return await station.to_dict_with_relations(db, include_programs=True, include_schedule=True)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



async def get_station_livechat_messages(db: AsyncSession, station_id: str, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    try:
        limit = min(limit, 200)  # Enforce 200 message limit
        
        query = select(LiveChatMessage).options(selectinload(LiveChatMessage.user),selectinload(LiveChatMessage.station)).where(and_(LiveChatMessage.station_id == station_id,LiveChatMessage.is_visible == True,LiveChatMessage.state == True,LiveChatMessage.status == True)).order_by(asc(LiveChatMessage.created_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return [await message.to_dict_with_relations(db=db) for message in messages]
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def delete_station_livechat_message(db: AsyncSession, message_id: str) -> bool:
    try:
        await db.execute(delete(LiveChatMessage).where(LiveChatMessage.id == message_id))
        return True
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def create_livechat_message(db: AsyncSession,station_id: str,message: str,user_id: Optional[str] = None,message_type: str = "user",metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        # Verify station exists
        station_result = await db.execute(select(Station).where(and_(Station.id == station_id, Station.state == True, Station.status == True)))
        station = station_result.scalar_one_or_none()
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        chat_message = LiveChatMessage(
            station_id=station_id,
            user_id=user_id,
            message=message,
            message_type=message_type,
        )
        
        db.add(chat_message)
        await db.commit()
        await db.refresh(chat_message)
        
        message_dict = await chat_message.to_dict_with_relations(db=db)

        if user_id:
            await websocket_manager.broadcast_to_station(
                db=db,
                station_id=station_id,
                data={"message": message_dict},
                message_type="livechat_message",
                message="New chat message"
            )
        return message_dict
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def get_user_hosts_by_station(db: AsyncSession, station_id: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    try:
        offset = (page - 1) * per_page
        
        # Get all radio programs for the station
        radio_programs_stmt = select(RadioProgram).where(
            and_(
                RadioProgram.station_id == station_id, 
                RadioProgram.state == True, 
                RadioProgram.status == True
            )
        )
        radio_programs_result = await db.execute(radio_programs_stmt)
        radio_programs = radio_programs_result.scalars().all()
        
        # Extract all host IDs from programs
        host_ids = set()
        for program in radio_programs:
            if program.hosts:  # Check if hosts exists and is not empty
                for host in program.hosts:
                    if isinstance(host, dict) and 'id' in host:
                        host_ids.add(host['id'])
        
        if not host_ids:
            return paginate_data([], page=page, per_page=per_page)
        
        # Get hosts by IDs
        stmt = select(Host).where(
            and_(
                Host.id.in_(list(host_ids)), 
                Host.state == True, 
                Host.status == True
            )
        ).order_by(desc(Host.created_at)).offset(offset).limit(per_page)
        
        result = await db.execute(stmt)
        hosts = result.scalars().all()
        
        hosts_data = [await host.to_dict_with_relations(db=db, include_programs=True) for host in hosts]
        
        return paginate_data(jsonable_encoder(hosts_data), page=page, per_page=per_page)
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch station hosts: {str(e)}")


async def get_user_radio_sessions(db: AsyncSession, station_id: str, data: Dict[str, Any], page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    try:
        query = select(RadioSessionRecording).where(and_(RadioSessionRecording.state == True, RadioSessionRecording.status == True, RadioSessionRecording.station_id == station_id, RadioSessionRecording.recording_status == 'completed'))
        filters = {}
        if data.get('program_id'): filters['program_id'] = data['program_id']
        if data.get('day_of_week'): filters['day_of_week'] = data['day_of_week']
        if data.get('recording_status'): filters['recording_status'] = data['recording_status']
        
        query = QueryOptimizer.add_multiple_filters(query, RadioSessionRecording, filters)
        if data.get('session_date'):
            try:
                session_date = datetime.fromisoformat(data['session_date']).date()
                query = query.where(RadioSessionRecording.session_date == session_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid session_date format")
        
        query = query.order_by(desc(RadioSessionRecording.created_at))
        async def transform_radio_session(item, db_session): return await item.to_dict_with_relations(db_session)
        return await paginate_query(db=db, query=query, page=page, per_page=per_page, transform_func=transform_radio_session, include_total=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get radio sessions: {str(e)}")



async def get_user_radio_events(db: AsyncSession, data: Dict[str, Any], page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    try:
        query = select(Event).where(and_(Event.state == True, Event.status == True))
        
        filters = {}
        
        # Event-specific filters based on actual model columns
        if data.get('category'): 
            filters['category'] = data['category']
        if data.get('event_type'): 
            filters['event_type'] = data['event_type']
        if data.get('currency'): 
            filters['currency'] = data['currency']
        if data.get('city'): 
            filters['city'] = data['city']
        if data.get('country'): 
            filters['country'] = data['country']
        
        # Boolean filters
        if data.get('is_virtual') is not None:
            filters['is_virtual'] = data['is_virtual']
        if data.get('is_featured') is not None:
            filters['is_featured'] = data['is_featured']
        if data.get('is_published') is not None:
            filters['is_published'] = data['is_published']
                
        query = QueryOptimizer.add_multiple_filters(query, Event, filters)
        
        # Date range filters
        if data.get('start_date'):
            try:
                start_date = datetime.fromisoformat(data['start_date'])
                query = query.where(Event.start_date >= start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format")
        
        if data.get('end_date'):
            try:
                end_date = datetime.fromisoformat(data['end_date'])
                query = query.where(Event.end_date <= end_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format")
        
        # Event date filter
        if data.get('event_date'):
            try:
                event_date = datetime.fromisoformat(data['event_date']).date()
                query = query.where(Event.start_date.cast(Date) == event_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid event_date format")
        
        # Search filter
        if data.get('search'):
            search_pattern = f"%{data['search']}%"
            query = query.where(or_(
                Event.title.ilike(search_pattern),
                Event.description.ilike(search_pattern),
                Event.venue_name.ilike(search_pattern),
                Event.venue_address.ilike(search_pattern)
            ))
        
        # Free/Paid filter (assuming events with featured_image are paid)
        if data.get('price_type'):
            if data['price_type'] == 'free':
                query = query.where(Event.featured_image_url.is_(None))
            elif data['price_type'] == 'paid':
                query = query.where(Event.featured_image_url.isnot(None))
        
        # Time-based filters for events
        if data.get('time_filter'):
            now = datetime.utcnow()
            if data['time_filter'] == 'upcoming':
                query = query.where(Event.start_date >= now)
            elif data['time_filter'] == 'past':
                query = query.where(Event.end_date < now)
            elif data['time_filter'] == 'current':
                query = query.where(and_(Event.start_date <= now, Event.end_date >= now))
        

        query = query.order_by(desc(Event.created_at))
        
        async def transform_event(item, db_session): 
            return await item.to_dict_with_relations(db_session)
            
        return await paginate_query(db=db, query=query, page=page, per_page=per_page, transform_func=transform_event, include_total=True)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get events: {str(e)}")


