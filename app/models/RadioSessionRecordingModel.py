# RadioSessionRecordingModel.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, JSON, Integer, Float
from sqlalchemy.orm import relationship, backref
from sqlalchemy import delete, select, and_
from datetime import datetime
from app.models.BaseModel import Base
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import uuid

class RadioSessionRecording(Base):
    __tablename__ = "radio_session_recordings"
    
    # Foreign Keys
    station_id = Column(String(36), ForeignKey('stations.id'), nullable=False)
    program_id = Column(String(36), ForeignKey('radio_programs.id'), nullable=True)
    
    # Session Information
    session_date = Column(DateTime, nullable=False)  # Date of the recording
    day_of_week = Column(String(10), nullable=False)  # monday, tuesday, etc.
    scheduled_start_time = Column(DateTime, nullable=False)
    scheduled_end_time = Column(DateTime, nullable=False)
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)
    
    # Recording Details
    recording_status = Column(String(20), nullable=False, default='scheduled')  # scheduled, recording, completed, failed, cancelled
    stream_url = Column(String(500), nullable=True)  # Live stream URL being recorded
    recording_file_path = Column(String(500), nullable=True)  # Path to recorded file
    recording_file_url = Column(String(500), nullable=True)  # Public URL to access recording
    file_size_mb = Column(Float, nullable=True)  # File size in MB
    duration_minutes = Column(Integer, nullable=True)  # Actual recording duration
    
    # Technical Details
    audio_format = Column(String(10), nullable=False, default='mp3')  # mp3, wav, aac
    audio_quality = Column(String(20), nullable=False, default='128kbps')  # 64kbps, 128kbps, 256kbps, 320kbps
    recording_process_id = Column(String(100), nullable=True)  # System process ID for monitoring
    
    # Session Metadata from Schedule
    studio = Column(String(1), nullable=True)  # A, B, C, D
    hosts = Column(JSON, nullable=True)  # List of host IDs
    session_notes = Column(Text, nullable=True)
    is_live_session = Column(Boolean, default=True)
    is_repeat_session = Column(Boolean, default=False)
    
    # Error Handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Processing Status
    is_processed = Column(Boolean, default=False)  # Has been post-processed
    processing_status = Column(String(20), nullable=True)  # normalizing, uploading, completed
    
    # Additional Metadata
    recording_metadata = Column(JSON, nullable=True)  # Extra data like tags, thumbnails, etc.
    
    # Relationships
    station = relationship("Station", foreign_keys=[station_id])
    program = relationship("RadioProgram", foreign_keys=[program_id])
    
    async def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'station_id': self.station_id,
            'program_id': self.program_id,
            'session_date': self.session_date.isoformat() if self.session_date else None,
            'day_of_week': self.day_of_week,
            'scheduled_start_time': self.scheduled_start_time.isoformat() if self.scheduled_start_time else None,
            'scheduled_end_time': self.scheduled_end_time.isoformat() if self.scheduled_end_time else None,
            'actual_start_time': self.actual_start_time.isoformat() if self.actual_start_time else None,
            'actual_end_time': self.actual_end_time.isoformat() if self.actual_end_time else None,
            'recording_status': self.recording_status,
            'stream_url': self.stream_url,
            'recording_file_path': self.recording_file_path,
            'recording_file_url': self.recording_file_url,
            'file_size_mb': self.file_size_mb,
            'duration_minutes': self.duration_minutes,
            'audio_format': self.audio_format,
            'audio_quality': self.audio_quality,
            'recording_process_id': self.recording_process_id,
            'studio': self.studio,
            'hosts': self.hosts,
            'session_notes': self.session_notes,
            'is_live_session': self.is_live_session,
            'is_repeat_session': self.is_repeat_session,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'is_processed': self.is_processed,
            'processing_status': self.processing_status,
            'recording_metadata': self.recording_metadata,
            'status': self.status,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    async def to_dict_with_relations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.refresh(self, ['station', 'program'])
            data = await self.to_dict()
            
            if self.station:
                data['station'] = await self.station.to_dict()
            if self.program:
                data['program'] = await self.program.to_dict()

            show_hosts = await self.get_program_hosts(db, self.hosts)
            if show_hosts:
                data['hosts'] = show_hosts
            else:
                data['hosts'] = []
                
            return data
            
        except Exception as e:
            raise Exception(f"Failed to convert recording to dictionary with relations: {str(e)}")

    async def delete_with_relations(self, db: AsyncSession):
        try:
            from app.utils.file_upload import remove_file
            if self.recording_file_path:
                remove_file(self.recording_file_path)
            await db.execute(delete(RadioSessionRecording).where(RadioSessionRecording.id == self.id))
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to delete recording with relations: {str(e)}")


    async def get_program_hosts(self, db: AsyncSession, hosts_json: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            if not hosts_json or not isinstance(hosts_json, list):
                return []
                
            from app.models.HostModel import Host
            
            # Extract host IDs from the JSON structure
            hosts_ids = []
            for host in hosts_json:
                if isinstance(host, dict) and 'id' in host:
                    hosts_ids.append(host['id'])
                elif isinstance(host, str):  # In case IDs are stored as strings
                    hosts_ids.append(host)
            
            if not hosts_ids:
                return []
                
            stmt = select(Host).where(Host.id.in_(hosts_ids))
            result = await db.execute(stmt)
            hosts = result.scalars().all()
            
            # Convert to dictionaries - this is the key fix
            hosts_data = []
            for host in hosts:
                try:
                    host_dict = await host.to_dict() if hasattr(host, 'to_dict') else {
                        'id': host.id,
                        'name': getattr(host, 'name', ''),
                        'role': getattr(host, 'role', ''),
                        'email': getattr(host, 'email', ''),
                        'phone': getattr(host, 'phone', ''),
                        'image_url': getattr(host, 'image_url', ''),
                    }
                    hosts_data.append(host_dict)
                except Exception as e:
                    # If individual host conversion fails, skip it
                    print(f"Failed to convert host {host.id}: {e}")
                    continue
                    
            return hosts_data
            
        except Exception as e:
            print(f"Failed to get program hosts: {str(e)}")
            return []  # Return empty list instead of raising exception

    def get_recording_filename(self) -> str:
        if not self.session_date or not self.station:
            return f"recording_{self.id}.{self.audio_format}"
        
        date_str = self.session_date.strftime('%Y%m%d')
        time_str = self.scheduled_start_time.strftime('%H%M') if self.scheduled_start_time else '0000'
        station_name = self.station.name.replace(' ', '_').lower() if hasattr(self.station, 'name') else 'station'
        
        return f"{station_name}_{date_str}_{time_str}_{self.id}.{self.audio_format}"
    
    def is_currently_recording(self) -> bool:
        return self.recording_status == 'recording'
    
    def is_scheduled_now(self) -> bool:
        now = datetime.utcnow()
        return (self.scheduled_start_time <= now <= self.scheduled_end_time and 
                self.recording_status == 'scheduled')
    
    def should_start_recording(self) -> bool:
        now = datetime.utcnow()
        return (now >= self.scheduled_start_time and 
                self.recording_status == 'scheduled' and
                self.is_live_session)
    
    def should_stop_recording(self) -> bool:
        now = datetime.utcnow()
        return (now >= self.scheduled_end_time and 
                self.recording_status == 'recording')
    
    def calculate_expected_duration(self) -> int:
        if not self.scheduled_start_time or not self.scheduled_end_time:
            return 0
        
        delta = self.scheduled_end_time - self.scheduled_start_time
        return int(delta.total_seconds() / 60)
    
    def get_recording_quality_settings(self) -> Dict[str, Any]:
        quality_settings = {
            '64kbps': {'bitrate': '64k', 'sample_rate': '22050'},
            '128kbps': {'bitrate': '128k', 'sample_rate': '44100'},
            '256kbps': {'bitrate': '256k', 'sample_rate': '44100'},
            '320kbps': {'bitrate': '320k', 'sample_rate': '44100'},
        }
        
        return quality_settings.get(self.audio_quality, quality_settings['128kbps'])

# Recording status enum for reference
RECORDING_STATUSES = {
    'scheduled': 'Scheduled for recording',
    'recording': 'Currently recording',
    'completed': 'Recording completed successfully',
    'failed': 'Recording failed',
    'cancelled': 'Recording cancelled',
    'processing': 'Post-processing recording',
    'ready': 'Recording ready for playback'
}

# Processing status enum
PROCESSING_STATUSES = {
    'pending': 'Waiting to be processed',
    'normalizing': 'Normalizing audio levels',
    'uploading': 'Uploading to storage',
    'generating_thumbnails': 'Creating thumbnails/previews',
    'completed': 'Processing completed',
    'failed': 'Processing failed'
}