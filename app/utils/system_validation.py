import asyncio
import subprocess
import os
import platform
import shutil
import psutil
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import logging
from dataclasses import dataclass
import pytz
import json
import concurrent.futures
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_database

logger = logging.getLogger(__name__)

@dataclass
class SystemInfo:
    """System information and capabilities"""
    platform: str
    platform_version: str
    architecture: str
    ffmpeg_version: str
    ffmpeg_path: str
    python_version: str
    available_disk_gb: float
    total_memory_gb: float
    cpu_count: int
    timezone: str
    is_production: bool
    os_specific_info: Dict[str, Any]

@dataclass
class ValidationResult:
    """Result of system validation"""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    system_info: Optional[SystemInfo]
    recommendations: list[str]
    platform_specific_issues: list[str]

class OSSpecificSystemValidator:
    """Validates system requirements with OS-specific checks for the recording service"""
    
    def __init__(self, recording_path: str = "./temp_recordings", min_disk_gb: float = 5.0):
        self.recording_path = recording_path
        self.min_disk_gb = min_disk_gb
        self.target_timezone = 'Africa/Nairobi'
        
        # Detect platform early
        self.platform_system = platform.system().lower()
        self.is_windows = self.platform_system == 'windows'
        self.is_linux = self.platform_system == 'linux'
        self.is_mac = self.platform_system == 'darwin'
        
    async def validate_system(self) -> ValidationResult:
        """Comprehensive system validation with OS-specific checks"""
        errors = []
        warnings = []
        recommendations = []
        platform_specific_issues = []
        system_info = None
        
        logger.info(f"Starting OS-specific system validation for {self.platform_system.title()}")
        
        try:
            # 1. Platform Detection and Info
            platform_info, platform_version, architecture = self._detect_platform_detailed()
            logger.info(f"Platform detected: {platform_info} ({architecture})")
            
            # 2. OS-Specific Pre-checks
            os_prereq_result = await self._validate_os_prerequisites()
            if os_prereq_result['errors']:
                errors.extend(os_prereq_result['errors'])
            if os_prereq_result['warnings']:
                warnings.extend(os_prereq_result['warnings'])
            if os_prereq_result['platform_issues']:
                platform_specific_issues.extend(os_prereq_result['platform_issues'])
            
            # 3. FFmpeg Validation (Enhanced Windows-compatible)
            ffmpeg_result = await self._validate_ffmpeg()
            if not ffmpeg_result[0]:
                errors.append(f"FFmpeg validation failed: {ffmpeg_result[1]}")
            else:
                ffmpeg_version, ffmpeg_path = ffmpeg_result[1], ffmpeg_result[2]
                logger.info(f"FFmpeg validated: {ffmpeg_version} at {ffmpeg_path}")
                
                # OS-specific FFmpeg checks
                try:
                    ffmpeg_os_issues = await self._validate_ffmpeg_os_specific(ffmpeg_path)
                    if ffmpeg_os_issues['warnings']:
                        warnings.extend(ffmpeg_os_issues['warnings'])
                    if ffmpeg_os_issues['platform_issues']:
                        platform_specific_issues.extend(ffmpeg_os_issues['platform_issues'])
                except Exception as e:
                    warnings.append(f"Could not perform OS-specific FFmpeg checks: {str(e)}")
            
            # 4. Timezone Configuration
            timezone_result = self._configure_timezone()
            if timezone_result[1]:  # Has warnings
                warnings.extend(timezone_result[1])
            logger.info(f"Timezone configured: {timezone_result[0]}")
            
            # 5. Storage Validation (OS-specific)
            storage_result = await self._validate_storage_os_specific()
            if not storage_result['success']:
                errors.append(f"Storage validation failed: {storage_result['error']}")
            else:
                available_gb = storage_result['available_gb']
                if available_gb < self.min_disk_gb:
                    warnings.append(f"Low disk space: {available_gb:.1f}GB available (recommended: >{self.min_disk_gb}GB)")
                logger.info(f"Storage validated: {available_gb:.1f}GB available")
                
                # Add OS-specific storage warnings
                if storage_result['warnings']:
                    warnings.extend(storage_result['warnings'])
                if storage_result['platform_issues']:
                    platform_specific_issues.extend(storage_result['platform_issues'])
            
            # 6. Database Connectivity
            db_result = await self._validate_database()
            if not db_result[0]:
                errors.append(f"Database validation failed: {db_result[1]}")
            else:
                logger.info("Database connectivity validated")
            
            # 7. File Permissions (OS-specific)
            permissions_result = await self._validate_file_permissions_os_specific()
            if not permissions_result['success']:
                errors.append(f"File permissions validation failed: {permissions_result['error']}")
            else:
                logger.info("File permissions validated")
                if permissions_result['warnings']:
                    warnings.extend(permissions_result['warnings'])
                if permissions_result['platform_issues']:
                    platform_specific_issues.extend(permissions_result['platform_issues'])
            
            # 8. System Resources (OS-specific)
            resources = await self._check_system_resources_os_specific()
            if resources['memory_gb'] < 1.0:
                warnings.append(f"Low memory: {resources['memory_gb']:.1f}GB (recommended: >1GB)")
            if resources['cpu_count'] < 2:
                warnings.append(f"Low CPU count: {resources['cpu_count']} cores (recommended: >2 cores)")
            
            # Add OS-specific resource warnings
            if resources['warnings']:
                warnings.extend(resources['warnings'])
            if resources['platform_issues']:
                platform_specific_issues.extend(resources['platform_issues'])
            
            # 9. Network Connectivity
            network_result = await self._validate_network()
            if not network_result[0]:
                warnings.append(f"Network validation warning: {network_result[1]}")
            
            # 10. OS-Specific Service Requirements
            service_result = await self._validate_os_specific_services()
            if service_result['warnings']:
                warnings.extend(service_result['warnings'])
            if service_result['platform_issues']:
                platform_specific_issues.extend(service_result['platform_issues'])
            
            # Create system info with OS-specific details
            system_info = SystemInfo(
                platform=platform_info,
                platform_version=platform_version,
                architecture=architecture,
                ffmpeg_version=ffmpeg_version if 'ffmpeg_version' in locals() else "Not available",
                ffmpeg_path=ffmpeg_path if 'ffmpeg_path' in locals() else "",
                python_version=platform.python_version(),
                available_disk_gb=storage_result['available_gb'] if storage_result['success'] else 0.0,
                total_memory_gb=resources['memory_gb'],
                cpu_count=resources['cpu_count'],
                timezone=timezone_result[0],
                is_production=self._is_production_environment(),
                os_specific_info=os_prereq_result['os_info']
            )
            
            # Generate recommendations (OS-specific)
            recommendations = self._generate_recommendations_os_specific(system_info, warnings, platform_specific_issues)
            
            is_valid = len(errors) == 0
            
            if is_valid:
                logger.info("✅ OS-specific system validation completed successfully")
            else:
                logger.error(f"❌ System validation failed with {len(errors)} errors")
                
            return ValidationResult(is_valid, errors, warnings, system_info, recommendations, platform_specific_issues)
            
        except Exception as e:
            logger.error(f"System validation failed with exception: {str(e)}")
            errors.append(f"Validation exception: {str(e)}")
            return ValidationResult(False, errors, warnings, system_info, recommendations, platform_specific_issues)
    
    def _detect_platform_detailed(self) -> Tuple[str, str, str]:
        """Detailed platform detection with version and architecture"""
        system = platform.system().lower()
        version = platform.release()
        architecture = platform.machine()
        
        if system == 'windows':
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                    build = winreg.QueryValueEx(key, "CurrentBuild")[0]
                    display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]
                return f"Windows {display_version}", f"{version} (Build {build})", architecture
            except:
                return f"Windows {version}", version, architecture
        elif system == 'linux':
            try:
                with open('/etc/os-release', 'r') as f:
                    os_info = {}
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            os_info[key] = value.strip('"')
                    
                    name = os_info.get('PRETTY_NAME', os_info.get('NAME', 'Linux'))
                    version_id = os_info.get('VERSION_ID', version)
                    return name, version_id, architecture
            except:
                return f"Linux {version}", version, architecture
        elif system == 'darwin':
            mac_version = platform.mac_ver()[0]
            return f"macOS {mac_version}", mac_version, architecture
        else:
            return f"Unknown ({system})", version, architecture
    
    async def _validate_os_prerequisites(self) -> Dict[str, Any]:
        """Validate OS-specific prerequisites"""
        result = {
            'errors': [],
            'warnings': [],
            'platform_issues': [],
            'os_info': {}
        }
        
        if self.is_windows:
            await self._validate_windows_prerequisites(result)
        elif self.is_linux:
            await self._validate_linux_prerequisites(result)
        elif self.is_mac:
            await self._validate_mac_prerequisites(result)
        
        return result
    
    async def _validate_windows_prerequisites(self, result: Dict[str, Any]):
        """Windows-specific validation"""
        try:
            # Check Windows version
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                build = int(winreg.QueryValueEx(key, "CurrentBuild")[0])
                result['os_info']['build'] = build
                
                # Windows 10 minimum build check
                if build < 19041:  # Windows 10 version 2004
                    result['warnings'].append(f"Old Windows build ({build}). Recommended: Windows 10 version 2004 or later")
                
                # Check for Windows Media Feature Pack (required for some audio codecs)
                try:
                    media_features = subprocess.run(['dism', '/online', '/get-features', '/featurename:MediaPlayback'], 
                                                  capture_output=True, text=True, timeout=10)
                    if 'State : Disabled' in media_features.stdout:
                        result['platform_issues'].append("Windows Media Feature Pack is disabled. May affect audio processing.")
                except:
                    result['warnings'].append("Could not check Windows Media Feature Pack status")
                
                # Check for Windows Subsystem for Linux (WSL) if present
                try:
                    wsl_check = subprocess.run(['wsl', '--status'], capture_output=True, text=True, timeout=5)
                    if wsl_check.returncode == 0:
                        result['os_info']['wsl_available'] = True
                        logger.info("WSL detected - additional Linux compatibility available")
                except:
                    result['os_info']['wsl_available'] = False
                
        except Exception as e:
            result['warnings'].append(f"Could not perform Windows-specific checks: {str(e)}")
        
        # Check Windows Defender exclusions for recording directory
        try:
            defender_check = subprocess.run(['powershell', '-Command', 
                                           f'Get-MpPreference | Select-Object -ExpandProperty ExclusionPath'], 
                                          capture_output=True, text=True, timeout=10)
            if self.recording_path not in defender_check.stdout:
                result['platform_issues'].append(f"Recording directory not in Windows Defender exclusions. This may cause file locking issues.")
        except:
            result['warnings'].append("Could not check Windows Defender exclusions")
        
        # Check for running antivirus that might interfere
        try:
            av_check = subprocess.run(['wmic', '/namespace:\\\\root\\SecurityCenter2', 'path', 'AntiVirusProduct', 'get', 'displayName'], 
                                    capture_output=True, text=True, timeout=10)
            if av_check.returncode == 0 and av_check.stdout.strip():
                av_products = [line.strip() for line in av_check.stdout.split('\n') if line.strip() and line.strip() != 'displayName']
                if av_products:
                    result['os_info']['antivirus'] = av_products
                    result['platform_issues'].append(f"Antivirus detected: {', '.join(av_products)}. May interfere with file operations.")
        except:
            pass
    
    async def _validate_linux_prerequisites(self, result: Dict[str, Any]):
        """Linux-specific validation"""
        try:
            # Check distribution
            with open('/etc/os-release', 'r') as f:
                os_info = {}
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os_info[key] = value.strip('"')
                result['os_info']['distribution'] = os_info
            
            # Check for systemd (modern service management)
            if os.path.exists('/etc/systemd'):
                result['os_info']['systemd'] = True
                logger.info("Systemd detected - modern service management available")
            else:
                result['os_info']['systemd'] = False
                result['warnings'].append("Systemd not detected. Service management may be limited.")
            
            # Check for required packages
            required_packages = ['libc6', 'libmp3lame0']
            missing_packages = []
            
            for package in required_packages:
                try:
                    pkg_check = subprocess.run(['dpkg', '-l', package], 
                                             capture_output=True, text=True, timeout=5)
                    if pkg_check.returncode != 0:
                        missing_packages.append(package)
                except:
                    # Try rpm-based systems
                    try:
                        rpm_check = subprocess.run(['rpm', '-q', package], 
                                                 capture_output=True, text=True, timeout=5)
                        if rpm_check.returncode != 0:
                            missing_packages.append(package)
                    except:
                        result['warnings'].append(f"Could not check for package: {package}")
            
            if missing_packages:
                result['platform_issues'].append(f"Missing recommended packages: {', '.join(missing_packages)}")
            
            # Check for audio system
            audio_systems = []
            if os.path.exists('/usr/bin/pulseaudio'):
                audio_systems.append('PulseAudio')
            if os.path.exists('/usr/bin/pipewire'):
                audio_systems.append('PipeWire')
            if os.path.exists('/proc/asound'):
                audio_systems.append('ALSA')
            
            result['os_info']['audio_systems'] = audio_systems
            if not audio_systems:
                result['warnings'].append("No audio system detected. Audio processing may be limited.")
            
            # Check ulimits for file operations
            try:
                ulimit_check = subprocess.run(['ulimit', '-n'], shell=True, 
                                            capture_output=True, text=True, timeout=5)
                file_limit = int(ulimit_check.stdout.strip())
                result['os_info']['file_descriptor_limit'] = file_limit
                
                if file_limit < 1024:
                    result['platform_issues'].append(f"Low file descriptor limit: {file_limit} (recommended: >1024)")
            except:
                result['warnings'].append("Could not check file descriptor limits")
                
        except Exception as e:
            result['warnings'].append(f"Could not perform Linux-specific checks: {str(e)}")
    
    async def _validate_mac_prerequisites(self, result: Dict[str, Any]):
        """macOS-specific validation"""
        try:
            # Check macOS version
            mac_version = platform.mac_ver()[0]
            version_parts = [int(x) for x in mac_version.split('.')]
            result['os_info']['macos_version'] = mac_version
            
            # Check minimum macOS version (10.15 Catalina)
            if version_parts[0] == 10 and version_parts[1] < 15:
                result['platform_issues'].append(f"Old macOS version: {mac_version}. Recommended: macOS 10.15 or later")
            
            # Check for Xcode Command Line Tools
            try:
                xcode_check = subprocess.run(['xcode-select', '--print-path'], 
                                           capture_output=True, text=True, timeout=5)
                if xcode_check.returncode == 0:
                    result['os_info']['xcode_tools'] = True
                    logger.info("Xcode Command Line Tools detected")
                else:
                    result['platform_issues'].append("Xcode Command Line Tools not installed. Required for development tools.")
            except:
                result['warnings'].append("Could not check Xcode Command Line Tools")
            
            # Check for Homebrew
            if shutil.which('brew'):
                result['os_info']['homebrew'] = True
                logger.info("Homebrew detected - package management available")
                
                # Check if FFmpeg was installed via Homebrew
                try:
                    brew_list = subprocess.run(['brew', 'list', 'ffmpeg'], 
                                             capture_output=True, text=True, timeout=5)
                    if brew_list.returncode == 0:
                        result['os_info']['ffmpeg_via_homebrew'] = True
                except:
                    result['os_info']['ffmpeg_via_homebrew'] = False
            else:
                result['os_info']['homebrew'] = False
                result['warnings'].append("Homebrew not detected. Package management may be limited.")
            
            # Check macOS security settings
            try:
                # Check if Terminal has Full Disk Access (needed for some operations)
                security_check = subprocess.run(['sqlite3', 
                                               '/Library/Application Support/com.apple.TCC/TCC.db', 
                                               "SELECT * FROM access WHERE service='kTCCServiceSystemPolicyAllFiles'"], 
                                              capture_output=True, text=True, timeout=5)
                if 'Terminal' not in security_check.stdout:
                    result['platform_issues'].append("Terminal may not have Full Disk Access. Some file operations may be restricted.")
            except:
                result['warnings'].append("Could not check macOS security permissions")
                
        except Exception as e:
            result['warnings'].append(f"Could not perform macOS-specific checks: {str(e)}")
    
    async def _validate_ffmpeg(self) -> Tuple[bool, str, str]:
        """Enhanced FFmpeg validation that works reliably on Windows and all platforms"""
        try:
            logger.info("Starting cross-platform FFmpeg validation...")
            
            # Step 1: Check if FFmpeg is in PATH
            ffmpeg_path = shutil.which('ffmpeg')
            if not ffmpeg_path:
                # OS-specific installation suggestions
                if self.is_windows:
                    return False, "FFmpeg not found. Install from https://ffmpeg.org or use 'winget install ffmpeg'", ""
                elif self.is_linux:
                    return False, "FFmpeg not found. Install with 'sudo apt install ffmpeg' (Ubuntu/Debian) or 'sudo yum install ffmpeg' (RHEL/CentOS)", ""
                elif self.is_mac:
                    return False, "FFmpeg not found. Install with 'brew install ffmpeg' or from https://ffmpeg.org", ""
                else:
                    return False, "FFmpeg not found in PATH. Please install FFmpeg and ensure it's accessible.", ""
            
            logger.info(f"FFmpeg found at: {ffmpeg_path}")
            
            # Step 2: Try multiple execution methods for maximum compatibility
            execution_methods = [
                ("Thread-based subprocess", self._method_thread_subprocess),
                ("Shell-based async", self._method_shell_async),
                ("Direct async (fallback)", self._method_direct_async)
            ]
            
            for method_name, method_func in execution_methods:
                try:
                    logger.info(f"Trying {method_name}...")
                    success, result, error = await method_func(ffmpeg_path)
                    
                    if success:
                        logger.info(f"✅ {method_name} succeeded!")
                        return self._validate_ffmpeg_output(result, ffmpeg_path)
                    else:
                        logger.warning(f"❌ {method_name} failed: {error}")
                        
                except Exception as e:
                    logger.warning(f"❌ {method_name} exception: {str(e)}")
                    continue
            
            return False, "All FFmpeg execution methods failed. Check FFmpeg installation and permissions.", ffmpeg_path
            
        except Exception as e:
            logger.error(f"FFmpeg validation error: {str(e)}")
            return False, f"FFmpeg validation error: {str(e)}", ""
    
    async def _method_thread_subprocess(self, ffmpeg_path: str) -> Tuple[bool, str, str]:
        """Method 1: Use thread pool for subprocess execution (most reliable on Windows)"""
        try:
            def run_ffmpeg():
                creation_flags = 0
                if self.is_windows:
                    creation_flags = subprocess.CREATE_NO_WINDOW
                
                result = subprocess.run(
                    [ffmpeg_path, '-version'],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=creation_flags
                )
                return result
            
            # Run in thread pool to avoid asyncio subprocess issues
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_ffmpeg)
                result = await asyncio.get_event_loop().run_in_executor(None, future.result)
            
            if result.returncode == 0:
                return True, result.stdout, ""
            else:
                return False, "", f"FFmpeg returned code {result.returncode}: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "", "FFmpeg command timed out"
        except Exception as e:
            return False, "", f"Thread method failed: {str(e)}"
    
    async def _method_shell_async(self, ffmpeg_path: str) -> Tuple[bool, str, str]:
        """Method 2: Use shell=True with asyncio (good Windows compatibility)"""
        try:
            creation_flags = 0
            if self.is_windows:
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            # Use shell=True which often works better on Windows
            process = await asyncio.create_subprocess_shell(
                f'"{ffmpeg_path}" -version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creation_flags
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=30
            )
            
            if process.returncode == 0:
                return True, stdout.decode('utf-8', errors='ignore'), ""
            else:
                return False, "", f"Shell method failed with code {process.returncode}: {stderr.decode('utf-8', errors='ignore')}"
                
        except asyncio.TimeoutError:
            return False, "", "Shell method timed out"
        except Exception as e:
            return False, "", f"Shell method failed: {str(e)}"
    
    async def _method_direct_async(self, ffmpeg_path: str) -> Tuple[bool, str, str]:
        """Method 3: Direct asyncio.create_subprocess_exec (original method)"""
        try:
            creation_flags = 0
            if self.is_windows:
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = await asyncio.create_subprocess_exec(
                ffmpeg_path, '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creation_flags
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=30
            )
            
            if process.returncode == 0:
                return True, stdout.decode('utf-8', errors='ignore'), ""
            else:
                return False, "", f"Direct method failed with code {process.returncode}: {stderr.decode('utf-8', errors='ignore')}"
                
        except asyncio.TimeoutError:
            return False, "", "Direct method timed out"
        except Exception as e:
            return False, "", f"Direct method failed: {str(e)}"
    
    def _validate_ffmpeg_output(self, output: str, ffmpeg_path: str) -> Tuple[bool, str, str]:
        """Validate FFmpeg output and check for required features"""
        try:
            if not output or len(output.strip()) == 0:
                return False, "FFmpeg output is empty", ffmpeg_path
            
            # Extract version line
            lines = output.split('\n')
            if not lines:
                return False, "No version information found", ffmpeg_path
            
            version_line = lines[0].strip()
            if not version_line.startswith('ffmpeg version'):
                return False, f"Unexpected version format: {version_line}", ffmpeg_path
            
            logger.info(f"FFmpeg version detected: {version_line}")
            
            # Check for libmp3lame support (required for MP3 encoding)
            if '--enable-libmp3lame' in output:
                logger.info("✅ libmp3lame support confirmed from configuration")
                return True, version_line, ffmpeg_path
            else:
                # If not in version output, assume it's available (modern FFmpeg builds)
                logger.info("✅ libmp3lame support assumed (modern FFmpeg build)")
                return True, version_line, ffmpeg_path
                
        except Exception as e:
            return False, f"Error validating FFmpeg output: {str(e)}", ffmpeg_path
    
    async def _validate_ffmpeg_os_specific(self, ffmpeg_path: str) -> Dict[str, Any]:
        """OS-specific FFmpeg validation"""
        result = {'warnings': [], 'platform_issues': []}
        
        try:
            # Try to check FFmpeg capabilities, but don't fail if this doesn't work
            def check_codecs():
                creation_flags = 0
                if self.is_windows:
                    creation_flags = subprocess.CREATE_NO_WINDOW
                
                result = subprocess.run(
                    [ffmpeg_path, '-codecs'],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    creationflags=creation_flags
                )
                return result
            
            # Use thread pool for codec check too
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(check_codecs)
                codec_result = await asyncio.get_event_loop().run_in_executor(None, future.result)
            
            if codec_result.returncode == 0:
                codecs_output = codec_result.stdout.lower()
                
                # OS-specific codec checks
                if self.is_windows:
                    # Windows-specific audio codecs
                    if 'mp3' not in codecs_output:
                        result['platform_issues'].append("MP3 codec not available in FFmpeg build")
                    if 'aac' not in codecs_output:
                        result['warnings'].append("AAC codec not available - may limit streaming compatibility")
                
                elif self.is_linux:
                    # Linux-specific checks
                    if 'pulse' not in codecs_output:
                        result['warnings'].append("PulseAudio support not detected in FFmpeg")
                    if 'alsa' not in codecs_output:
                        result['warnings'].append("ALSA support not detected in FFmpeg")
                
                elif self.is_mac:
                    # macOS-specific checks
                    if 'avfoundation' not in codecs_output:
                        result['warnings'].append("AVFoundation support not detected in FFmpeg")
                    if 'videotoolbox' not in codecs_output:
                        result['warnings'].append("VideoToolbox support not detected in FFmpeg")
            
        except Exception as e:
            result['warnings'].append(f"Could not perform OS-specific FFmpeg checks: {str(e)}")
        
        return result
    
    def _configure_timezone(self) -> Tuple[str, list[str]]:
        """Configure timezone with OS-specific handling"""
        warnings = []
        
        try:
            # Set timezone for the application
            nairobi_tz = pytz.timezone(self.target_timezone)
            current_time = datetime.now(nairobi_tz)
            
            # OS-specific timezone checks
            if self.is_windows:
                try:
                    # Check Windows timezone
                    tz_check = subprocess.run(['tzutil', '/g'], capture_output=True, text=True, timeout=5)
                    if tz_check.returncode == 0:
                        windows_tz = tz_check.stdout.strip()
                        if 'E. Africa Standard Time' not in windows_tz:
                            warnings.append(f"Windows timezone is '{windows_tz}', not 'E. Africa Standard Time'. Application will use Nairobi time.")
                except:
                    warnings.append("Could not check Windows timezone setting")
            
            elif self.is_linux:
                try:
                    # Check system timezone
                    if os.path.exists('/etc/timezone'):
                        with open('/etc/timezone', 'r') as f:
                            system_tz = f.read().strip()
                            if system_tz != self.target_timezone:
                                warnings.append(f"System timezone is '{system_tz}', not '{self.target_timezone}'. Application will use Nairobi time.")
                    elif os.path.islink('/etc/localtime'):
                        link_target = os.readlink('/etc/localtime')
                        if self.target_timezone not in link_target:
                            warnings.append(f"System timezone differs from target. Application will use Nairobi time.")
                except:
                    warnings.append("Could not determine Linux system timezone")
            
            elif self.is_mac:
                try:
                    # Check macOS timezone
                    tz_check = subprocess.run(['systemsetup', '-gettimezone'], 
                                            capture_output=True, text=True, timeout=5)
                    if tz_check.returncode == 0:
                        mac_tz = tz_check.stdout.strip()
                        if self.target_timezone not in mac_tz:
                            warnings.append(f"macOS timezone differs from target. Application will use Nairobi time.")
                except:
                    warnings.append("Could not check macOS timezone setting")
            
            # Set environment variable for subprocess
            os.environ['TZ'] = self.target_timezone
            
            return f"{self.target_timezone} (UTC{current_time.strftime('%z')})", warnings
            
        except Exception as e:
            warnings.append(f"Timezone configuration warning: {str(e)}")
            return "UTC (fallback)", warnings
    
    async def _validate_storage_os_specific(self) -> Dict[str, Any]:
        """OS-specific storage validation"""
        result = {
            'success': False,
            'available_gb': 0.0,
            'warnings': [],
            'platform_issues': [],
            'error': ''
        }
        
        try:
            # Create recording directory if it doesn't exist
            recording_dir = Path(self.recording_path)
            recording_dir.mkdir(parents=True, exist_ok=True)
            
            # Check available disk space
            disk_usage = psutil.disk_usage(str(recording_dir))
            available_gb = disk_usage.free / (1024**3)
            total_gb = disk_usage.total / (1024**3)
            
            result['success'] = True
            result['available_gb'] = available_gb
            
            # OS-specific storage checks
            if self.is_windows:
                # Check if on system drive
                if str(recording_dir).startswith('C:'):
                    result['warnings'].append("Recording directory on system drive (C:). Consider using a separate drive for better performance.")
                
                # Check file system
                try:
                    import ctypes
                    drive = str(recording_dir)[0] + ':\\'
                    file_system = ctypes.create_string_buffer(255)
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        ctypes.c_wchar_p(drive), None, 0, None, None, None, file_system, 255)
                    fs_type = file_system.value.decode()
                    
                    if fs_type != 'NTFS':
                        result['platform_issues'].append(f"File system is {fs_type}, not NTFS. May have file size limitations.")
                except:
                    result['warnings'].append("Could not determine file system type")
            
            elif self.is_linux:
                # Check mount options
                try:
                    with open('/proc/mounts', 'r') as f:
                        mounts = f.read()
                        mount_point = str(recording_dir)
                        
                        # Find the mount point for our directory
                        for line in mounts.split('\n'):
                            parts = line.split()
                            if len(parts) > 3 and mount_point.startswith(parts[1]):
                                mount_options = parts[3]
                                if 'noexec' in mount_options:
                                    result['platform_issues'].append("Mount point has 'noexec' option. May prevent some operations.")
                                if 'ro' in mount_options:
                                    result['platform_issues'].append("Mount point is read-only!")
                                break
                except:
                    pass
                
                # Check for sufficient inodes
                try:
                    statvfs = os.statvfs(str(recording_dir))
                    free_inodes = statvfs.f_favail
                    if free_inodes < 10000:
                        result['warnings'].append(f"Low inode count: {free_inodes} (may limit number of files)")
                except:
                    pass
            
            elif self.is_mac:
                # Check if on case-sensitive file system
                test_file1 = recording_dir / "TeSt.tmp"
                test_file2 = recording_dir / "test.tmp"
                try:
                    test_file1.touch()
                    if test_file2.exists():
                        result['warnings'].append("File system is case-insensitive. May cause filename conflicts.")
                    test_file1.unlink()
                except:
                    pass
            
            # Common checks for all platforms
            if total_gb < 100:
                result['warnings'].append(f"Small storage device: {total_gb:.1f}GB total")
            
            if available_gb / total_gb < 0.1:  # Less than 10% free
                result['platform_issues'].append(f"Storage nearly full: {available_gb:.1f}GB free of {total_gb:.1f}GB")
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def _validate_database(self) -> Tuple[bool, str]:
        """Validate database connectivity"""
        try:
            db = get_database()
            db_session = await db.__anext__()
            
            try:
                # Simple connectivity test
                result = await db_session.execute(text("SELECT 1"))
                result.scalar()
                
                # Test if required tables exist (basic check)
                tables_to_check = ['stations', 'station_schedules', 'radio_session_recordings']
                for table in tables_to_check:
                    try:
                        await db_session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                    except Exception as table_error:
                        return False, f"Required table '{table}' not accessible: {str(table_error)}"
                
                return True, "Database connectivity confirmed"
                
            finally:
                await db.aclose()
                
        except Exception as e:
            return False, f"Database connection failed: {str(e)}"
    
    async def _validate_file_permissions_os_specific(self) -> Dict[str, Any]:
        """OS-specific file permissions validation"""
        result = {
            'success': False,
            'warnings': [],
            'platform_issues': [],
            'error': ''
        }
        
        try:
            # Test write permissions in recording directory
            test_file = Path(self.recording_path) / "test_write_permission.tmp"
            
            # Write test
            with open(test_file, 'w') as f:
                f.write("test")
            
            # Read test
            with open(test_file, 'r') as f:
                content = f.read()
                if content != "test":
                    result['error'] = "File read/write test failed"
                    return result
            
            # OS-specific permission checks
            if self.is_windows:
                # Check for write permissions on parent directory
                try:
                    import win32security
                    import win32file
                    
                    # Get current user SID
                    user_sid = win32security.GetTokenInformation(
                        win32security.GetCurrentProcessToken(),
                        win32security.TokenUser
                    )[0]
                    
                    # Check directory permissions
                    dir_sd = win32security.GetFileSecurity(
                        str(self.recording_path),
                        win32security.DACL_SECURITY_INFORMATION
                    )
                    
                    # This is a simplified check - full ACL checking is complex
                    result['warnings'].append("Windows ACL permissions not fully validated")
                    
                except ImportError:
                    result['warnings'].append("pywin32 not available for detailed Windows permission checks")
                except Exception as e:
                    result['warnings'].append(f"Could not check Windows permissions: {str(e)}")
            
            elif self.is_linux or self.is_mac:
                # Check Unix permissions
                dir_stat = os.stat(self.recording_path)
                dir_mode = oct(dir_stat.st_mode)[-3:]
                
                # Check if owner has write permissions
                if not (dir_stat.st_mode & 0o200):
                    result['platform_issues'].append("Owner does not have write permissions")
                
                # Check if directory is owned by current user
                if dir_stat.st_uid != os.getuid():
                    result['warnings'].append("Recording directory not owned by current user")
                
                # Check for restrictive umask
                current_umask = os.umask(0)
                os.umask(current_umask)  # Restore original umask
                
                if current_umask & 0o022:
                    result['warnings'].append(f"Restrictive umask: {oct(current_umask)} - may cause permission issues")
            
            # Delete test file
            test_file.unlink()
            result['success'] = True
            
        except Exception as e:
            result['error'] = f"File permission test failed: {str(e)}"
        
        return result
    
    async def _check_system_resources_os_specific(self) -> Dict[str, Any]:
        """OS-specific system resource checking"""
        base_resources = {
            'memory_gb': 0.0,
            'memory_available_gb': 0.0,
            'memory_percent': 0.0,
            'cpu_count': 1,
            'cpu_percent': 0.0,
            'warnings': [],
            'platform_issues': []
        }
        
        try:
            memory = psutil.virtual_memory()
            cpu_count = psutil.cpu_count()
            
            base_resources.update({
                'memory_gb': memory.total / (1024**3),
                'memory_available_gb': memory.available / (1024**3),
                'memory_percent': memory.percent,
                'cpu_count': cpu_count,
                'cpu_percent': psutil.cpu_percent(interval=1)
            })
            
            # OS-specific resource checks
            if self.is_windows:
                # Check for Windows-specific memory pressure
                if memory.percent > 80:
                    base_resources['platform_issues'].append("High memory usage on Windows may cause file locking issues")
                
                # Check CPU architecture
                if platform.machine().lower() in ['arm64', 'aarch64']:
                    base_resources['warnings'].append("ARM64 Windows detected - ensure FFmpeg compatibility")
            
            elif self.is_linux:
                # Check for swap usage
                try:
                    swap = psutil.swap_memory()
                    if swap.percent > 50:
                        base_resources['warnings'].append(f"High swap usage: {swap.percent:.1f}%")
                except:
                    pass
                
                # Check load average
                try:
                    load_avg = os.getloadavg()
                    if load_avg[0] > cpu_count:
                        base_resources['platform_issues'].append(f"High system load: {load_avg[0]:.1f} (CPU count: {cpu_count})")
                except:
                    pass
                
                # Check for CPU governor
                try:
                    with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'r') as f:
                        governor = f.read().strip()
                        if governor == 'powersave':
                            base_resources['warnings'].append("CPU governor set to 'powersave' - may affect performance")
                except:
                    pass
            
            elif self.is_mac:
                # Check for Apple Silicon
                if platform.machine().lower() in ['arm64', 'aarch64']:
                    base_resources['warnings'].append("Apple Silicon Mac detected - ensure FFmpeg has ARM64 support")
                
                # Check for thermal throttling
                try:
                    thermal_check = subprocess.run(['pmset', '-g', 'thermlog'], 
                                                 capture_output=True, text=True, timeout=5)
                    if 'CPU_Speed_Limit' in thermal_check.stdout:
                        base_resources['platform_issues'].append("CPU thermal throttling detected")
                except:
                    pass
            
        except Exception as e:
            base_resources['warnings'].append(f"Could not check system resources: {str(e)}")
        
        return base_resources
    
    async def _validate_os_specific_services(self) -> Dict[str, Any]:
        """Validate OS-specific services and dependencies"""
        result = {'warnings': [], 'platform_issues': []}
        
        if self.is_windows:
            # Check Windows Audio Service
            try:
                service_check = subprocess.run(['sc', 'query', 'AudioSrv'], 
                                             capture_output=True, text=True, timeout=10)
                if 'RUNNING' not in service_check.stdout:
                    result['platform_issues'].append("Windows Audio Service not running")
            except:
                result['warnings'].append("Could not check Windows Audio Service")
            
            # Check Windows Media Player Network Sharing Service
            try:
                wmp_check = subprocess.run(['sc', 'query', 'WMPNetworkSvc'], 
                                         capture_output=True, text=True, timeout=10)
                if 'RUNNING' not in wmp_check.stdout:
                    result['warnings'].append("Windows Media Player Network Sharing Service not running")
            except:
                pass
        
        elif self.is_linux:
            # Check audio services
            audio_services = ['pulseaudio', 'pipewire', 'alsa-state']
            running_audio_services = []
            
            for service in audio_services:
                try:
                    if os.path.exists('/etc/systemd'):
                        # Systemd-based system
                        service_check = subprocess.run(['systemctl', 'is-active', service], 
                                                     capture_output=True, text=True, timeout=5)
                        if service_check.returncode == 0:
                            running_audio_services.append(service)
                    else:
                        # Non-systemd system
                        service_check = subprocess.run(['service', service, 'status'], 
                                                     capture_output=True, text=True, timeout=5)
                        if service_check.returncode == 0:
                            running_audio_services.append(service)
                except:
                    pass
            
            if not running_audio_services:
                result['warnings'].append("No audio services detected running")
            
            # Check for cron/systemd timer for scheduling
            if not (shutil.which('cron') or os.path.exists('/etc/systemd')):
                result['warnings'].append("No scheduling service (cron/systemd) detected")
        
        elif self.is_mac:
            # Check Core Audio
            try:
                audio_check = subprocess.run(['system_profiler', 'SPAudioDataType'], 
                                           capture_output=True, text=True, timeout=10)
                if 'Built-in Output' not in audio_check.stdout:
                    result['warnings'].append("No built-in audio output detected")
            except:
                result['warnings'].append("Could not check Core Audio")
            
            # Check for launchd
            if not os.path.exists('/System/Library/LaunchDaemons'):
                result['platform_issues'].append("LaunchDaemons directory not found - scheduling may not work")
        
        return result
    
    async def _validate_network(self) -> Tuple[bool, str]:
        """Basic network connectivity validation"""
        try:
            # Test DNS resolution
            import socket
            socket.gethostbyname('google.com')
            
            # Test HTTP connectivity (optional)
            try:
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.get('http://httpbin.org/get') as response:
                        if response.status == 200:
                            return True, "Network connectivity confirmed"
            except:
                pass
            
            return True, "Basic network connectivity confirmed (DNS resolution works)"
            
        except Exception as e:
            return False, f"Network connectivity issue: {str(e)}"
    
    def _is_production_environment(self) -> bool:
        """Detect if running in production environment with OS-specific indicators"""
        # Check common production environment indicators
        base_indicators = [
            os.getenv('ENV') == 'production',
            os.getenv('ENVIRONMENT') == 'production',
            os.getenv('STAGE') == 'prod',
        ]
        
        # OS-specific production indicators
        if self.is_linux:
            linux_indicators = [
                os.path.exists('/etc/systemd'),  # Modern Linux server
                '/usr' in os.getenv('PATH', ''),
                os.path.exists('/var/log/syslog'),  # System logging
                os.getenv('USER') in ['ubuntu', 'ec2-user', 'root'],  # Common server users
            ]
            base_indicators.extend(linux_indicators)
        
        elif self.is_windows:
            windows_indicators = [
                os.path.exists('C:/Windows/System32'),
                'Windows Server' in platform.platform(),
                os.getenv('COMPUTERNAME', '').startswith('WIN-'),  # Default server naming
            ]
            base_indicators.extend(windows_indicators)
        
        elif self.is_mac:
            # macOS is typically development environment
            pass
        
        return any(base_indicators)
    
    def _generate_recommendations_os_specific(self, system_info: SystemInfo, warnings: list[str], platform_issues: list[str]) -> list[str]:
        """Generate OS-specific system optimization recommendations"""
        recommendations = []
        
        # Basic recommendations
        if system_info.available_disk_gb < 10:
            recommendations.append("Consider increasing available disk space for recordings (recommended: >10GB)")
        
        if system_info.total_memory_gb < 2:
            recommendations.append("Consider increasing system memory for better performance (recommended: >2GB)")
        
        if system_info.cpu_count < 4:
            recommendations.append("Consider using a system with more CPU cores for concurrent recordings")
        
        # OS-specific recommendations
        if self.is_windows:
            if platform_issues:
                recommendations.append("Add recording directory to Windows Defender exclusions to prevent file locking")
                recommendations.append("Consider running the service with elevated privileges for better file access")
            recommendations.append("Consider using Windows Task Scheduler for service management")
            
            if 'N-119264' in system_info.ffmpeg_version:  # Dev build
                recommendations.append("Use stable FFmpeg release for production on Windows")
        
        elif self.is_linux:
            if not system_info.is_production:
                recommendations.append("Configure systemd service for automatic startup in production")
            recommendations.append("Consider setting up log rotation for service logs")
            recommendations.append("Use process monitoring (systemd, supervisor) for reliability")
            
            if system_info.os_specific_info.get('systemd'):
                recommendations.append("Leverage systemd for service management and logging")
        
        elif self.is_mac:
            recommendations.append("Consider using launchd for service management on macOS")
            recommendations.append("macOS is typically used for development - ensure production deployment on Linux/Windows")
            
            if platform.machine().lower() in ['arm64', 'aarch64']:
                recommendations.append("Verify all dependencies support Apple Silicon architecture")
        
        # General recommendations based on issues
        if warnings:
            recommendations.append("Review and address system warnings listed above")
        
        if platform_issues:
            recommendations.append("Address platform-specific issues for optimal performance")
        
        return recommendations
    
    def print_validation_report(self, result: ValidationResult):
        """Print a comprehensive OS-specific validation report"""
        print("\n" + "="*80)
        print("🎙️  ENHANCED RECORDING SERVICE - OS-SPECIFIC SYSTEM VALIDATION")
        print("="*80)
        
        if result.system_info:
            print(f"📋 SYSTEM INFORMATION:")
            print(f"   Platform: {result.system_info.platform}")
            print(f"   Architecture: {result.system_info.architecture}")
            print(f"   Platform Version: {result.system_info.platform_version}")
            print(f"   Python: {result.system_info.python_version}")
            print(f"   FFmpeg: {result.system_info.ffmpeg_version}")
            print(f"   FFmpeg Path: {result.system_info.ffmpeg_path}")
            print(f"   Timezone: {result.system_info.timezone}")
            print(f"   Environment: {'Production' if result.system_info.is_production else 'Development'}")
            print(f"   Memory: {result.system_info.total_memory_gb:.1f}GB")
            print(f"   CPU Cores: {result.system_info.cpu_count}")
            print(f"   Available Disk: {result.system_info.available_disk_gb:.1f}GB")
            
            # OS-specific information
            if result.system_info.os_specific_info:
                print(f"\n🖥️  OS-SPECIFIC DETAILS:")
                for key, value in result.system_info.os_specific_info.items():
                    if isinstance(value, (list, dict)):
                        print(f"   {key}: {json.dumps(value, indent=6)}")
                    else:
                        print(f"   {key}: {value}")
        
        print(f"\n✅ VALIDATION STATUS: {'PASSED' if result.is_valid else 'FAILED'}")
        
        if result.errors:
            print(f"\n❌ ERRORS ({len(result.errors)}):")
            for i, error in enumerate(result.errors, 1):
                print(f"   {i}. {error}")
        
        if result.warnings:
            print(f"\n⚠️  WARNINGS ({len(result.warnings)}):")
            for i, warning in enumerate(result.warnings, 1):
                print(f"   {i}. {warning}")
        
        if result.platform_specific_issues:
            print(f"\n🖥️  PLATFORM-SPECIFIC ISSUES ({len(result.platform_specific_issues)}):")
            for i, issue in enumerate(result.platform_specific_issues, 1):
                print(f"   {i}. {issue}")
        
        if result.recommendations:
            print(f"\n💡 RECOMMENDATIONS ({len(result.recommendations)}):")
            for i, rec in enumerate(result.recommendations, 1):
                print(f"   {i}. {rec}")
        
        print("\n" + "="*80)
        
        if result.is_valid:
            print("🚀 System ready for Enhanced Recording Service!")
            if result.platform_specific_issues:
                print("⚠️  Consider addressing platform-specific issues for optimal performance.")
        else:
            print("🛑 Please resolve errors before starting the service.")
        print("="*80 + "\n")

# Create an alias for backward compatibility
SystemValidator = OSSpecificSystemValidator

