from fastapi import FastAPI

from routers import holidays as holidays_router
from routers import top100 as top100_router
from routers import analysis as analysis_router

app = FastAPI()
app.include_router(holidays_router.router)
app.include_router(top100_router.router)
app.include_router(analysis_router.router)

# 앱 시작 시 티커 맵 로드
# @app.on_event("startup")
# async def startup_event():
#     load_ticker_map()
