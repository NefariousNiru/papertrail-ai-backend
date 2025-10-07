# main.py
import asyncio
import routes
from contextlib import asynccontextmanager
from util.enums import Environment, Color
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from config.settings import settings
from config.cache import close_redis, get_redis


@asynccontextmanager
async def lifespan(fastApi: FastAPI):
    print(f"{Color.GREEN}Server Started{Color.RESET}")
    print(f"{Color.GREEN}Initializing...{Color.RESET}")

    try:
        # Warm Redis
        await get_redis()
    except Exception as e:
        print("Failed to connect to Redis:", e)
        raise

    try:
        yield
    finally:
        try:
            await close_redis()
        except Exception as e:
            print("Error closing Redis:", e)

        print(f"{Color.RED}Server Shutdown{Color.RESET}")


app: FastAPI = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,  # Allow cookies and other credentials
    allow_methods=["GET", "POST"],  # Allowed HTTP Methods
    allow_headers=["Authorization", "Content-Type", "Accept"],  # Allowed HTTP Headers
)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


routes.register_routes(app)

if __name__ == "__main__":
    import uvicorn

    reload = settings.app_env == Environment.DEV
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=reload)
