import os
import base64
import tempfile
import shutil
from typing import Union, Optional
from fastapi import UploadFile
import aiofiles
import time
from io import BytesIO
from sqlalchemy.ext.asyncio import AsyncSession

async def process_file_to_upload_type(file_data: Union[str, bytes, UploadFile]) -> Optional[UploadFile]:
    try:
        print(file_data)
        if isinstance(file_data, UploadFile):
            return file_data      
        # Create a temporary file to hold the binary data
        temp_file_handle, temp_file_path = tempfile.mkstemp(suffix=".tmp")
        
        # Handle different input types
        if isinstance(file_data, bytes):
            # It's already binary data
            binary_content = file_data
            content_type = "application/octet-stream"
            filename = f"file_{int(time.time())}.bin"
            
        elif isinstance(file_data, str):
            # Check if it's a base64 data URL
            if file_data.startswith(('data:image/', 'data:video/', 'data:audio/')):
                # Extract content type and data
                content_type = file_data.split(';')[0].split(':')[1]
                base64_data = file_data.split(',')[1]
                binary_content = base64.b64decode(base64_data)
                
                # Set filename with appropriate extension
                ext = content_type.split('/')[1]
                filename = f"file_{int(time.time())}.{ext}"
                
            # Check if it's a path to an existing file
            elif os.path.exists(file_data):
                async with aiofiles.open(file_data, 'rb') as f:
                    binary_content = await f.read()
                content_type = "application/octet-stream"
                filename = os.path.basename(file_data)
                
            # Assume it's just a string (treat as text)
            else:
                binary_content = file_data.encode('utf-8')
                content_type = "text/plain"
                filename = f"file_{int(time.time())}.txt"
        else:
            # Unsupported type
            os.close(temp_file_handle)
            os.unlink(temp_file_path)
            return None
            
        # Write the binary content to the temp file
        async with aiofiles.open(temp_file_path, 'wb') as f:
            await f.write(binary_content)
            
        # Create a file-like object from the temp file
        file_obj = open(temp_file_path, 'rb')
        
        # Create and configure the UploadFile object
        upload_file = UploadFile(
            filename=filename,
            file=file_obj,
            content_type=content_type,
        )
        
        print(upload_file)
        # Add cleanup callback to remove the temp file when done
        original_close = upload_file.file.close
        
        def close_and_cleanup():
            original_close()
            os.close(temp_file_handle)
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
        upload_file.file.close = close_and_cleanup
        
        return upload_file
        
    except Exception as e:
        print(f"Error converting to UploadFile: {str(e)}")
        # Clean up any temp files if they exist
        if 'temp_file_handle' in locals():
            os.close(temp_file_handle)
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return None



def convert_status_to_boolean(status_value):
    if isinstance(status_value, bool):
        return status_value
        
    if isinstance(status_value, str):
        # Convert string to lowercase for case-insensitive comparison
        status_str = status_value.lower().strip()
        
        # Check for various "true" representations
        if status_str in ('true', 't', 'yes', 'y', '1', 'on', 'active'):
            return 1
            
        # Check for various "false" representations
        if status_str in ('false', 'f', 'no', 'n', '0', 'off', 'inactive'):
            return 0
    
    # For numeric types
    if isinstance(status_value, (int, float)):
        return bool(status_value)
        
    # Default to False for None or unrecognized values
    return 0



#Logs
async def log_system_error(db: AsyncSession, service: str, error: Exception, access_function: str, **kwargs):
    try:
        # Get error details
        error_type = type(error).__name__
        error_message = str(error)
        
        # Get stack trace
        stack_trace = traceback.format_exc()
        
        # Try to get line number and file path from traceback
        tb = traceback.extract_tb(error.__traceback__)
        if tb:
            last_trace = tb[-1]
            line_number = last_trace.lineno
            file_path = last_trace.filename
        else:
            line_number = None
            file_path = None
        
        # Extract error code if it's an HTTPException
        error_code = None
        if hasattr(error, 'status_code'):
            error_code = str(error.status_code)
        elif hasattr(error, 'code'):
            error_code = str(error.code)
        
        # Create error log entry
        error_log = SystemErrorLog(
            service=service,
            access_function=access_function,
            error_message=error_message,
            error_type=error_type,
            error_code=error_code,
            stack_trace=stack_trace,
            line_number=line_number,
            file_path=file_path,
            user_id=kwargs.get('user_id'),
            user_ip=kwargs.get('user_ip'),
            user_agent=kwargs.get('user_agent'),
            request_path=kwargs.get('request_path'),
            request_method=kwargs.get('request_method'),
            request_data=kwargs.get('request_data'),
            severity=kwargs.get('severity', 'ERROR'),
            environment=kwargs.get('environment'),
            notes=kwargs.get('notes'),
            resolved='no',
            status=True,
            state=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(error_log)
        await db.commit()
        
        return error_log
        
    except Exception as e:
        # If we can't log the error, at least print it
        print(f"Failed to log error: {e}")
        print(f"Original error: {error}")
        await db.rollback()
        return None