import asyncio
import subprocess
import os
import signal
import platform
import uuid
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import logging
import io
import pytz
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, UploadFile
from app.models.RadioSessionRecordingModel import RadioSessionRecording
from app.models.StationModel import Station
from app.models.StationScheduleModel import StationSchedule
from app.models.RadioProgramModel import RadioProgram
from app.database import get_database
from app.utils.file_upload import save_upload_file

# Import system validation components
from app.utils.system_validation import SystemValidator, ValidationResult, SystemInfo

logger = logging.getLogger(__name__)

class EnhancedStationRecordingService:
    def __init__(self):
        # Core service properties
        self.station_tasks = {}
        self.recording_processes = {}
        self.base_recording_path = os.getenv("RECORDING_BASE_PATH", "./temp_recordings")
        self.recording_format = "mp3"
        self.check_interval = 5
        
        # File handling configuration
        self.max_file_access_retries = 10
        self.base_retry_delay = 0.5  # seconds
        self.max_retry_delay = 30.0  # seconds
        self.windows_file_delay = 2.0  # Extra delay for Windows file handle cleanup
        self.process_cleanup_timeout = 20.0  # seconds
        
        # Validation and system info
        self.system_info: Optional[SystemInfo] = None
        self.validation_result: Optional[ValidationResult] = None
        self._startup_time: Optional[datetime] = None
        self._is_validated = False
        
        # Platform detection
        self.platform_system = platform.system().lower()
        self.is_windows = self.platform_system == 'windows'
        self.is_linux = self.platform_system == 'linux'
        self.is_mac = self.platform_system == 'darwin'
        
        # Initialize system validator
        self.validator = SystemValidator(
            recording_path=self.base_recording_path,
            min_disk_gb=5.0
        )
        
        logger.info(f"Enhanced Recording Service - Platform: {self.platform_system}")
        logger.info(f"File handling config - Max retries: {self.max_file_access_retries}, Windows delay: {self.windows_file_delay}s")
    
    async def validate_and_start(self):
        """Validate system requirements and start the recording service"""
        logger.info("🎙️ Starting Enhanced Station Recording Service with System Validation")
        
        try:
            # Step 1: System Validation using SystemValidator
            logger.info("Step 1: Performing comprehensive system validation...")
            self.validation_result = await self.validator.validate_system()
            
            # Print validation report
            self.validator.print_validation_report(self.validation_result)
            
            # Check if validation passed
            if not self.validation_result.is_valid:
                logger.error("❌ System validation failed. Recording service cannot start.")
                raise SystemExit("System validation failed - see report above")
            
            if self.validation_result.warnings:
                logger.warning(f"⚠️ System validation passed with {len(self.validation_result.warnings)} warnings")
            
            self.system_info = self.validation_result.system_info
            self._is_validated = True
            
            # Step 2: Initialize recording directory with validated path
            Path(self.base_recording_path).mkdir(parents=True, exist_ok=True)
            
            # Step 3: Start the recording service
            logger.info("Step 2: Starting recording service...")
            await self.start()
            
            self._startup_time = datetime.now(pytz.timezone('Africa/Nairobi'))
            logger.info("✅ Enhanced Recording Service started successfully!")
            logger.info(f"Service started at: {self._startup_time}")
            logger.info(f"Platform: {self.system_info.platform}")
            logger.info(f"FFmpeg: {self.system_info.ffmpeg_version}")
            logger.info(f"Timezone: {self.system_info.timezone}")
            
        except Exception as e:
            logger.error(f"❌ Failed to start recording service: {str(e)}")
            raise
    
    def _get_process_creation_kwargs(self):
        kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
        if self.is_windows:
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['preexec_fn'] = os.setsid
        return kwargs
    
    async def _is_process_running(self, process: subprocess.Popen) -> bool:
        """Check if process is still running"""
        try:
            return process.poll() is None
        except:
            return False
    
    async def _wait_for_process_cleanup(self, process: subprocess.Popen, timeout: float = None) -> bool:
        """Wait for process to fully cleanup with timeout"""
        if timeout is None:
            timeout = self.process_cleanup_timeout
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not await self._is_process_running(process):
                # Additional delay for Windows file handle cleanup
                if self.is_windows:
                    await asyncio.sleep(self.windows_file_delay)
                return True
            await asyncio.sleep(0.1)
        return False
    
    def _terminate_process(self, process):
        """Gracefully terminate process with platform-specific handling"""
        try:
            if not process or process.poll() is not None:
                return True
                
            logger.info(f"🛑 Terminating process PID: {process.pid}")
            
            if self.is_windows:
                process.terminate()
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            return True
        except ProcessLookupError:
            logger.debug("Process already terminated")
            return True
        except Exception as e:
            logger.warning(f"Graceful termination failed: {str(e)}")
            return False
    
    def _force_kill_process(self, process):
        """Force kill process with platform-specific handling"""
        try:
            if not process or process.poll() is not None:
                return True
                
            logger.warning(f"🔥 Force killing process PID: {process.pid}")
            
            if self.is_windows:
                process.kill()
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            return True
        except ProcessLookupError:
            logger.debug("Process already killed")
            return True
        except Exception as e:
            logger.error(f"Force kill failed: {str(e)}")
            return False
    
    async def _is_file_locked(self, file_path: str) -> bool:
        """Check if file is locked by another process"""
        try:
            # Try to open file in read+write mode
            with open(file_path, 'r+b'):
                return False
        except (PermissionError, IOError):
            return True
        except FileNotFoundError:
            return False  # File doesn't exist, so not locked
    
    async def _wait_for_file_unlock(self, file_path: str, max_retries: int = None, base_delay: float = None) -> bool:
        """Wait for file to be unlocked with exponential backoff retry"""
        if max_retries is None:
            max_retries = self.max_file_access_retries
        if base_delay is None:
            base_delay = self.base_retry_delay
            
        if not os.path.exists(file_path):
            logger.warning(f"File does not exist: {file_path}")
            return False
            
        for attempt in range(max_retries):
            if not await self._is_file_locked(file_path):
                logger.info(f"✅ File unlocked after {attempt + 1} attempts: {os.path.basename(file_path)}")
                return True
                
            delay = min(base_delay * (2 ** attempt), self.max_retry_delay)
            logger.info(f"🔄 File locked, retry {attempt + 1}/{max_retries} in {delay:.1f}s: {os.path.basename(file_path)}")
            await asyncio.sleep(delay)
        
        logger.error(f"❌ File remains locked after {max_retries} attempts: {file_path}")
        return False
    
    async def _safe_file_read(self, file_path: str) -> Tuple[bool, Optional[bytes], str]:
        """Safely read file with retry mechanism and detailed error reporting"""
        if not os.path.exists(file_path):
            return False, None, f"File does not exist: {file_path}"
        
        # Check file size
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return False, None, f"File is empty: {file_path}"
            logger.info(f"📁 Reading file: {os.path.basename(file_path)} ({file_size / (1024*1024):.2f}MB)")
        except Exception as e:
            return False, None, f"Cannot get file size: {str(e)}"
        
        # Wait for file to be unlocked
        if not await self._wait_for_file_unlock(file_path):
            return False, None, f"File remains locked after retries: {file_path}"
        
        # Try to read file with retries
        for attempt in range(self.max_file_access_retries):
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                logger.info(f"✅ File read successfully: {os.path.basename(file_path)} ({len(content)} bytes)")
                return True, content, "Success"
            except (PermissionError, IOError) as e:
                delay = min(self.base_retry_delay * (2 ** attempt), self.max_retry_delay)
                logger.warning(f"⚠️ File read attempt {attempt + 1} failed: {str(e)}, retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
            except Exception as e:
                return False, None, f"Unexpected error reading file: {str(e)}"
        
        return False, None, f"Failed to read file after {self.max_file_access_retries} attempts"
    
    async def _safe_file_delete(self, file_path: str) -> Tuple[bool, str]:
        """Safely delete file with retry mechanism"""
        if not os.path.exists(file_path):
            return True, "File already deleted"
        
        # Wait for file to be unlocked
        if not await self._wait_for_file_unlock(file_path):
            return False, f"Cannot delete locked file: {file_path}"
        
        # Try to delete file with retries
        for attempt in range(self.max_file_access_retries):
            try:
                os.remove(file_path)
                logger.info(f"🗑️ File deleted successfully: {os.path.basename(file_path)}")
                return True, "File deleted successfully"
            except (PermissionError, IOError) as e:
                delay = min(self.base_retry_delay * (2 ** attempt), self.max_retry_delay)
                logger.warning(f"⚠️ File delete attempt {attempt + 1} failed: {str(e)}, retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
            except Exception as e:
                return False, f"Unexpected error deleting file: {str(e)}"
        
        return False, f"Failed to delete file after {self.max_file_access_retries} attempts"
    
    def _add_seconds_to_time(self, time_str: str, seconds: int) -> str:
        try:
            hour, minute = map(int, time_str.split(':'))
            dt = datetime.now().replace(hour=hour, minute=minute, second=0)
            new_dt = dt + timedelta(seconds=seconds)
            return new_dt.strftime('%H:%M')
        except:
            return time_str
    
    def _time_to_seconds(self, time_str: str) -> int:
        try:
            hour, minute = map(int, time_str.split(':'))
            return hour * 3600 + minute * 60
        except:
            return 0
    
    def _get_current_session(self, schedule: StationSchedule) -> Optional[Dict]:
        # Use Nairobi timezone for session calculations
        nairobi_tz = pytz.timezone('Africa/Nairobi')
        now = datetime.now(nairobi_tz)
        day_name = now.strftime('%A').lower()
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        
        if not schedule or not schedule.sessions or day_name not in schedule.sessions:
            return None
        
        for session in schedule.sessions[day_name]:
            start_time = session.get('start_time')
            end_time = session.get('end_time')
            
            if start_time and end_time:
                start_seconds = self._time_to_seconds(start_time)
                end_seconds = self._time_to_seconds(end_time)
                
                if end_seconds <= start_seconds:
                    end_seconds += 24 * 3600
                
                if start_seconds <= current_seconds <= end_seconds:
                    return session
        return None
    
    def _should_start_recording(self, session: Dict) -> bool:
        # Use Nairobi timezone
        nairobi_tz = pytz.timezone('Africa/Nairobi')
        now = datetime.now(nairobi_tz)
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        start_seconds = self._time_to_seconds(session.get('start_time', '00:00'))
        
        return current_seconds >= start_seconds
    
    def _should_stop_recording(self, session: Dict) -> bool:
        # Use Nairobi timezone
        nairobi_tz = pytz.timezone('Africa/Nairobi')
        now = datetime.now(nairobi_tz)
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        end_seconds = self._time_to_seconds(session.get('end_time', '23:59'))
        
        return current_seconds >= end_seconds
    
    async def start(self):
        """Start the recording service (internal method, use validate_and_start() instead)"""
        if not self._is_validated:
            logger.warning("Service starting without validation! Consider using validate_and_start() instead.")
        
        logger.info("Starting Enhanced Station Recording Service")
        db = get_database()
        try:
            db_session = await db.__anext__()
            stations = await self._get_active_stations(db_session)
            logger.info(f"Found {len(stations)} active stations")
            for station in stations:
                await self._start_station_task(station)
        finally:
            await db.aclose()
    
    async def stop(self):
        logger.info("🛑 Stopping Enhanced Recording Service - Graceful shutdown initiated")
        
        # Step 1: Stop all active recordings gracefully
        active_recordings = list(self.recording_processes.keys())
        if active_recordings:
            logger.info(f"Step 1: Stopping {len(active_recordings)} active recordings...")
            
            for recording_key in active_recordings:
                logger.info(f"Stopping recording: {recording_key}")
                db = get_database()
                try:
                    db_session = await db.__anext__()
                    await self._stop_session_recording(db_session, recording_key)
                    logger.info(f"✅ Recording stopped and saved: {recording_key}")
                except Exception as e:
                    logger.error(f"❌ Error stopping recording {recording_key}: {str(e)}")
                finally:
                    await db.aclose()
            
            logger.info(f"✅ All {len(active_recordings)} recordings have been stopped and saved")
        else:
            logger.info("No active recordings to stop")
        
        # Step 2: Cancel all station tasks
        station_tasks = list(self.station_tasks.items())
        if station_tasks:
            logger.info(f"Step 2: Cancelling {len(station_tasks)} station tasks...")
            
            for station_id, task in station_tasks:
                logger.info(f"Cancelling station task: {station_id}")
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=10.0)  # Give 10 seconds for graceful cancellation
                except asyncio.CancelledError:
                    logger.info(f"✅ Station task {station_id} cancelled successfully")
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Station task {station_id} cancellation timed out")
                except Exception as e:
                    logger.error(f"❌ Error cancelling station task {station_id}: {str(e)}")
            
            logger.info(f"✅ All {len(station_tasks)} station tasks have been cancelled")
        else:
            logger.info("No station tasks to cancel")
        
        # Step 3: Clear all tracking data
        self.station_tasks.clear()
        self.recording_processes.clear()
        
        # Step 4: Log final status and uptime
        if self._startup_time:
            uptime = datetime.now(pytz.timezone('Africa/Nairobi')) - self._startup_time
            logger.info(f"📊 Service uptime: {uptime}")
            logger.info(f"🕒 Service stopped at: {datetime.now(pytz.timezone('Africa/Nairobi'))}")
        
        logger.info("✅ Enhanced Recording Service stopped successfully - All recordings saved and completed")
    
    async def _get_active_stations(self, db: AsyncSession) -> List[Station]:
        try:
            result = await db.execute(
                select(Station).where(and_(Station.status == True, Station.state == True))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching active stations: {str(e)}")
            return []
    
    async def _start_station_task(self, station: Station):
        if station.id in self.station_tasks:
            old_task = self.station_tasks[station.id]
            old_task.cancel()
            try:
                await old_task
            except asyncio.CancelledError:
                pass
        
        task = asyncio.create_task(
            self._station_recording_loop(station.id),
            name=f"station_recording_{station.id}"
        )
        self.station_tasks[station.id] = task
        logger.info(f"Started recording task for: {station.name}")
    
    async def _station_recording_loop(self, station_id: str):
        logger.info(f"Recording loop started for station: {station_id}")
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                db = get_database()
                try:
                    db_session = await db.__anext__()
                    station = await self._get_station(db_session, station_id)
                    if not station or not station.status or not station.state:
                        logger.warning(f"Station {station_id} is inactive, stopping loop")
                        break
                    
                    schedule = await self._get_station_schedule(db_session, station_id)
                    if not schedule:
                        await asyncio.sleep(self.check_interval)
                        continue
                    
                    current_session = self._get_current_session(schedule)
                    if current_session:
                        # Use Nairobi timezone for session date
                        nairobi_tz = pytz.timezone('Africa/Nairobi')
                        session_date = datetime.now(nairobi_tz).strftime('%Y%m%d')
                        recording_key = f"{station_id}_{session_date}_{current_session['start_time'].replace(':', '')}"
                        
                        if (self._should_start_recording(current_session) and 
                            recording_key not in self.recording_processes):
                            logger.info(f"Starting recording for session: {current_session['start_time']}-{current_session['end_time']} on {station.name}")
                            await self._start_session_recording(db_session, station, current_session, recording_key)
                        
                        if (recording_key in self.recording_processes and 
                            self._should_stop_recording(current_session)):
                            logger.info(f"Stopping recording for session: {current_session['start_time']}-{current_session['end_time']} on {station.name}")
                            await self._stop_session_recording(db_session, recording_key)
                            
                            await asyncio.sleep(30)
                
                finally:
                    await db.aclose()
                
                # Reset error counter on successful iteration
                consecutive_errors = 0
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info(f"Station {station_id} task cancelled")
                await self._save_station_recordings_on_shutdown(station_id)
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in station {station_id} loop (attempt {consecutive_errors}): {str(e)}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors for station {station_id}, stopping loop")
                    break
                
                # Exponential backoff
                backoff_delay = min(self.check_interval * (2 ** consecutive_errors), 300)
                await asyncio.sleep(backoff_delay)
    
    async def _get_station(self, db: AsyncSession, station_id: str) -> Optional[Station]:
        try:
            result = await db.execute(select(Station).where(Station.id == station_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching station {station_id}: {str(e)}")
            return None
    
    async def _get_station_schedule(self, db: AsyncSession, station_id: str) -> Optional[StationSchedule]:
        try:
            result = await db.execute(
                select(StationSchedule).where(
                    and_(StationSchedule.station_id == station_id, StationSchedule.state == True)
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching schedule for station {station_id}: {str(e)}")
            return None
    
    async def _get_program(self, db: AsyncSession, program_id: str) -> Optional[RadioProgram]:
        if not program_id:
            return None
        try:
            result = await db.execute(select(RadioProgram).where(RadioProgram.id == program_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching program {program_id}: {str(e)}")
            return None
    
    async def _generate_filename(self, station: Station, program: Optional[RadioProgram], session: Dict) -> str:
        """Generate unique recording filename to prevent conflicts"""
        def sanitize_name(name: str) -> str:
            return ''.join(c for c in name if c.isalnum() or c in '-_').lower()
        
        station_name = sanitize_name(station.name)
        program_name = sanitize_name(program.title) if program else 'unknown_program'
        
        # Use Nairobi timezone for filename
        nairobi_tz = pytz.timezone('Africa/Nairobi')
        now = datetime.now(nairobi_tz)
        date_str = now.strftime('%Y%m%d')
        start_time = session.get('start_time', '0000').replace(':', '')
        
        # Add unique identifier to prevent filename conflicts
        unique_id = str(uuid.uuid4())[:8]
        timestamp = now.strftime('%H%M%S')
        
        filename = f"{station_name}_{program_name}_{date_str}_{start_time}_{timestamp}_{unique_id}.{self.recording_format}"
        logger.info(f"📝 Generated unique filename: {filename}")
        return filename
    
    async def _start_session_recording(self, db: AsyncSession, station: Station, session: Dict, recording_key: str):
        try:
            program = await self._get_program(db, session.get('program_id'))
            filename = await self._generate_filename(station, program, session)
            file_path = os.path.join(self.base_recording_path, filename)
            
            recording_entry = await self._create_recording_entry(db, station, session, file_path)
            logger.info(f"Created recording entry: {recording_entry.id}")
            
            process = await self._start_ffmpeg_recording(station.streaming_link, file_path)
            if process:
                self.recording_processes[recording_key] = {
                    'process': process,
                    'recording_id': recording_entry.id,
                    'file_path': file_path,
                    'start_time': datetime.now(pytz.timezone('Africa/Nairobi')),
                    'session': session
                }
                logger.info(f"Recording started: {station.name} - {filename} (PID: {process.pid})")
            else:
                recording_entry.recording_status = 'failed'
                recording_entry.error_message = 'Failed to start FFmpeg process'
                recording_entry.actual_end_time = datetime.now(pytz.timezone('Africa/Nairobi'))
                await db.commit()
                logger.error(f"Failed to start FFmpeg for {station.name}")
            
        except Exception as e:
            logger.error(f"Failed to start recording for {station.name}: {str(e)}")
    
    async def _create_recording_entry(self, db: AsyncSession, station: Station, session: Dict, file_path: str) -> RadioSessionRecording:
        # Use Nairobi timezone for all datetime operations
        nairobi_tz = pytz.timezone('Africa/Nairobi')
        now = datetime.now(nairobi_tz)
        session_date = now.date()
        
        start_time_str = session.get('start_time', '00:00')
        end_time_str = session.get('end_time', '23:59')
        
        try:
            start_time = datetime.combine(session_date, datetime.strptime(start_time_str, '%H:%M').time())
            end_time = datetime.combine(session_date, datetime.strptime(end_time_str, '%H:%M').time())
            
            # Apply Nairobi timezone
            start_time = nairobi_tz.localize(start_time)
            end_time = nairobi_tz.localize(end_time)
            
            if end_time <= start_time:
                end_time += timedelta(days=1)
        except ValueError as e:
            logger.warning(f"Invalid time format in session: {str(e)}")
            start_time = now
            end_time = now + timedelta(hours=1)
        
        recording = RadioSessionRecording(
            station_id=station.id,
            program_id=session.get('program_id'),
            session_date=session_date,
            day_of_week=now.strftime('%A').lower(),
            scheduled_start_time=start_time,
            scheduled_end_time=end_time,
            actual_start_time=now,
            recording_status='recording',
            stream_url=station.streaming_link,
            recording_file_path=file_path,
            audio_format=self.recording_format,
            audio_quality='128kbps',
            studio=session.get('studio', 'A'),
            hosts=session.get('hosts', []),
            session_notes=session.get('notes', ''),
            is_live_session=session.get('is_live', True),
            is_repeat_session=session.get('is_repeat', False),
            status=True,
            state=True
        )
        
        db.add(recording)
        await db.commit()
        await db.refresh(recording)
        return recording
    
    async def _start_ffmpeg_recording(self, stream_url: str, output_path: str) -> Optional[subprocess.Popen]:
        try:
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', stream_url,
                '-reconnect', '1',
                '-reconnect_streamed', '1',
                '-reconnect_delay_max', '30',
                '-timeout', '30000000',
                '-acodec', 'libmp3lame',
                '-ab', '128k',
                '-ar', '44100',
                '-ac', '2',
                '-y',
                '-loglevel', 'warning',
                output_path
            ]
            
            process_kwargs = self._get_process_creation_kwargs()
            logger.info(f"Starting FFmpeg on {self.platform_system}")
            
            process = subprocess.Popen(ffmpeg_cmd, **process_kwargs)
            
            await asyncio.sleep(3)
            if process.poll() is None:
                logger.info(f"FFmpeg started successfully (PID: {process.pid})")
                return process
            else:
                stderr_output = process.stderr.read().decode() if process.stderr else "Unknown error"
                logger.error(f"FFmpeg failed: {stderr_output}")
                return None
            
        except FileNotFoundError:
            logger.error("FFmpeg not found - Please install FFmpeg")
            return None
        except Exception as e:
            logger.error(f"FFmpeg start error: {str(e)}")
            return None
    
    async def _stop_session_recording(self, db: AsyncSession, recording_key: str):
        if recording_key not in self.recording_processes:
            logger.warning(f"Recording key {recording_key} not found in active processes")
            return
        
        recording_data = self.recording_processes[recording_key]
        process = recording_data['process']
        
        logger.info(f"🛑 Stopping recording: {recording_key}")
        
        try:
            # Step 1: Gracefully terminate the FFmpeg process
            logger.info(f"Terminating FFmpeg process (PID: {process.pid})")
            self._terminate_process(process)
            
            # Step 2: Wait for process to terminate gracefully with extended timeout
            logger.info(f"⏳ Waiting for process cleanup (timeout: {self.process_cleanup_timeout}s)")
            process_cleaned = await self._wait_for_process_cleanup(process)
            
            if not process_cleaned:
                logger.warning("⚠️ Graceful termination timed out, force killing FFmpeg process")
                self._force_kill_process(process)
                
                # Wait additional time for force kill cleanup
                await asyncio.sleep(self.windows_file_delay if self.is_windows else 1.0)
                
                # Final verification
                if await self._is_process_running(process):
                    logger.error("❌ Process still running after force kill")
                else:
                    logger.info("✅ Process force killed successfully")
            else:
                logger.info("✅ FFmpeg process terminated gracefully")
        
        except Exception as e:
            logger.error(f"❌ Error stopping process: {str(e)}")
            self._force_kill_process(process)
            await asyncio.sleep(self.windows_file_delay if self.is_windows else 1.0)
        
        # Step 3: Finalize and save the recording with enhanced error handling
        try:
            logger.info(f"💾 Finalizing and saving recording: {recording_key}")
            await self._finalize_recording(db, recording_data)
            logger.info(f"✅ Recording finalized successfully: {recording_key}")
        except Exception as finalize_error:
            logger.error(f"❌ Error finalizing recording {recording_key}: {str(finalize_error)}")
            # Try to mark as failed in database
            try:
                await self._mark_recording_as_failed(db, recording_data, str(finalize_error))
            except Exception as mark_error:
                logger.error(f"❌ Failed to mark recording as failed: {str(mark_error)}")
        
        # Step 4: Remove from active processes
        try:
            del self.recording_processes[recording_key]
            logger.info(f"✅ Recording removed from active processes: {recording_key}")
        except KeyError:
            logger.warning(f"⚠️ Recording key {recording_key} already removed from processes")
    
    async def _mark_recording_as_failed(self, db: AsyncSession, recording_data: Dict, error_message: str):
        """Mark recording as failed in database"""
        try:
            recording_id = recording_data['recording_id']
            actual_start_time = recording_data['start_time']
            
            result = await db.execute(
                select(RadioSessionRecording).where(RadioSessionRecording.id == recording_id)
            )
            recording = result.scalar_one_or_none()
            
            if recording:
                nairobi_tz = pytz.timezone('Africa/Nairobi')
                actual_end_time = datetime.now(nairobi_tz)
                actual_duration_minutes = (actual_end_time - actual_start_time).total_seconds() / 60
                
                recording.recording_status = 'failed'
                recording.error_message = error_message
                recording.actual_end_time = actual_end_time
                recording.duration_minutes = round(actual_duration_minutes, 1)
                
                await db.commit()
                logger.info(f"💾 Recording marked as failed in database: {recording_id}")
        except Exception as e:
            logger.error(f"❌ Failed to mark recording as failed: {str(e)}")
            try:
                await db.rollback()
            except:
                pass
    
    async def _finalize_recording(self, db: AsyncSession, recording_data: Dict):
        try:
            recording_id = recording_data['recording_id']
            file_path = recording_data['file_path']
            actual_start_time = recording_data['start_time']
            
            logger.info(f"📋 Finalizing recording ID: {recording_id}")
            
            result = await db.execute(
                select(RadioSessionRecording).where(RadioSessionRecording.id == recording_id)
            )
            recording = result.scalar_one_or_none()
            
            if not recording:
                logger.error(f"❌ Recording entry not found in database: {recording_id}")
                return
            
            # Use Nairobi timezone
            nairobi_tz = pytz.timezone('Africa/Nairobi')
            actual_end_time = datetime.now(nairobi_tz)
            actual_duration_minutes = (actual_end_time - actual_start_time).total_seconds() / 60
            
            logger.info(f"📊 Recording duration: {actual_duration_minutes:.1f} minutes")
            
            # Check if recording file exists and has content
            if os.path.exists(file_path):
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > 0:
                        file_size_mb = file_size / (1024 * 1024)
                        logger.info(f"📁 Recording file size: {file_size_mb:.2f}MB")
                        
                        # Step 1: Safely read the file with retry mechanism
                        logger.info(f"📖 Reading recording file: {os.path.basename(file_path)}")
                        success, file_content, error_msg = await self._safe_file_read(file_path)
                        
                        if success and file_content:
                            try:
                                # Step 2: Prepare file for upload
                                original_filename = os.path.basename(file_path)
                                logger.info(f"💾 Uploading file: {original_filename}")
                                
                                file_obj = io.BytesIO(file_content)
                                upload_file = UploadFile(
                                    file=file_obj,
                                    filename=original_filename,
                                    headers={"content-type": "audio/mpeg"}
                                )
                                
                                # Step 3: Upload file and get saved path/URL
                                file_path_saved, file_url = await save_upload_file(upload_file, "recordings/sessions")
                                logger.info(f"✅ File uploaded successfully: {file_url}")
                                
                                # Step 4: Update recording status as COMPLETED
                                recording.recording_status = 'completed'
                                recording.actual_end_time = actual_end_time
                                recording.recording_file_path = file_path_saved
                                recording.recording_file_url = file_url
                                recording.file_size_mb = round(file_size_mb, 2)
                                recording.duration_minutes = round(actual_duration_minutes, 1)
                                recording.error_message = None  # Clear any previous error messages
                                
                                # Step 5: Safely delete temporary file
                                delete_success, delete_msg = await self._safe_file_delete(file_path)
                                if delete_success:
                                    logger.info(f"🗑️ Temporary file cleaned up: {original_filename}")
                                else:
                                    logger.warning(f"⚠️ Could not delete temporary file: {delete_msg}")
                                    # Still mark as completed since upload succeeded
                                
                                logger.info(f"✅ Recording COMPLETED successfully: {original_filename} ({file_size_mb:.2f}MB, {actual_duration_minutes:.1f}min)")
                                
                            except Exception as upload_error:
                                logger.error(f"❌ File upload failed: {str(upload_error)}")
                                # Keep the temporary file if upload fails
                                recording.recording_status = 'failed'
                                recording.error_message = f'File upload error: {str(upload_error)}'
                                recording.actual_end_time = actual_end_time
                                recording.duration_minutes = round(actual_duration_minutes, 1)
                                recording.recording_file_path = file_path  # Keep temp path for retry
                        else:
                            logger.error(f"❌ Could not read recording file: {error_msg}")
                            recording.recording_status = 'failed'
                            recording.error_message = f'File read error: {error_msg}'
                            recording.actual_end_time = actual_end_time
                            recording.duration_minutes = round(actual_duration_minutes, 1)
                            recording.recording_file_path = file_path  # Keep temp path for manual recovery
                    else:
                        logger.warning(f"⚠️ Recording file is empty: {file_path}")
                        recording.recording_status = 'failed'
                        recording.error_message = 'Recording file is empty (0 bytes)'
                        recording.actual_end_time = actual_end_time
                        recording.duration_minutes = round(actual_duration_minutes, 1)
                except Exception as file_check_error:
                    logger.error(f"❌ Error checking file: {str(file_check_error)}")
                    recording.recording_status = 'failed'
                    recording.error_message = f'File check error: {str(file_check_error)}'
                    recording.actual_end_time = actual_end_time
                    recording.duration_minutes = round(actual_duration_minutes, 1)
            else:
                logger.warning(f"⚠️ Recording file not found: {file_path}")
                recording.recording_status = 'failed'
                recording.error_message = 'Recording file not found'
                recording.actual_end_time = actual_end_time
                recording.duration_minutes = round(actual_duration_minutes, 1)
            
            # Step 6: Commit changes to database
            await db.commit()
            
            # Step 7: Log final status
            status_emoji = "✅" if recording.recording_status == 'completed' else "❌"
            logger.info(f"{status_emoji} Recording finalized: {recording.recording_status.upper()} ({recording.duration_minutes}min)")
            
            # Step 8: Additional cleanup for failed recordings
            if recording.recording_status == 'failed' and os.path.exists(file_path):
                logger.info(f"💾 Keeping temporary file for manual recovery: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Critical error during recording finalization: {str(e)}")
            try:
                # Attempt to mark as failed in database
                if 'recording' in locals() and recording:
                    recording.recording_status = 'failed'
                    recording.error_message = f'Finalization error: {str(e)}'
                    recording.actual_end_time = datetime.now(pytz.timezone('Africa/Nairobi'))
                    if 'actual_duration_minutes' in locals():
                        recording.duration_minutes = round(actual_duration_minutes, 1)
                    await db.commit()
                    logger.info("💾 Recording marked as failed in database")
                else:
                    await db.rollback()
                    logger.info("🔄 Database transaction rolled back")
            except Exception as commit_error:
                logger.error(f"❌ Failed to update database after error: {str(commit_error)}")
                try:
                    await db.rollback()
                except:
                    pass
    
    async def _save_station_recordings_on_shutdown(self, station_id: str):
        """Enhanced shutdown save with better error handling"""
        station_recordings = [k for k in self.recording_processes.keys() if k.startswith(station_id)]
        
        if not station_recordings:
            logger.info(f"No active recordings to save for station: {station_id}")
            return
        
        logger.info(f"💾 Saving {len(station_recordings)} recordings for station {station_id} on shutdown...")
        
        for recording_key in station_recordings:
            try:
                logger.info(f"🛑 Shutdown save: {recording_key}")
                db = get_database()
                try:
                    db_session = await db.__anext__()
                    await self._stop_session_recording(db_session, recording_key)
                    logger.info(f"✅ Successfully saved on shutdown: {recording_key}")
                except Exception as save_error:
                    logger.error(f"❌ Error saving recording {recording_key} on shutdown: {str(save_error)}")
                    # Try to at least mark as failed
                    try:
                        if recording_key in self.recording_processes:
                            recording_data = self.recording_processes[recording_key]
                            await self._mark_recording_as_failed(db_session, recording_data, f"Shutdown save error: {str(save_error)}")
                    except Exception as mark_error:
                        logger.error(f"❌ Could not mark recording as failed: {str(mark_error)}")
                finally:
                    try:
                        await db.aclose()
                    except:
                        pass
            except Exception as outer_error:
                logger.error(f"❌ Critical error during shutdown save {recording_key}: {str(outer_error)}")
        
        logger.info(f"✅ Shutdown save completed for station: {station_id}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Enhanced service status with file handling metrics"""
        status = {
            "service_running": len(self.station_tasks) > 0,
            "platform": self.platform_system,
            "total_stations": len(self.station_tasks),
            "active_recordings": len(self.recording_processes),
            "is_validated": self._is_validated,
            "startup_time": self._startup_time.isoformat() if self._startup_time else None,
            "file_handling_config": {
                "max_retries": self.max_file_access_retries,
                "base_retry_delay": self.base_retry_delay,
                "max_retry_delay": self.max_retry_delay,
                "windows_file_delay": self.windows_file_delay,
                "process_cleanup_timeout": self.process_cleanup_timeout
            },
            "validation_result": {
                "is_valid": self.validation_result.is_valid if self.validation_result else False,
                "errors": self.validation_result.errors if self.validation_result else [],
                "warnings": self.validation_result.warnings if self.validation_result else []
            } if self.validation_result else None,
            "system_info": self.system_info.__dict__ if self.system_info else None,
            "stations": {
                station_id: {
                    "task_running": not task.done() if hasattr(task, 'done') else True,
                    "recordings": [k for k in self.recording_processes.keys() if k.startswith(station_id)]
                }
                for station_id, task in self.station_tasks.items()
            },
            "recording_processes": {
                key: {
                    "recording_id": data.get('recording_id'),
                    "file_path": data.get('file_path'),
                    "start_time": data.get('start_time').isoformat() if data.get('start_time') else None,
                    "session": data.get('session'),
                    "process_pid": data.get('process').pid if data.get('process') else None
                }
                for key, data in self.recording_processes.items()
            }
        }
        return status
    
    def get_health_check(self) -> Dict[str, Any]:
        """Enhanced health check with process monitoring"""
        dead_tasks = sum(1 for task in self.station_tasks.values() if hasattr(task, 'done') and task.done())
        
        # Check for zombie processes
        zombie_processes = 0
        for recording_data in self.recording_processes.values():
            process = recording_data.get('process')
            if process and process.poll() is not None:
                zombie_processes += 1
        
        return {
            "healthy": len(self.station_tasks) > 0 and dead_tasks == 0 and self._is_validated,
            "platform": self.platform_system,
            "total_stations": len(self.station_tasks),
            "dead_tasks": dead_tasks,
            "active_recordings": len(self.recording_processes),
            "zombie_processes": zombie_processes,
            "check_interval": self.check_interval,
            "validation_status": "validated" if self._is_validated else "not_validated",
            "system_info": self.system_info.__dict__ if self.system_info else None,
            "file_handling_healthy": True,  # Could add more sophisticated checks here
            "uptime_seconds": (datetime.now(pytz.timezone('Africa/Nairobi')) - self._startup_time).total_seconds() if self._startup_time else 0
        }

# Create service instance
recording_service = EnhancedStationRecordingService()


async def cleanup_temp_files():
    try:
        temp_path = Path(recording_service.base_recording_path)
        if not temp_path.exists():
            return 0
        
        cleaned_count = 0
        for file_path in temp_path.glob("*.mp3"):
            try:
                # Check if file is older than 1 hour and not in active recordings
                file_age = time.time() - file_path.stat().st_mtime
                is_active = any(data.get('file_path') == str(file_path) for data in recording_service.recording_processes.values())
                
                if file_age > 3600 and not is_active:  # 1 hour old and not active
                    success, msg = await recording_service._safe_file_delete(str(file_path))
                    if success:
                        cleaned_count += 1
                        logger.info(f"🗑️ Cleaned up orphaned file: {file_path.name}")
                    else:
                        logger.warning(f"⚠️ Could not clean up file: {msg}")
            except Exception as e:
                logger.error(f"❌ Error cleaning up file {file_path}: {str(e)}")
        
        logger.info(f"✅ Cleanup completed: {cleaned_count} files removed")
        return cleaned_count
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {str(e)}")
        return 0



# Signal handler for graceful shutdown
def setup_signal_handlers():
    import signal
    
    def signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(stop_recording_service())
    
    # Register signal handlers (Unix systems)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, signal_handler)


async def periodic_cleanup():
    while True:
        try:
            await asyncio.sleep(1800)  # Run every 30 minutes
            await cleanup_temp_files()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Error in periodic cleanup: {str(e)}")

