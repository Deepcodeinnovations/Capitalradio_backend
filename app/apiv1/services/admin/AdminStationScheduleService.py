# StationScheduleService.py
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.StationScheduleModel import StationSchedule
from app.models.StationModel import Station
from app.models.RadioProgramModel import RadioProgram
from app.models.UserModel import User
import json
import copy


async def get_or_create_station_schedule(db: AsyncSession, station_id: str) -> Dict[str, Any]:
    try:
        # Verify station exists
        station_result = await db.execute(select(Station).where(and_(Station.id == station_id, Station.state == True)))
        station = station_result.scalar_one_or_none()
        
        if not station:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
        
        schedule_result = await db.execute(select(StationSchedule).where(and_(StationSchedule.station_id == station_id, StationSchedule.state == True)))
        schedule = schedule_result.scalar_one_or_none()
        
        if not schedule:
            schedule = StationSchedule(
                station_id=station_id,
                sessions=StationSchedule.get_empty_sessions(),
                status=True,
                state=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(schedule)
            await db.commit()
            await db.refresh(schedule)
        
        return await schedule.to_dict_with_relations(db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def update_station_schedule(db: AsyncSession, station_id: str, sessions_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:

    try:
        # Get existing schedule or create new one
        schedule_result = await db.execute(select(StationSchedule).where(and_(StationSchedule.station_id == station_id, StationSchedule.state == True)))
        schedule = schedule_result.scalar_one_or_none()
        
        if not schedule:
            # Create new schedule
            schedule = StationSchedule(
                station_id=station_id,
                sessions=sessions_data,
                status=True,
                state=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(schedule)
        else:
            schedule.sessions = sessions_data
            schedule.updated_at = datetime.utcnow()
        validation_result = schedule.validate_sessions()
        if not validation_result["valid"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid sessions data: {', '.join(validation_result['errors'])}")
        await validate_programs_exist(db, sessions_data)
        await db.commit()
        await db.refresh(schedule)
        
        result = await schedule.to_dict_with_relations(db)
        
        # Add validation warnings to result
        if validation_result["warnings"]:
            result["warnings"] = validation_result["warnings"]
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def validate_programs_exist(db: AsyncSession, sessions_data: Dict[str, Any]) -> None:
    program_ids = set()
    
    # Collect all program IDs from sessions
    for day, sessions in sessions_data.items():
        for session in sessions:
            if "program_id" in session:
                program_ids.add(session["program_id"])
    
    if not program_ids:
        return
    
    programs_result = await db.execute(select(RadioProgram).where(and_(RadioProgram.id.in_(program_ids), RadioProgram.state == True)))
    existing_programs = {p.id for p in programs_result.scalars().all()}
    
    missing_programs = program_ids - existing_programs
    if missing_programs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Programs not found: {', '.join(missing_programs)}")


async def add_session_to_day(db: AsyncSession, station_id: str, day: str, session_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    try:
        current_schedule = await get_or_create_station_schedule(db, station_id)
        sessions = copy.deepcopy(current_schedule["sessions"])
        
        if day not in sessions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid day: {day}")
        sessions[day].append(session_data)

        return await update_station_schedule(db, station_id, sessions, user_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



async def update_session_in_day(db: AsyncSession, station_id: str, day: str, session_index: int, session_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    try:
        current_schedule = await get_or_create_station_schedule(db, station_id)
        sessions = copy.deepcopy(current_schedule["sessions"])
        
        if day not in sessions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid day: {day}")
        
        if session_index < 0 or session_index >= len(sessions[day]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid session index: {session_index}")
        
        sessions[day][session_index] = session_data
        return await update_station_schedule(db, station_id, sessions, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



async def remove_session_from_day(db: AsyncSession, station_id: str, day: str, session_index: int, user_id: str) -> Dict[str, Any]:
    try:
        current_schedule = await get_or_create_station_schedule(db, station_id)
        sessions = copy.deepcopy(current_schedule["sessions"])
        
        if day not in sessions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid day: {day}")
        
        if session_index < 0 or session_index >= len(sessions[day]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid session index: {session_index}")
        sessions[day].pop(session_index)
        return await update_station_schedule(db, station_id, sessions, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def clear_day_schedule(db: AsyncSession, station_id: str, day: str, user_id: str) -> Dict[str, Any]:
    try:
        current_schedule = await get_or_create_station_schedule(db, station_id)
        sessions = copy.deepcopy(current_schedule["sessions"])
        
        if day not in sessions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid day: {day}")
        sessions[day] = []
        return await update_station_schedule(db, station_id, sessions, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



async def duplicate_day_schedule(db: AsyncSession, station_id: str, source_day: str, target_day: str, user_id: str) -> Dict[str, Any]:
    try:
        current_schedule = await get_or_create_station_schedule(db, station_id)
        sessions = copy.deepcopy(current_schedule["sessions"])
        
        if source_day not in sessions or target_day not in sessions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid day specified")
        sessions[target_day] = copy.deepcopy(sessions[source_day])
        return await update_station_schedule(db, station_id, sessions, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def get_schedule_conflicts(db: AsyncSession, station_id: str) -> Dict[str, Any]:
    try:
        schedule = await get_or_create_station_schedule(db, station_id)
        temp_schedule = StationSchedule(station_id=station_id,sessions=schedule["sessions"])
        validation_result = temp_schedule.validate_sessions()
        
        return {
            "station_id": station_id,
            "has_conflicts": not validation_result["valid"] or len(validation_result["warnings"]) > 0,
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"],
            "total_issues": len(validation_result["errors"]) + len(validation_result["warnings"])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



async def get_schedule_statistics(db: AsyncSession, station_id: str) -> Dict[str, Any]:
    try:
        schedule = await get_or_create_station_schedule(db, station_id)
        sessions = schedule["sessions"]
        
        stats = {
            "total_sessions": 0,
            "total_hours": 0,
            "live_sessions": 0,
            "repeat_sessions": 0,
            "studio_usage": {"A": 0, "B": 0, "C": 0, "D": 0},
            "daily_distribution": {},
            "program_usage": {},
            "busiest_day": None,
            "quietest_day": None
        }
        
        daily_counts = {}
        total_minutes = 0
        
        for day, day_sessions in sessions.items():
            daily_counts[day] = len(day_sessions)
            stats["daily_distribution"][day] = len(day_sessions)
            
            for session in day_sessions:
                stats["total_sessions"] += 1
                
                # Calculate duration
                start_time = session.get("start_time", "00:00")
                end_time = session.get("end_time", "00:00")
                
                try:
                    start_hour, start_min = map(int, start_time.split(":"))
                    end_hour, end_min = map(int, end_time.split(":"))
                    
                    start_minutes = start_hour * 60 + start_min
                    end_minutes = end_hour * 60 + end_min
                    
                    if end_minutes > start_minutes:
                        duration = end_minutes - start_minutes
                        total_minutes += duration
                except:
                    pass
                
                # Count live/repeat
                if session.get("is_live", False):
                    stats["live_sessions"] += 1
                if session.get("is_repeat", False):
                    stats["repeat_sessions"] += 1
                
                # Studio usage
                studio = session.get("studio", "A")
                if studio in stats["studio_usage"]:
                    stats["studio_usage"][studio] += 1
                
                # Program usage
                program_id = session.get("program_id")
                if program_id:
                    stats["program_usage"][program_id] = stats["program_usage"].get(program_id, 0) + 1
        
        stats["total_hours"] = round(total_minutes / 60, 2)
        
        if daily_counts:
            stats["busiest_day"] = max(daily_counts, key=daily_counts.get)
            stats["quietest_day"] = min(daily_counts, key=daily_counts.get)
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))