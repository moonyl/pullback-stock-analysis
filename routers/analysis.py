from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from statistics import mean

from pykrx import stock
import pandas as pd
import numpy as np

from database import db
from routers.holidays import is_business_day

router = APIRouter()

# 종목명-티커 매핑 캐시 (초기화 시 로드)
_ticker_map_cache = {}

def load_ticker_map():
    """코스피, 코스닥 모든 종목의 티커-종목명 매핑을 로드하여 캐시합니다."""
    global _ticker_map_cache
    if not _ticker_map_cache:
        print("Loading ticker map...")
        try:
            all_tickers = stock.get_market_ticker_list(market="ALL")
            temp_map = {}
            for ticker in all_tickers:
                try:
                    name = stock.get_market_ticker_name(ticker)
                    if name:
                        temp_map[name] = ticker
                except Exception as e:
                    print(f"Warning: Could not get name for ticker {ticker}: {e}")
            _ticker_map_cache = temp_map
            print(f"Ticker map loaded with {len(_ticker_map_cache)} entries.")
        except Exception as e:
            print(f"Fatal Error: Failed to load ticker map: {e}")
            _ticker_map_cache = {}

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    load_ticker_map()
    yield

router = APIRouter(lifespan=lifespan)

def check_pullback(ticker: str, date_str: str) -> dict:
    """주어진 티커와 날짜를 기준으로 눌림목 조건을 확인합니다."""
    try:
        start_date = (datetime.strptime(date_str, '%Y%m%d') - timedelta(days=100)).strftime('%Y%m%d')
        df = stock.get_market_ohlcv(fromdate=start_date, todate=date_str, ticker=ticker)

        if len(df) < 60:
            return {"is_pullback": False, "reason": "데이터 부족 (최소 60일 필요)"}

        df['ma5'] = df['종가'].rolling(5).mean()
        df['ma20'] = df['종가'].rolling(20).mean()
        df['ma60'] = df['종가'].rolling(60).mean()
        df['avg_vol_3'] = df['거래량'].rolling(3).mean()

        latest = df.iloc[-1]

        cond1_ma_aligned = bool(latest['ma5'] > latest['ma20'] > latest['ma60'])
        ma20_slope = np.polyfit(range(3), df['ma20'].iloc[-3:], 1)[0]
        cond1_ma20_rising = bool(ma20_slope > 0)

        recent_high_found = False
        avg_vol_rise = 0
        high_date_index = None

        high_window_df = df.iloc[-46:-1]
        valid_highs = high_window_df[high_window_df['종가'] > high_window_df['ma20'] * 1.05]
        if not valid_highs.empty:
            high_date_index = valid_highs.index[-1]
            days_since_high = (df.index[-1] - high_date_index).days
            if days_since_high >= 3 and days_since_high <= 30:
                recent_high_found = True
                high_date_loc = df.index.get_loc(high_date_index)
                if high_date_loc >= 10:
                    avg_vol_rise = df.iloc[high_date_loc - 10:high_date_loc]['거래량'].mean()

        cond3_near_ma20 = bool(pd.notna(latest['ma20']) and (latest['ma20'] * 0.98 <= latest['종가'] <= latest['ma20'] * 1.03))

        cond4_volume_decreased = False
        if recent_high_found and avg_vol_rise > 0 and pd.notna(latest['avg_vol_3']):
            cond4_volume_decreased = latest['avg_vol_3'] < avg_vol_rise * 0.8

        conditions = [bool(cond1_ma_aligned), bool(cond1_ma20_rising), bool(recent_high_found), bool(cond3_near_ma20), bool(cond4_volume_decreased)]
        satisfied = sum(conditions)
        score = round(satisfied / len(conditions), 2)

        is_pullback = satisfied >= 4

        return {
            "is_pullback": is_pullback,
            "score": score,
            "details": {
                "기준일": date_str,
                "종가": latest['종가'],
                "ma5": latest['ma5'],
                "ma20": latest['ma20'],
                "ma60": latest['ma60'],
                "최근3일평균거래량": latest['avg_vol_3'],
                "상승시평균거래량": avg_vol_rise,
                "조건1_정배열": cond1_ma_aligned,
                "조건2_ma20상승기울기": cond1_ma20_rising,
                "조건3_최근상승이력(고점기준)": recent_high_found,
                "조건4_ma20근접": cond3_near_ma20,
                "조건5_거래량감소": cond4_volume_decreased,
                "조건_만족도": f"{satisfied}/5"
            }
        }

    except Exception as e:
        return {"is_pullback": False, "reason": f"오류 발생: {e}"}

@router.get("/pullback/by-name/{stock_name}")
def get_pullback_status_by_name(stock_name: str):
    """주어진 종목명에 대해 오늘 또는 가장 최근 영업일 기준으로 눌림목 상태를 확인합니다."""
    
    # 종목명으로 티커 찾기
    ticker = _ticker_map_cache.get(stock_name)
    if not ticker:
        # 캐시에 없으면 실시간으로 다시 시도 (캐시 로드 실패 대비)
        # 또는 캐시 로드 실패 시 에러 반환하도록 수정 가능
        print(f"Warning: Ticker for '{stock_name}' not found in cache. Attempting real-time lookup.")
        try:
            tickers = stock.get_market_ticker_list(market="ALL")
            found = False
            for t in tickers:
                try:
                    if stock.get_market_ticker_name(t) == stock_name:
                        ticker = t
                        found = True
                        # 찾았으면 캐시 업데이트 (선택적)
                        _ticker_map_cache[stock_name] = ticker 
                        print(f"Found ticker {ticker} for '{stock_name}' and updated cache.")
                        break
                except Exception:
                    continue # 이름 조회 실패 시 다음 티커로
            if not found:
                 raise HTTPException(status_code=404, detail=f"종목명 '{stock_name}'에 해당하는 티커를 찾을 수 없습니다.")
        except Exception as e:
             raise HTTPException(status_code=500, detail=f"티커 조회 중 오류 발생: {e}")

    # --- 이하 로직은 기존 get_pullback_status와 유사 ---
    today = datetime.today().date()
    reference_date = None

    # 기준일 찾기 (오늘 또는 가장 최근 영업일)
    if is_business_day(today):
        reference_date = today
    else:
        # 최대 5일 전까지 거슬러 올라가며 영업일 찾기
        for i in range(1, 6):
            check_date = today - timedelta(days=i)
            if is_business_day(check_date):
                reference_date = check_date
                break
    
    if not reference_date:
        raise HTTPException(status_code=404, detail="최근 5일 내 영업일을 찾을 수 없습니다.")

    reference_date_str = reference_date.strftime('%Y%m%d')
    
    # check_pullback 함수 호출 (찾은 티커 사용)
    result = check_pullback(ticker, reference_date_str)
    
    if "reason" in result and "오류 발생" in result["reason"]:
         raise HTTPException(status_code=500, detail=result["reason"])
    elif "reason" in result and "데이터 부족" in result["reason"]:
         raise HTTPException(status_code=404, detail=result["reason"])

    # 결과에 종목명과 티커 추가
    result["stock_name"] = stock_name
    result["ticker"] = ticker
    return result
