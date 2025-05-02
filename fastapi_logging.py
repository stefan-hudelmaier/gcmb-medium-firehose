from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import json
import secrets
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = secrets.token_hex(8)
        
        # Log request
        await self._log_request(request, request_id)
        
        # Get request start time
        start_time = datetime.now()
        
        # Process the request and get response
        response = await call_next(request)
        
        # Calculate request duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log response
        await self._log_response(response, request_id, duration)
        
        return response
    
    async def _log_request(self, request: Request, request_id: str):
        headers = dict(request.headers)
        
        try:
            # Read request body
            body = await request.body()
            if body:
                try:
                    body_json = json.loads(body)
                    body_text = json.dumps(body_json, indent=2)
                except json.JSONDecodeError:
                    body_text = body.decode()
            else:
                body_text = ""
        except Exception:
            body_text = "<binary data>"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
            "body": body_text
        }
        
        logger.info(f"SERVER REQUEST [{request_id}]:\n{json.dumps(log_data, indent=2)}")
    
    async def _log_response(self, response: Response, request_id: str, duration: float):
        headers = dict(response.headers)
        
        try:
            # Get response body if it exists
            if isinstance(response, Response):
                body = response.body
            else:
                # For StreamingResponse and other types, we can't log the body
                body = b""
            
            if body:
                try:
                    body_json = json.loads(body)
                    body_text = json.dumps(body_json, indent=2)
                except json.JSONDecodeError:
                    body_text = body.decode()
            else:
                body_text = ""
        except Exception:
            body_text = "<binary data>"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "status_code": response.status_code,
            "duration": f"{duration:.3f}s",
            "headers": headers,
            "body": body_text
        }
        
        logger.info(f"SERVER RESPONSE [{request_id}]:\n{json.dumps(log_data, indent=2)}")
