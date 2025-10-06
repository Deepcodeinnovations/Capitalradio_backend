from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, or_
from datetime import datetime
from typing import Dict, Any, Optional
from app.utils.file_upload import save_upload_file, remove_file
from app.models.RadioSessionRecordingModel import RadioSessionRecording
from app.utils.advanced_paginator import paginate_query, QueryOptimizer
import math
import os
import json




async def get_radio_sessions(db: AsyncSession, data: Dict[str, Any], page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    try:
        query = select(RadioSessionRecording).where(and_(RadioSessionRecording.state == True))
        
        # Apply filters using QueryOptimizer
        filters = {}
        if data.get('station_id'): filters['station_id'] = data['station_id']
        if data.get('program_id'): filters['program_id'] = data['program_id']
        if data.get('day_of_week'): filters['day_of_week'] = data['day_of_week']
        if data.get('recording_status'): filters['recording_status'] = data['recording_status']
        
        query = QueryOptimizer.add_multiple_filters(query, RadioSessionRecording, filters)
        
        # Handle session_date filter separately
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


async def get_radio_session_by_id(db: AsyncSession, session_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(RadioSessionRecording).where(and_(RadioSessionRecording.id == session_id, RadioSessionRecording.state == True)))
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="Radio session not found")
            
        return await session.to_dict_with_relations(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get radio session: {str(e)}")



async def update_radio_session_recording(db: AsyncSession, data: Dict[str, Any], session_id: str, recording_file: Optional[UploadFile] = None) -> Dict[str, Any]:
    try:
        result = await db.execute(select(RadioSessionRecording).where(and_(RadioSessionRecording.id == session_id, RadioSessionRecording.state == True)))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        # Handle file upload
        if recording_file and recording_file.filename:
            if session.recording_file_path:
                remove_file(session.recording_file_path)
            file_path, file_url = await save_upload_file(recording_file, "recordings/sessions")
            session.recording_file_path = file_path
            session.recording_file_url = file_url
            if os.path.exists(file_path):
                session.file_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
        
        # Handle status timestamps
        if data.get('recording_status') == 'recording' and not session.actual_start_time:
            session.actual_start_time = datetime.utcnow()
        elif data.get('recording_status') in ['completed', 'failed'] and not session.actual_end_time:
            session.actual_end_time = datetime.utcnow()
            if session.actual_start_time:
                session.duration_minutes = int((session.actual_end_time - session.actual_start_time).total_seconds() / 60)
        
        session.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(session)
        return await session.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")




async def delete_radio_session(db: AsyncSession, session_id: str) -> bool:
    try:
        result = await db.execute(select(RadioSessionRecording).where(and_(RadioSessionRecording.id == session_id, RadioSessionRecording.state == True)))
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="Radio session not found")
        
        await session.delete_with_relations(db)
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete radio session: {str(e)}")


async def toggle_radio_session_status(db: AsyncSession, session_id: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(RadioSessionRecording).where(and_(RadioSessionRecording.id == session_id, RadioSessionRecording.state == True)))
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="Radio session not found")
        
        session.status = not session.status
        session.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(session)
        return await session.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to toggle radio session status: {str(e)}")


async def update_radio_session_recording_status(db: AsyncSession, session_id: str, recording_status: str) -> Dict[str, Any]:
    try:
        result = await db.execute(select(RadioSessionRecording).where(and_(RadioSessionRecording.id == session_id, RadioSessionRecording.state == True)))
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="Radio session not found")
        
        session.recording_status = recording_status
        session.updated_at = datetime.utcnow()
        
        # Update timestamps based on status
        if recording_status == 'recording' and not session.actual_start_time:
            session.actual_start_time = datetime.utcnow()
        elif recording_status == 'completed' and not session.actual_end_time:
            session.actual_end_time = datetime.utcnow()
        
        await db.commit()
        await db.refresh(session)
        return await session.to_dict_with_relations(db)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update recording status: {str(e)}")