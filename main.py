# main.py
from fastapi_limiter import FastAPILimiter
import routes
from contextlib import asynccontextmanager
from util.enums import Environment, Color
from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from config.settings import settings
from config.cache import close_redis, get_redis
from fastapi.responses import JSONResponse
from util.logger import init_logger


async def _real_ip(request: Request) -> str:
    if settings.TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@asynccontextmanager
async def lifespan(fastApi: FastAPI):
    try:
        # Warm Redis
        init_logger()
        print(f"{Color.GREEN}Initializing...{Color.RESET}")
        redis = await get_redis()
        await FastAPILimiter.init(redis, identifier=_real_ip)
        print(f"{Color.BLUE}Server Started{Color.RESET}")
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
    allow_origins=[settings.ALLOWED_ORIGIN],
    allow_credentials=True,  # Allow cookies and other credentials
    allow_methods=["GET", "POST"],  # Allowed HTTP Methods
    allow_headers=["Authorization", "Content-Type", "Accept"],  # Allowed HTTP Headers
)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.exception_handler(429)
async def ratelimit_handler(request: Request, exc):
    return JSONResponse(
        status_code=429,
        content={
            "ok": False,
            "error": "rate_limited",
            "message": "Too many requests. Try again in 60s.",
        },
        headers={"Retry-After": "60"},
    )


routes.register_routes(app)

if __name__ == "__main__":
    import uvicorn

    reload = settings.APP_ENV == Environment.DEV
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=reload)
