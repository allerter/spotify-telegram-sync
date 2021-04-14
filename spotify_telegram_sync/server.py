import asyncio
import logging

import uvicorn
from bot import prepare_clients, update_playlist
from constants import SERVER_PORT
from fastapi import FastAPI

app = FastAPI()
logger = logging.getLogger("sts.server")


@app.get("/")
async def read_root():
    return "OK"


async def check_playlist():
    try:
        queue = asyncio.Queue()
        await prepare_clients(queue, use_httpx=False)
        clients = await queue.get()
        await update_playlist(**clients)
    except Exception as e:
        logger.error(e)
        raise e
    finally:
        await clients["telegram"].disconnect()
        await clients["spotify"].close()


@app.get("/update_playlist")
async def update_playlist_path():
    asyncio.ensure_future(check_playlist())
    return "I'll check"


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
