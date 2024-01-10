import asyncio
import logging
from os import environ
from httpx import AsyncClient
from fastapi import FastAPI, HTTPException, Response
import backoff

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the target server URL
target_server_url = environ.get('TARGET_SERVER_URL')

async def forward_request(request):
    async with AsyncClient() as client:
        # Forward the request to the target server
        response = await client.request(
            request.method,
            target_server_url + request.url.path,
            headers=dict(request.headers),
            content=request.stream(),
        )
        return response

@backoff.on_exception(backoff.expo, (Exception,), max_tries=10)
async def forward_request_with_retry(request):
    return await forward_request(request)

@app.middleware("http")
async def reverse_proxy(request, call_next):
    try:
        # Forward the request to the target server with retries and backoff
        response = await forward_request_with_retry(request)

        # Log 500 and 502 errors along with response body
        if response.status_code in [500, 502]:
            logger.error(f"Received {response.status_code} error from the target server. Response body: {response.text}")

        # Create a new FastAPI response with the forwarded content
        content = response.read()
        new_response = Response(content=content, status_code=response.status_code, headers=response.headers)

        return new_response

    except Exception as e:
        # Log other exceptions
        logger.error(f"An error occurred while forwarding the request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
