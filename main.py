from fastapi import FastAPI, Request, Response, HTTPException, Header
from fastapi.responses import PlainTextResponse
import hashlib
import hmac
import json
from typing import Optional
import httpx
import secrets
from pathlib import Path
import os
from urllib.parse import urljoin


# Get base URL from environment variable or use default
BASE_URL = os.getenv("WEBSUB_BASE_URL", "http://localhost:8080")
CALLBACK_PATH = "/webhook"

app = FastAPI()

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
    """Read topics from JSON file and send subscription requests"""
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
        
        async with httpx.AsyncClient() as client:
            for topic_url in config["topics"]:
                # Generate a random challenge string
                challenge = secrets.token_urlsafe(32)
                
                # Prepare subscription request parameters
                params = {
                    "hub.mode": "subscribe",
                    "hub.topic": topic_url,
                    "hub.callback": callback_url,
                    "hub.challenge": challenge
                }
                
                try:
                    # Send subscription request to the hub
                    response = await client.get(topic_url, params=params)
                    if response.status_code == 200 and response.text == challenge:
                        print(f"Successfully subscribed to {topic_url}")
                        # Store subscription
                        if topic_url not in subscriptions:
                            subscriptions[topic_url] = set()
                        subscriptions[topic_url].add(callback_url)
                    else:
                        print(f"Failed to subscribe to {topic_url}: Invalid response")
                except Exception as e:
                    print(f"Error subscribing to {topic_url}: {str(e)}")
    
    except json.JSONDecodeError:
        print("Error: Invalid JSON in topics.json")
    except Exception as e:
        print(f"Error: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Subscribe to topics when the application starts"""
    await subscribe_to_topics()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

