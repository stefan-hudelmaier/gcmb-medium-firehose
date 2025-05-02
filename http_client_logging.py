import httpx
import json
import secrets
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class LoggingTransport(httpx.AsyncBaseTransport):
    def __init__(self, transport: httpx.AsyncBaseTransport):
        self._transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Generate request ID
        request_id = secrets.token_hex(8)
        
        # Log request
        await self._log_request(request, request_id)
        
        # Get request start time
        start_time = datetime.now()
        
        # Send request and get response
        response = await self._transport.handle_async_request(request)
        
        # Calculate request duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log response
        await self._log_response(response, request_id, duration)
        
        return response
    
    async def _log_request(self, request: httpx.Request, request_id: str):
        headers = dict(request.headers)
        
        try:
            # Create a copy of the request to read the body
            body = request.content
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
        
        logger.info(f"CLIENT REQUEST [{request_id}]:\n{json.dumps(log_data, indent=2)}")
    
    async def _log_response(self, response: httpx.Response, request_id: str, duration: float):
        headers = dict(response.headers)
        
        try:
            # Read the response content without consuming the stream
            body = await response.aread()
            if body:
                try:
                    body_json = json.loads(body)
                    body_text = json.dumps(body_json, indent=2)
                except json.JSONDecodeError:
                    body_text = body.decode()
            else:
                body_text = ""
            
            # Create a new response with the same content
            response._content = body
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
        
        logger.info(f"CLIENT RESPONSE [{request_id}]:\n{json.dumps(log_data, indent=2)}")

class LoggingClient(httpx.AsyncClient):
    """Custom HTTP client that automatically uses logging transport"""
    def __init__(self, **kwargs):
        transport = httpx.AsyncHTTPTransport()
        logging_transport = LoggingTransport(transport)
        super().__init__(transport=logging_transport, **kwargs)

# Global client instance
http_client: Optional[LoggingClient] = None

async def get_http_client() -> LoggingClient:
    """Get or create a logging HTTP client instance"""
    global http_client
    if http_client is None:
        http_client = LoggingClient()
    return http_client

async def cleanup_http_client():
    """Close the HTTP client"""
    global http_client
    if http_client is not None:
        await http_client.aclose()
        http_client = None
