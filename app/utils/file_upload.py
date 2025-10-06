import os
import uuid
from fastapi import UploadFile, HTTPException
import aiofiles
import shutil
from typing import Tuple
import time
import base64
import io
from app.utils.constants import BASE_URL
# Base configuration
UPLOAD_DIR = "static/uploads/"
ALLOWED_EXTENSIONS = {
    # Image extensions
    ".svg", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    
    # Audio extensions
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".m4a",

    # Video extensions
    ".mp4", ".avi", ".mov", ".wmv", ".mkv",

    # Text extensions
    ".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".srt"
}


def create_upload_dir(absolute_path: str) -> None:
    if not os.path.exists(absolute_path):
        os.makedirs(absolute_path, exist_ok=True)

async def save_upload_file(file: UploadFile, path_url: str) -> Tuple[str, str]:
    try:
        # Create full directory path
        absolute_path = os.path.join(UPLOAD_DIR, path_url).replace('\\', '/')
        create_upload_dir(absolute_path)
        

        # Validate file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        print('This is the file Extenstion Extracted from the File Being Uploaded')
        print(file_ext)
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed"
            )
        # Generate unique filename
        original_name = os.path.splitext(file.filename)[0]
        timestamp = str(int(time.time()))
        unique_filename = f"{original_name}_{timestamp}{file_ext}"
        
        # Create file paths
        file_path = os.path.join(absolute_path, unique_filename).replace('\\', '/')
        file_url = os.path.join(BASE_URL, absolute_path, unique_filename).replace('\\', '/')

        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        
        return file_path, file_url
        
    except Exception as e:
        if 'file_path' in locals() and os.path.exists(file_path):
            remove_file(file_path)
            
        raise HTTPException(
            status_code=500,
            detail=f"Could not upload file: {str(e)}"
        )



def remove_file(file_path: str) -> None:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Remove empty directories
            directory = os.path.dirname(file_path)
            while directory != UPLOAD_DIR.rstrip('/'):
                if os.path.exists(directory) and not os.listdir(directory):
                    os.rmdir(directory)
                    directory = os.path.dirname(directory)
                else:
                    break
                    
    except Exception as e:
        print(f"Error removing file {file_path}: {str(e)}")


def base64_to_upload_file(base64_data: str, filename: str = None) -> UploadFile:
    try:
        # Handle data URI format (data:image/jpeg;base64,...)
        if base64_data.startswith("data:"):
            header, data = base64_data.split(',', 1)
            # Extract MIME type
            mime_type = header.split(':')[1].split(';')[0]
            file_extension = mime_type.split('/')[1]
        else:
            # Plain base64 data
            data = base64_data
            mime_type = "application/octet-stream"
            file_extension = "bin"
        
        # Generate filename if not provided
        if not filename:
            import uuid
            filename = f"upload_{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Decode base64 data
        file_content = base64.b64decode(data)
        
        # Create file-like object
        file_obj = io.BytesIO(file_content)
        
        # Create UploadFile
        upload_file = UploadFile(
            file=file_obj,
            filename=filename,
            headers={"content-type": mime_type}
        )
        
        return upload_file
        
    except Exception as e:
        raise ValueError(f"Failed to convert base64 to UploadFile: {str(e)}")