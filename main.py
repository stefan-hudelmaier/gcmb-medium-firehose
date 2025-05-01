from fastapi import FastAPI, Request, Response, HTTPException, Header, status
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib
import hmac
import json
from typing import Optional, Callable, Any
import httpx
import secrets
from pathlib import Path
import os
from urllib.parse import urljoin
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import logging
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables
BASE_URL = os.getenv("WEBSUB_BASE_URL", "http://localhost:8080")
HUB_URL = os.getenv("WEBSUB_HUB_URL", "http://medium.superfeedr.com")
CALLBACK_PATH = "/webhook"

class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = secrets.token_hex(8)
        
        # Log request
        await self._log_request(request, request_id)
        
        # Get request start time
        start_time = time.time()
        
        # Process the request and get response
        response = await call_next(request)
        
        # Calculate request duration
        duration = time.time() - start_time
        
        # Log response
        await self._log_response(response, request_id, duration)
        
        return response
    
    async def _log_request(self, request: Request, request_id: str):
        headers = dict(request.headers)
        body = await request.body()
        
        try:
            body_text = body.decode()
            if body_text:
                try:
                    body_json = json.loads(body_text)
                    body_text = json.dumps(body_json, indent=2)
                except json.JSONDecodeError:
                    pass
        except UnicodeDecodeError:
            body_text = f"<binary data of length {len(body)}>"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
            "body": body_text
        }
        
        logger.info(f"REQUEST [{request_id}]:\n{json.dumps(log_data, indent=2)}")
    
    async def _log_response(self, response: Response, request_id: str, duration: float):
        headers = dict(response.headers)
        
        # Get response body if it exists
        body = b""
        if hasattr(response, "body"):
            body = response.body
        
        try:
            body_text = body.decode()
            if body_text:
                try:
                    body_json = json.loads(body_text)
                    body_text = json.dumps(body_json, indent=2)
                except json.JSONDecodeError:
                    pass
        except UnicodeDecodeError:
            body_text = f"<binary data of length {len(body)}>"
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "status_code": response.status_code,
            "duration": f"{duration:.3f}s",
            "headers": headers,
            "body": body_text
        }
        
        logger.info(f"RESPONSE [{request_id}]:\n{json.dumps(log_data, indent=2)}")

class LoggingTransport(httpx.AsyncBaseTransport):
    def __init__(self, transport: httpx.AsyncBaseTransport):
        self._transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Generate request ID
        request_id = secrets.token_hex(8)
        
        # Log request
        self._log_request(request, request_id)
        
        # Get request start time
        start_time = time.time()
        
        # Send request and get response
        response = await self._transport.handle_async_request(request)
        
        # Calculate request duration
        duration = time.time() - start_time
        
        # Log response
        self._log_response(response, request_id, duration)
        
        return response
    
    def _log_request(self, request: httpx.Request, request_id: str):
        headers = dict(request.headers)
        
        try:
            body = request.read()
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
    
    def _log_response(self, response: httpx.Response, request_id: str, duration: float):
        headers = dict(response.headers)
        
        try:
            body = response.read()
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
        
        logger.info(f"CLIENT RESPONSE [{request_id}]:\n{json.dumps(log_data, indent=2)}")

app = FastAPI()
app.add_middleware(RequestResponseLoggingMiddleware)

# Store subscriptions and secrets in memory (in production, use a proper database)
subscriptions = {}
hub_secrets = {}  # Map of topic to secret

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify the hub signature of the payload"""
    if not signature or not signature.startswith("sha1="):
        return False
    
    expected_signature = "sha1=" + hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha1
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@app.get("/")
async def root():
    return {"message": "WebSub Hub is running"}

@app.get("/webhook")
async def webhook_verification(
    mode: str,
    topic: str,
    challenge: Optional[str] = None,
    lease_seconds: Optional[int] = None
):
    """Handle WebSub subscription verification"""
    if mode == "subscribe" or mode == "unsubscribe":
        if challenge:
            # Return the challenge code as plain text for verification
            return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=400, detail="Invalid verification request")

@app.post("/webhook")
async def webhook_handler(
    request: Request,
    x_hub_signature: Optional[str] = Header(None),
    topic: str = Header(..., alias="X-Hub-Topic")
):
    """Handle WebSub content distribution"""
    body = await request.body()
    
    # Verify signature if a secret is set for this topic
    if topic in hub_secrets:
        if not verify_signature(body, x_hub_signature, hub_secrets[topic]):
            raise HTTPException(status_code=403, detail="Invalid signature")
    
    try:
        # Parse the content
        content = json.loads(body)
        
        # Distribute content to all subscribers for this topic
        if topic in subscriptions:
            # In a production environment, this should be done asynchronously
            # and with proper error handling for each subscriber
            for callback_url in subscriptions[topic]:
                # Here you would make an HTTP POST request to each subscriber
                # This is a placeholder for the actual distribution logic
                print(f"Distributing to {callback_url}: {content}")
        
        return {"status": "success", "message": "Content distributed", "subscriber_count": len(subscriptions.get(topic, []))}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")


async def subscribe_to_topics():
    """Read topics from JSON file and send subscription requests to WebSub hub"""
    try:
        topics_file = Path("topics.json")
        if not topics_file.exists():
            print("topics.json not found")
            return
        
        with open(topics_file) as f:
            config = json.load(f)
        
        # Generate callback URL from base URL
        callback_url = urljoin(BASE_URL, CALLBACK_PATH)
        print(f"Using callback URL: {callback_url}")
        print(f"Using hub URL: {HUB_URL}")
        
        # Create client with logging transport
        transport = httpx.AsyncHTTPTransport()
        logging_transport = LoggingTransport(transport)
        async with httpx.AsyncClient(transport=logging_transport) as client:
            for topic_url in config["topics"]:
                # Prepare subscription request parameters
                params = {
                    "hub.mode": "subscribe",
                    "hub.topic": topic_url,
                    "hub.callback": callback_url,
                    "hub.verify": "async"
                }
                
                try:
                    # Send subscription request to the hub
                    response = await client.post(HUB_URL, data=params)
                    if response.status_code in [200, 202]:
                        print(f"Subscription request sent for {topic_url}")
                        # Store subscription intent (actual subscription will be confirmed via webhook)
                        if topic_url not in subscriptions:
                            subscriptions[topic_url] = set()
                        subscriptions[topic_url].add(callback_url)
                    else:
                        print(f"Failed to subscribe to {topic_url}: Hub returned {response.status_code}")
                        print(f"Hub response: {response.text}")
                except Exception as e:
                    print(f"Error subscribing to {topic_url}: {str(e)}")
    
    except json.JSONDecodeError:
        print("Error: Invalid JSON in topics.json")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
