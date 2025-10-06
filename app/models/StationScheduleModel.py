# StationScheduleModel.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, JSON, select
from sqlalchemy.orm import relationship, backref
from datetime import datetime
from app.models.BaseModel import Base
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
import uuid

class StationSchedule(Base):
    __tablename__ = "station_schedules"
    station_id = Column(String(36), ForeignKey('stations.id'), nullable=False, unique=True)
    sessions = Column(JSON, nullable=False, default=lambda: {
        "sunday": [],
        "monday": [],
        "tuesday": [],
        "wednesday": [],
        "thursday": [],
        "friday": [],
        "saturday": []
    })

    notes = Column(Text, nullable=True)
    station = relationship("Station", back_populates="schedule")
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'station_id': self.station_id,
            'sessions': self.sessions,
            'notes': self.notes,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            from app.models.RadioProgramModel import RadioProgram
            
            await db.refresh(self, ['station'])
            data = await self.to_dict()
            
            if self.station:
                data['station'] = await self.station.to_dict()
            
            # Fetch programs for all sessions
            sessions_with_programs = {}
            for day, day_sessions in self.sessions.items():
                sessions_with_programs[day] = []
                for session in day_sessions:
                    session_with_program = session.copy()
                    if 'program_id' in session:
                        program = await self._get_program_by_id(db, session['program_id'])
                        session_with_program['program'] = await program.to_dict_with_relations(db) if program else None
                    sessions_with_programs[day].append(session_with_program)
            
            data['sessions'] = sessions_with_programs
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert schedule to dictionary with relations: {str(e)}")

    async def _get_program_by_id(self, db: AsyncSession, program_id: str) -> Optional['RadioProgram']:
        try:
            from app.models.RadioProgramModel import RadioProgram
            result = await db.execute(select(RadioProgram).where(RadioProgram.id == program_id))
            return result.scalar_one_or_none()
        except Exception:
            return None

    async def get_sessions_with_programs(self, db: AsyncSession) -> Dict[str, List[Dict[str, Any]]]:
        """Get all sessions with their associated program data"""
        sessions_with_programs = {}
        
        for day, day_sessions in self.sessions.items():
            sessions_with_programs[day] = []
            for session in day_sessions:
                session_data = session.copy()
                if 'program_id' in session:
                    program = await self._get_program_by_id(db, session['program_id'])
                    session_data['program'] = await program.to_dict() if program else None
                sessions_with_programs[day].append(session_data)
        
        return sessions_with_programs

    async def get_current_session(self, db: AsyncSession, day: str, current_time: str) -> Optional[Dict[str, Any]]:
        """Get the current session for a specific day and time"""
        if day not in self.sessions:
            return None
        
        for session in self.sessions[day]:
            start_time = session.get('start_time')
            end_time = session.get('end_time')
            
            if start_time and end_time and start_time <= current_time <= end_time:
                session_data = session.copy()
                if 'program_id' in session:
                    program = await self._get_program_by_id(db, session['program_id'])
                    session_data['program'] = await program.to_dict() if program else None
                return session_data
        
        return None

    async def get_day_sessions_with_programs(self, db: AsyncSession, day: str) -> List[Dict[str, Any]]:
        """Get all sessions for a specific day with program data"""
        if day not in self.sessions:
            return []
        
        sessions_with_programs = []
        for session in self.sessions[day]:
            session_data = session.copy()
            if 'program_id' in session:
                program = await self._get_program_by_id(db, session['program_id'])
                session_data['program'] = await program.to_dict() if program else None
            sessions_with_programs.append(session_data)
        
        return sessions_with_programs

    @classmethod
    def get_empty_sessions(cls) -> Dict[str, List]:
        return {
            "sunday": [],
            "monday": [],
            "tuesday": [],
            "wednesday": [],
            "thursday": [],
            "friday": [],
            "saturday": []
        }

    def validate_sessions(self) -> Dict[str, Any]:
        errors = []
        warnings = []
        
        if not isinstance(self.sessions, dict):
            errors.append("Sessions must be a dictionary")
            return {"valid": False, "errors": errors, "warnings": warnings}
        
        required_days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        
        for day in required_days:
            if day not in self.sessions:
                errors.append(f"Missing day: {day}")
                continue
                
            if not isinstance(self.sessions[day], list):
                errors.append(f"{day} must be a list")
                continue
            
            # Check each session in the day
            day_sessions = self.sessions[day]
            for i, session in enumerate(day_sessions):
                session_errors = self._validate_session(session, day, i)
                errors.extend(session_errors)
            
            # Check for time conflicts within the day
            conflicts = self._check_day_conflicts(day_sessions, day)
            warnings.extend(conflicts)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_session(self, session: Dict, day: str, index: int) -> List[str]:
        errors = []
        required_fields = ["program_id", "start_time", "end_time"]
        
        for field in required_fields:
            if field not in session:
                errors.append(f"{day}[{index}]: Missing {field}")
        
        # Validate time format
        if "start_time" in session:
            if not self._is_valid_time(session["start_time"]):
                errors.append(f"{day}[{index}]: Invalid start_time format (use HH:MM)")
        
        if "end_time" in session:
            if not self._is_valid_time(session["end_time"]):
                errors.append(f"{day}[{index}]: Invalid end_time format (use HH:MM)")
        
        # Validate start_time < end_time
        if "start_time" in session and "end_time" in session:
            if session["start_time"] >= session["end_time"]:
                errors.append(f"{day}[{index}]: start_time must be before end_time")
        
        return errors
    
    def _check_day_conflicts(self, sessions: List[Dict], day: str) -> List[str]:
        conflicts = []
        
        for i, session1 in enumerate(sessions):
            for j, session2 in enumerate(sessions[i+1:], i+1):
                if self._sessions_overlap(session1, session2):
                    conflicts.append(
                        f"{day}: Session {i+1} ({session1.get('start_time')}-{session1.get('end_time')}) "
                        f"conflicts with Session {j+1} ({session2.get('start_time')}-{session2.get('end_time')})"
                    )
        
        return conflicts
    
    def _sessions_overlap(self, session1: Dict, session2: Dict) -> bool:
        start1 = session1.get("start_time")
        end1 = session1.get("end_time")
        start2 = session2.get("start_time")
        end2 = session2.get("end_time")
        
        if not all([start1, end1, start2, end2]):
            return False
        
        return (start1 < end2) and (start2 < end1)
    
    def _is_valid_time(self, time_str: str) -> bool:
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return False
            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except:
            return False

    async def get_session_program(self, db: AsyncSession, program_id: str) -> Optional[Dict[str, Any]]:
        for day, day_sessions in self.sessions.items():
            for session in day_sessions:
                if session.get("program_id") == program_id:
                    session_data = session.copy()
                    program = await self._get_program_by_id(db, program_id)
                    session_data['program'] = await program.to_dict_with_relations(db) if program else None
                    return session_data
        return None