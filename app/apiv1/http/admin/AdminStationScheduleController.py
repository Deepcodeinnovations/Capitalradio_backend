# AdminStationScheduleController.py
from fastapi import APIRouter, Request, status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.constants import SUCCESS, ERROR
from app.utils.returns_data import returnsdata
from typing import Optional, Dict, Any
from app.utils.security import get_current_user_details, verify_admin_access
from app.apiv1.services.admin.AdminStationScheduleService import (
    get_or_create_station_schedule,
    update_station_schedule,
    add_session_to_day,
    update_session_in_day,
    remove_session_from_day,
    clear_day_schedule,
    duplicate_day_schedule,
    get_schedule_conflicts,
    get_schedule_statistics
)
import json

router = APIRouter()

@router.post("/get/{station_id}", status_code=status.HTTP_200_OK)
async def get_station_schedule(station_id: str,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        schedule_data = await get_or_create_station_schedule(db, station_id)
        return returnsdata.success(data=schedule_data,msg="Station schedule retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get station schedule: {str(e)}", ERROR)




@router.post("/update/{station_id}", status_code=status.HTTP_200_OK)
async def update_schedule(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        body_data = await request.form()
        sessions_json = body_data.get("sessions")
        
        if not sessions_json:
            return returnsdata.error_msg("Sessions data is required", ERROR)
        
        try:
            sessions_data = json.loads(sessions_json)
        except json.JSONDecodeError:
            return returnsdata.error_msg("Invalid JSON format for sessions", ERROR)
        
        updated_schedule = await update_station_schedule(db, station_id, sessions_data, current_user.get("id"))
        
        return returnsdata.success(data=updated_schedule,msg="Station schedule updated successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update schedule: {str(e)}", ERROR)



@router.post("/add_session/{station_id}/{day}", status_code=status.HTTP_201_CREATED)
async def add_session(station_id: str,day: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        body_data = await request.form()
        
        required_fields = ["program_id", "start_time", "end_time"]
        for field in required_fields:
            if not body_data.get(field):
                return returnsdata.error_msg(f"{field.replace('_', ' ').title()} is required", ERROR)
        
        session_data = {
            "program_id": body_data.get("program_id"),
            "start_time": body_data.get("start_time"),
            "end_time": body_data.get("end_time"),
            "studio": body_data.get("studio", "A"),
            "is_live": body_data.get("is_live", "true").lower() == "true",
            "is_repeat": body_data.get("is_repeat", "false").lower() == "true",
            "notes": body_data.get("notes", "")
        }
        
        hosts_json = body_data.get("hosts")
        if hosts_json:
            try:
                session_data["hosts"] = json.loads(hosts_json)
            except json.JSONDecodeError:
                return returnsdata.error_msg("Invalid JSON format for hosts", ERROR)
        else:
            session_data["hosts"] = []
        
        updated_schedule = await add_session_to_day(db, station_id, day, session_data, current_user.get("id"))
        
        return returnsdata.success(data=updated_schedule,msg="Session added successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to add session: {str(e)}", ERROR)


@router.post("/update_session/{station_id}/{day}/{session_index}", status_code=status.HTTP_200_OK)
async def update_session(station_id: str,day: str,session_index: int,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        body_data = await request.form()
    
        session_data = {}
        optional_fields = ["program_id", "start_time", "end_time", "studio", "notes"]
        for field in optional_fields:
            if body_data.get(field) is not None:
                session_data[field] = body_data.get(field)
        
        if body_data.get("is_live") is not None:
            session_data["is_live"] = body_data.get("is_live", "false").lower() == "true"
        
        if body_data.get("is_repeat") is not None:
            session_data["is_repeat"] = body_data.get("is_repeat", "false").lower() == "true"
        
        hosts_json = body_data.get("hosts")
        if hosts_json:
            try:
                session_data["hosts"] = json.loads(hosts_json)
            except json.JSONDecodeError:
                return returnsdata.error_msg("Invalid JSON format for hosts", ERROR)
        
        if not session_data:
            return returnsdata.error_msg("No update data provided", ERROR)
        
        updated_schedule = await update_session_in_day(db, station_id, day, session_index, session_data, current_user.get("id"))
        
        return returnsdata.success(data=updated_schedule,msg="Session updated successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update session: {str(e)}", ERROR)


@router.post("/remove_session/{station_id}/{day}/{session_index}", status_code=status.HTTP_200_OK)
async def remove_session(station_id: str,day: str,session_index: int,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        updated_schedule = await remove_session_from_day(db, station_id, day, session_index, current_user.get("id"))
        
        return returnsdata.success(data=updated_schedule,msg="Session removed successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to remove session: {str(e)}", ERROR)


@router.post("/clear_day/{station_id}/{day}", status_code=status.HTTP_200_OK)
async def clear_day(station_id: str,day: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        updated_schedule = await clear_day_schedule(db, station_id, day, current_user.get("id"))
        
        return returnsdata.success(data=updated_schedule,msg=f"{day.title()} schedule cleared successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to clear day schedule: {str(e)}", ERROR)


@router.post("/duplicate_day/{station_id}/{source_day}/{target_day}", status_code=status.HTTP_200_OK)
async def duplicate_day(station_id: str,source_day: str,target_day: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        updated_schedule = await duplicate_day_schedule(db, station_id, source_day, target_day, current_user.get("id"))
        
        return returnsdata.success(data=updated_schedule,msg=f"{day.title()} schedule cleared successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to clear day schedule: {str(e)}", ERROR)


@router.post("/duplicate_day/{station_id}/{source_day}/{target_day}", status_code=status.HTTP_200_OK)
async def duplicate_day(station_id: str,source_day: str,target_day: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        updated_schedule = await duplicate_day_schedule(db, station_id, source_day, target_day, current_user.get("id"))
        
        return returnsdata.success(data=updated_schedule,msg=f"Schedule duplicated from {source_day} to {target_day} successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to duplicate day schedule: {str(e)}", ERROR)


@router.post("/conflicts/{station_id}", status_code=status.HTTP_200_OK)
async def get_conflicts(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        conflicts_data = await get_schedule_conflicts(db, station_id)
        
        return returnsdata.success(data=conflicts_data,msg="Schedule conflicts retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get schedule conflicts: {str(e)}", ERROR)


@router.post("/conflicts/{station_id}", status_code=status.HTTP_200_OK)
async def get_conflicts(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        conflicts_data = await get_schedule_conflicts(db, station_id)
        
        return returnsdata.success(data=conflicts_data,msg="Schedule conflicts retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get schedule conflicts: {str(e)}", ERROR)


@router.post("/statistics/{station_id}", status_code=status.HTTP_200_OK)
async def get_statistics(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        stats_data = await get_schedule_statistics(db, station_id)
        return returnsdata.success(data=stats_data,msg="Schedule statistics retrieved successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get schedule statistics: {str(e)}", ERROR)




@router.post("/validate/{station_id}", status_code=status.HTTP_200_OK)
async def validate_schedule(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        body_data = await request.form()
        sessions_json = body_data.get("sessions")
        
        if sessions_json:
            try:
                sessions_data = json.loads(sessions_json)
            except json.JSONDecodeError:
                return returnsdata.error_msg("Invalid JSON format for sessions", ERROR)
        else:
            # Get current schedule if no sessions provided
            schedule_data = await get_or_create_station_schedule(db, station_id)
            sessions_data = schedule_data["sessions"]
        
        # Create temporary schedule for validation
        from app.models.StationScheduleModel import StationSchedule
        temp_schedule = StationSchedule(station_id=station_id,sessions=sessions_data)
        
        validation_result = temp_schedule.validate_sessions()
        
        return returnsdata.success(
            data={
                "station_id": station_id,
                "validation_result": validation_result,
                "is_valid": validation_result["valid"],
                "error_count": len(validation_result["errors"]),
                "warning_count": len(validation_result["warnings"])
            },
            msg="Schedule validation completed",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to validate schedule: {str(e)}", ERROR)




@router.post("/backup/{station_id}", status_code=status.HTTP_200_OK)
async def backup_schedule(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        
        schedule_data = await get_or_create_station_schedule(db, station_id)
        
        backup_data = {
            "station_id": station_id,
            "backup_date": datetime.utcnow().isoformat(),
            "backed_up_by": current_user.get("id"),
            "sessions": schedule_data["sessions"],
            "metadata": {
                "station_name": schedule_data.get("station", {}).get("name", "Unknown"),
                "total_sessions": sum(len(day_sessions) for day_sessions in schedule_data["sessions"].values())
            }
        }
        
        return returnsdata.success(data=backup_data,msg="Schedule backup created successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to create schedule backup: {str(e)}", ERROR)




@router.post("/restore/{station_id}", status_code=status.HTTP_200_OK)
async def restore_schedule(station_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        if hasattr(current_user, 'status_code'):
           current_user = json.loads(current_user.body.decode())
        
        body_data = await request.form()
        backup_json = body_data.get("backup_data")
        
        if not backup_json:
            return returnsdata.error_msg("Backup data is required", ERROR)
        
        try:
            backup_data = json.loads(backup_json)
        except json.JSONDecodeError:
            return returnsdata.error_msg("Invalid JSON format for backup data", ERROR)
        
        if "sessions" not in backup_data:
            return returnsdata.error_msg("Invalid backup data: missing sessions", ERROR)
        
        updated_schedule = await update_station_schedule(db, station_id, backup_data["sessions"], current_user.get("id"))
        
        return returnsdata.success(data=updated_schedule,msg="Schedule restored from backup successfully",status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to restore schedule: {str(e)}", ERROR)