from datetime import datetime, timedelta
from statistics import mean
from pykrx import stock
import pandas as pd
import numpy as np
from database import db
from routers.holidays import is_business_day

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

def get_previous_business_days(n: int, end_date_str: str) -> list[str]:
    """주어진 종료 날짜 이전의 n개 영업일(주말 및 공휴일 제외) 리스트를 반환합니다."""
    business_days = []
    current_date = datetime.strptime(end_date_str, '%Y%m%d').date()

    while len(business_days) < n:
        current_date -= timedelta(days=1)
        if is_business_day(current_date):
            business_days.append(current_date.strftime('%Y%m%d'))
    return business_days

def get_firestore_data(date: str) -> list | None:
    """지정된 날짜의 Top 100 데이터를 Firestore에서 조회합니다."""
    doc_ref = db.collection('daily_top100').document(date)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('data', [])
    else:
        print(f"Warning: Data for {date} not found in Firestore.")
        return None