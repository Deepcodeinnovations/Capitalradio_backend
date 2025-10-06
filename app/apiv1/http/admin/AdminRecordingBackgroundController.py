from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_database
from app.utils.security import get_current_user_details, verify_admin_access
from app.utils.returns_data import returnsdata
from app.utils.pagination import paginate_data
from fastapi.encoders import jsonable_encoder
from app.utils.constants import SUCCESS, ERROR
from app.apiv1.services.admin.AdminRecordingBackgroundService import (
    get_radio_sessions,
    get_radio_session_by_id,
    delete_radio_session,
    toggle_radio_session_status,
    update_radio_session_recording
)
from datetime import datetime
from app.utils.RecordingBackgroundUtil import recording_service
router = APIRouter()

@router.post("/start")
async def start_recording_endpoint(request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        await recording_service.validate_and_start()
        return returnsdata.success_msg(msg="Recording started successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to start recording: {str(e)}", ERROR)


@router.post("/stop")
async def stop_recording_endpoint(request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        await recording_service.stop()
        return returnsdata.success_msg(msg="Recording stopped successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to stop recording: {str(e)}", ERROR)

@router.post("/recording_status")
async def get_recording_status_endpoint(request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        recording_status = recording_service.get_service_status()
        return returnsdata.success(data=recording_status, msg="Recording status retrieved successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get recording status: {str(e)}", ERROR)


@router.post("/list")
async def get_radio_sessions_endpoint(request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        data = dict(await request.form())
        verify_admin_access(current_user)
        page = int(data.get("page", 1))
        per_page = int(data.get("per_page", 10))
        radio_sessions = await get_radio_sessions(db, data, page=page, per_page=per_page)
        return returnsdata.success(data=radio_sessions, msg="Radio sessions retrieved successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get radio sessions: {str(e)}", ERROR)


@router.post("/get/{session_id}")
async def get_radio_session_endpoint(session_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        radio_session = await get_radio_session_by_id(db, session_id)
        return returnsdata.success(data=radio_session, msg="Radio session retrieved successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to get radio session: {str(e)}", ERROR)


@router.post("/update/{session_id}")
async def update_radio_session_endpoint(session_id: str, request: Request, db: AsyncSession = Depends(get_database), current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        form_data = await request.form()
        data = dict(form_data)
        recording_file = data.pop('recording_file', None)
        updated_recording = await update_radio_session_recording(db, data, session_id, recording_file)
        return returnsdata.success(data=updated_recording, msg="Recording updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Update failed: {str(e)}", ERROR)

        
@router.post("/delete/{session_id}")
async def delete_radio_session_endpoint(session_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        success = await delete_radio_session(db, session_id)
        return returnsdata.success_msg(msg="Radio session deleted successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to delete radio session: {str(e)}", ERROR)


@router.post("/toggle-status/{session_id}")
async def toggle_radio_session_status_endpoint(session_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        verify_admin_access(current_user)
        radio_session = await toggle_radio_session_status(db, session_id)
        status_text = "activated" if radio_session['status'] else "deactivated"
        return returnsdata.success(data=radio_session, msg=f"Radio session {status_text} successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to toggle radio session status: {str(e)}", ERROR)


@router.post("/update-recording-status/{session_id}")
async def update_recording_status_endpoint(session_id: str,request: Request,db: AsyncSession = Depends(get_database),current_user = Depends(get_current_user_details)):
    try:
        data = dict(await request.form())
        verify_admin_access(current_user)
        
        recording_status = data.get("recording_status")
        if not recording_status:
            return returnsdata.error_msg("Recording status is required", ERROR)
        
        if recording_status not in ['scheduled', 'recording', 'completed', 'failed']:
            return returnsdata.error_msg("Invalid recording status", ERROR)
        
        radio_session = (db, data, session_id)
        return returnsdata.success(data=radio_session, msg="Recording status updated successfully", status=SUCCESS)
    except Exception as e:
        return returnsdata.error_msg(f"Failed to update recording status: {str(e)}", ERROR)