# Create app/apiv1/http/streaming/StreamController.py
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import logging
import urllib.parse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/proxy")
async def proxy_stream(url: str = Query(..., description="Stream URL to proxy")):
    """Simple stream proxy for HTTP to HTTPS conversion"""
    try:
        # Decode the URL
        decoded_url = urllib.parse.unquote(url)
        
        # Validate URL
        if not decoded_url.startswith('http://') and not decoded_url.startswith('https://'):
            raise HTTPException(status_code=400, detail="Invalid URL")
        
        # Stream the content
        async def stream_generator():
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream('GET', decoded_url) as response:
                    if response.status_code != 200:
                        raise HTTPException(status_code=response.status_code, detail="Stream not available")
                    
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        if chunk:
                            yield chunk
        
        return StreamingResponse(
            stream_generator(),
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
                "Connection": "keep-alive"
            }
        )
        
    except Exception as e:
        logger.error(f"Stream proxy error: {e}")
        raise HTTPException(status_code=500, detail="Stream proxy failed")