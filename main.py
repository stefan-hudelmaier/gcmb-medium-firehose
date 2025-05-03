import asyncio
import hashlib
import hmac
import json
import logging
import os
import traceback
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import atoma
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.responses import PlainTextResponse

from database import Database
from fastapi_logging import RequestResponseLoggingMiddleware
from http_client_logging import get_http_client, cleanup_http_client
from mqtt_publish import MqttPublisher

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment variables
BASE_URL = os.getenv("WEBSUB_BASE_URL", "http://localhost:8080")
CALLBACK_PATH = "/websub/webhook"

# Store subscriptions and secrets in memory (in production, use a proper database)
subscriptions = {}
hub_secrets = {}  # Map of topic to secret
db = Database()
mqtt_publish = MqttPublisher()

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application"""
    # Startup
    post_count = db.count_posts()
    logger.info(f"Starting server with {post_count} previously seen posts in database")
    
    # Start subscription expiry checker
    expiry_checker = asyncio.create_task(check_expiring_subscriptions())
    
    # Subscribe to topics asynchronously so that the server can finish starting and is available
    asyncio.create_task(subscribe_to_topics())
    
    yield
    
    # Shutdown
    expiry_checker.cancel()
    try:
        await expiry_checker
    except asyncio.CancelledError:
        pass
    
    await cleanup_http_client()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestResponseLoggingMiddleware)


@app.get(CALLBACK_PATH)
async def webhook_verification(
    mode: str = Query(..., alias="hub.mode"),
    topic: str = Query(..., alias="hub.topic"),
    challenge: Optional[str] = Query(None, alias="hub.challenge"),
    lease_seconds: Optional[int] = Query(None, alias="hub.lease_seconds")
):
    """Handle WebSub subscription verification"""
    logger.info(f"Received verification request: mode={mode}, topic={topic}")
    
    if mode == "subscribe":
        if topic not in subscriptions:
            logger.warning(f"Received verification for unknown subscription: {topic}")
            raise HTTPException(status_code=404, detail="Subscription not found")

        lease_seconds = int(lease_seconds) if lease_seconds else 24 * 60 * 60  # Default to 24 hours

        # Find the hub URL from our config
        with open("topics.json") as f:
            config = json.load(f)
            hub_url = next((hub['url'] for hub in config['hubs']
                          if topic in hub['topics']), None)

        if hub_url:
            db.add_subscription(topic, hub_url, lease_seconds)
            logger.info(f"Stored subscription lease for {topic}, expires in {lease_seconds} seconds")
        
        # Return the challenge code to confirm subscription
        if challenge:
            return PlainTextResponse(content=challenge)
    
    elif mode == "unsubscribe":
        # Handle unsubscribe verification if needed
        if challenge:
            return PlainTextResponse(content=challenge)
    
    raise HTTPException(status_code=400, detail="Invalid verification request")


async def check_expiring_subscriptions():
    """Check for expiring subscriptions and renew them"""
    while True:
        try:
            # Get subscriptions expiring in the next 5 minutes
            expiring = db.get_expiring_subscriptions(within_minutes=5)
            if expiring:
                logger.info(f"Found {len(expiring)} subscription(s) expiring soon")
                
                # Get HTTP client
                client = await get_http_client()
                
                # Try to renew each subscription
                for sub in expiring:
                    logger.info(f"Renewing subscription for {sub.topic_url} (expires {sub.lease_expires})")
                    await subscribe_to_topic(client, sub.hub_url, sub.topic_url)
        
        except Exception as e:
            logger.error(f"Error checking expiring subscriptions: {str(e)}")
            if logger.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
        
        # Check every minute
        await asyncio.sleep(60)


async def subscribe_to_topic(client: httpx.AsyncClient, hub_url: str, topic_url: str, max_retries: int = 20) -> bool:
    """
    Subscribe to a single topic with retry logic
    Returns True if subscription was successful, False otherwise
    """
    params = {
        "hub.mode": "subscribe",
        "hub.topic": topic_url,
        "hub.callback": urljoin(BASE_URL, CALLBACK_PATH),
        "hub.verify": "async"
    }
    
    for attempt in range(max_retries):
        try:
            response = await client.post(hub_url, data=params)
            if response.status_code in [200, 202]:
                logger.info(f"Subscription request sent for {topic_url}")
                return True
            elif response.status_code == 422:
                logger.warning(f"Received 422 for {topic_url}, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait 1 second before retrying
                    continue
            else:
                logger.error(f"Failed to subscribe to {topic_url}: Hub returned {response.status_code}")
                logger.error(f"Hub response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error subscribing to {topic_url}: {str(e)}")
            if logger.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return False
    
    logger.error(f"Failed to subscribe to {topic_url} after {max_retries} attempts")
    return False

async def subscribe_to_topics():
    """Read topics from JSON file and send subscription requests to WebSub hub"""
    # wait a little so that server finishes startup
    await asyncio.sleep(1)
    
    try:
        topics_file = Path("topics.json")
        if not topics_file.exists():
            logger.error("topics.json not found")
            return
        
        with open(topics_file) as f:
            config = json.load(f)
        
        # Generate callback URL from base URL
        callback_url = urljoin(BASE_URL, CALLBACK_PATH)
        logger.info(f"Using callback URL: {callback_url}")
        
        # Get the logging client
        client = await get_http_client()
        
        for hub in config["hubs"]:
            hub_url = hub['url']
            for topic_url in hub["topics"]:
                # Check if we already have an active subscription
                subscription = db.get_subscription(topic_url)
                if subscription:
                    if subscription.lease_expires > datetime.now():
                        logger.info(f"Skipping {topic_url}, subscription active until {subscription.lease_expires}")
                        continue
                    else:
                        logger.info(f"Subscription expired for {topic_url}, renewing")
                
                # Subscribe to topic
                if await subscribe_to_topic(client, hub_url, topic_url):
                    # Store subscription intent (actual subscription will be confirmed via webhook)
                    if topic_url not in subscriptions:
                        subscriptions[topic_url] = set()
                    subscriptions[topic_url].add(callback_url)
    
    except json.JSONDecodeError:
        logger.error("Error: Invalid JSON in topics.json")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if logger.isEnabledFor(logging.DEBUG):
            traceback.print_exc()


@app.post(CALLBACK_PATH)
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
        # First check if this is a status message using ElementTree
        try:
            tree = ET.parse(BytesIO(body))
            root = tree.getroot()
            
            # Remove namespace from tag names for easier checking
            # This handles cases where the feed might use namespaces like {http://www.w3.org/2005/Atom}feed
            ns = root.tag.split('}')[0] + '}' if '}' in root.tag else ''
            root_tag = root.tag.split('}')[-1]
            
            if root_tag == 'feed':
                # Check for an empty id element, this indicates a status message without entries
                for child in root:
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag == 'id':
                        if child.text is None or child.text.strip() == "":
                            logger.info(f"Received status message for topic {topic}: {child.text}")
                            return {"status": "success", "message": "Status message received"}
            
            # If we get here, it's not a status message, parse with atoma
            feed = atoma.parse_atom_bytes(body)
            for entry in feed.entries:
                logger.info(f"Received entry: {entry.id_} {entry.title}")
                # Store post ID in database
                if db.add_post(entry.id_):
                    logger.info(f"New post added: {entry.id_}")
                    # Publish to MQTT
                    mqtt_topic = topic.replace("https://", "").replace("/", "_").replace("\\", "").strip()
                    mqtt_topic = f"medium/medium-firehose/feeds/{mqtt_topic}"
                    mqtt_publish.send_msg(body, mqtt_topic)
                else:
                    logger.info(f"Post already exists: {entry.id_}")
        
            return {"status": "success", "message": "Content distributed"}
            
        except ET.ParseError:
            logger.error("Failed to parse XML")
            raise HTTPException(status_code=400, detail="Invalid XML")
            
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=400, detail="Error processing webhook")


def extract_topic_from_link(link_header):
    """
    link header example: <https://example.com/feed>; rel="self"
    """
    return link_header.split(";")[0].strip("<>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
