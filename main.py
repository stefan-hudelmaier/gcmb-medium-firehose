from fastapi import FastAPI, Request, Response, HTTPException, Header, status, Query
from fastapi.responses import PlainTextResponse
import hashlib
import hmac
import json
from typing import Optional
import secrets
from pathlib import Path
import os
from urllib.parse import urljoin
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import logging
import time
from datetime import datetime
from database import Database
from http_client_logging import get_http_client, cleanup_http_client
from fastapi_logging import RequestResponseLoggingMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment variables
BASE_URL = os.getenv("WEBSUB_BASE_URL", "http://localhost:8080")
HUB_URL = os.getenv("WEBSUB_HUB_URL", "http://medium.superfeedr.com")
CALLBACK_PATH = "/webhook"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application"""
    # Startup
    await subscribe_to_topics()
    yield
    # Shutdown - cleanup HTTP client
    await cleanup_http_client()

app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestResponseLoggingMiddleware)

# Store subscriptions and secrets in memory (in production, use a proper database)
subscriptions = {}
hub_secrets = {}  # Map of topic to secret
db = Database()

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

@app.get("/webhook")
async def root():
    return {"message": "WebSub Hub is running"}

@app.get("/webhook")
async def webhook_verification(
    mode: str = Query(..., alias="hub.mode"),
    topic: str = Query(..., alias="hub.topic"),
    challenge: Optional[str] = Query(None, alias="hub.challenge"),
    lease_seconds: Optional[int] = Query(None, alias="hub.lease_seconds")
):
    """Handle WebSub subscription verification"""
    if mode == "subscribe" or mode == "unsubscribe":
        if challenge:
            # Return the challenge code as plain text for verification
            return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=400, detail="Invalid verification request")


def extract_topic_from_link(link_header):
    """
    link header example: <https://example.com/feed>; rel="self"
    """
    return link_header.split(";")[0].strip("<>")


@app.post("/webhook")
async def webhook_handler(
    request: Request,
    x_hub_signature: Optional[str] = Header(None),
    link_header: str = Header(..., alias="link")
):
    """Handle WebSub content distribution"""
    body = await request.body()
    
    topic = extract_topic_from_link(link_header)
    
    # Verify signature if a secret is set for this topic
    if topic in hub_secrets:
        if not verify_signature(body, x_hub_signature, hub_secrets[topic]):
            raise HTTPException(status_code=403, detail="Invalid signature")
    
    try:
        feed = atoma.parse_atom_bytes(body)
        for entry in feed.entries:
            logger.info(f"Received entry: {entry.id_} {entry.title}")
            # Store post ID in database
            if db.add_post(entry.id_):
                logger.info(f"New post added: {entry.id_}")
            else:
                logger.debug(f"Post already exists: {entry.id_}")
        
        # Distribute content to all subscribers for this topic
        if topic in subscriptions:
            # In a production environment, this should be done asynchronously
            # and with proper error handling for each subscriber
            for callback_url in subscriptions[topic]:
                # Here you would make an HTTP POST request to each subscriber
                # This is a placeholder for the actual distribution logic
                print(f"Distributing to {callback_url}: {feed}")
        
        return {"status": "success", "message": "Content distributed", "subscriber_count": len(subscriptions.get(topic, []))}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")


async def subscribe_to_topics():

    # wait a little so that server finishes startup
    await asyncio.sleep(1)
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
        logger.info(f"Using callback URL: {callback_url}")
        logger.info(f"Using hub URL: {HUB_URL}")
        
        # Get the logging client
        client = await get_http_client()

        for hub in config["hubs"]:
            hub_url = hub['url']
            for topic_url in hub["topics"]:
                # Prepare subscription request parameters
                params = {
                    "hub.mode": "subscribe",
                    "hub.topic": topic_url,
                    "hub.callback": callback_url,
                    "hub.verify": "async"
                }

                try:
                    # Send subscription request to the hub
                    response = await client.post(hub_url, data=params)
                    if response.status_code in [200, 202, 204]:
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
    #except Exception as e:
    #    print(f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
