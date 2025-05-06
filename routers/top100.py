from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from statistics import mean

from pykrx import stock
import pandas as pd
import numpy as np

from database import db
from routers.holidays import is_business_day
from services.firestore_service import get_firestore_data
from services.stock_service import get_previous_business_days

router = APIRouter()

@router.get("/top100/{date}")
def get_top100(date: str):
    """지정된 날짜의 Top 100 데이터를 Firestore에서 조회합니다."""
    doc_ref = db.collection('daily_top100').document(date)
    doc = doc_ref.get()
    if doc.exists: 
        return doc.to_dict().get('data', [])
    else:
        return {"message": "해당 날짜의 데이터가 없습니다."}, 404

def _create_snapshot_data(date: str):
    """지정된 날짜의 Top 100 데이터를 생성하여 Firestore에 저장하는 내부 로직"""
    try:
        df = stock.get_market_ohlcv_by_ticker(date)
        top = (
            df.sort_values(by='거래대금', ascending=False)
            .head(100)
            .reset_index()[['티커', '거래량', '거래대금']]
        )
        top['종목명'] = top['티커'].map(lambda t: stock.get_market_ticker_name(t))
        top = top[['종목명', '거래량', '거래대금']]
        records = top.to_dict('records')

        doc_ref = db.collection('daily_top100').document(date)
        doc_ref.set({'data': records})

        return {"message": f"{date}의 Top 100 데이터 스냅샷 생성 및 저장 완료"}
    except Exception as e:
        print(f"Error creating snapshot for {date}: {e}")
        return {"message": f"{date} 데이터 처리 중 오류 발생: {e}"}, 500

@router.post("/snapshot") 
def create_snapshot_today():
    """오늘 날짜의 Top 100 데이터를 생성하여 Firestore에 저장합니다."""
    today_date = datetime.today().strftime('%Y%m%d')
    return _create_snapshot_data(today_date)

@router.post("/snapshot/{date}")
def create_snapshot_with_date(date: str):
    """지정된 날짜의 Top 100 데이터를 생성하여 Firestore에 저장합니다."""
    return _create_snapshot_data(date)

@router.post("/cleanup")
def cleanup_old_data():
    """Firestore에서 최근 5영업일 이전의 오래된 Top 100 데이터를 삭제합니다."""
    try:
        today = datetime.today().date()
        business_days_to_keep = []
        current_date = today

        if is_business_day(today):
             business_days_to_keep.append(today.strftime('%Y%m%d'))

        while len(business_days_to_keep) < 5:
            current_date -= timedelta(days=1)
            if is_business_day(current_date):
                business_days_to_keep.append(current_date.strftime('%Y%m%d'))
        
        keep_dates_set = set(business_days_to_keep)
        print(f"Keeping data for dates: {sorted(list(keep_dates_set), reverse=True)}")

        collection_ref = db.collection('daily_top100')
        docs = collection_ref.stream()
        
        docs_to_delete = []
        for doc in docs:
            if doc.id not in keep_dates_set:
                docs_to_delete.append(doc.id)
        
        deleted_count = 0
        if not docs_to_delete:
            return {"message": "삭제할 오래된 데이터가 없습니다. (최근 5영업일 데이터만 보관 중)"}

        for doc_id in docs_to_delete:
            collection_ref.document(doc_id).delete()
            deleted_count += 1
            print(f"Deleted document: {doc_id}")

        return {"message": f"오래된 데이터 {deleted_count}개 삭제 완료. 최근 5영업일 데이터만 보관됩니다."}
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return {"message": f"데이터 정리 중 오류 발생: {e}"}, 500

@router.get("/hot-stocks")
def get_hot_stocks():
    """오늘 또는 가장 최근 영업일의 관심도가 높은 종목(신규 Top100 진입 또는 거래대금 급증)을 조회합니다."""
    try:
        today_str = datetime.today().strftime('%Y%m%d')
        reference_date_str = None
        
        today_data = get_firestore_data(today_str)
        if today_data:
            reference_date_str = today_str
        else:
            print(f"Warning: Data for today ({today_str}) not found. Searching for the most recent business day data.")
            potential_dates = get_previous_business_days(10, today_str) 
            for date in potential_dates:
                if get_firestore_data(date):
                    reference_date_str = date
                    print(f"Using data from the most recent business day: {reference_date_str}")
                    break
        
        if not reference_date_str:
            raise HTTPException(status_code=404, detail="최근 영업일의 Top 100 데이터가 없습니다. 먼저 스냅샷을 생성해주세요.")

        previous_5_days_from_ref = get_previous_business_days(5, reference_date_str)
        all_relevant_dates = [reference_date_str] + previous_5_days_from_ref
        
        daily_data = {}
        for date in all_relevant_dates:
            data = get_firestore_data(date)            
            if data is not None:
                daily_data[date] = {item['종목명']: item for item in data}
            else:
                daily_data[date] = {}

        reference_stocks = daily_data.get(reference_date_str, {})
        if not reference_stocks:
             raise HTTPException(status_code=404, detail=f"{reference_date_str}의 Top 100 데이터가 없습니다.")

        previous_business_day_str = previous_5_days_from_ref[0] 
        previous_day_top100_names = set(daily_data.get(previous_business_day_str, {}).keys())
        
        hot_stocks_result = []

        for stock_name, ref_day_info in reference_stocks.items():
            is_new_entry = stock_name not in previous_day_top100_names
            
            past_values = []
            for date in previous_5_days_from_ref:
                stock_data_on_date = daily_data.get(date, {}).get(stock_name)
                if stock_data_on_date:
                    past_values.append(stock_data_on_date.get('거래대금', 0))
            
            avg_5_day_value = mean(past_values) if past_values else 0
            ref_day_value = ref_day_info.get('거래대금', 0)
            
            is_value_surge = avg_5_day_value > 0 and ref_day_value >= 2 * avg_5_day_value

            if is_new_entry or is_value_surge:
                hot_stocks_result.append({
                    "종목명": stock_name,
                    "거래대금": ref_day_value,
                    "거래량": ref_day_info.get('거래량', 0),
                    "이전영업일Top100": not is_new_entry,
                    "5일평균거래대금": avg_5_day_value,
                    "거래대금배수(5일평균기준)": 0 if avg_5_day_value == 0 else ref_day_value/avg_5_day_value
                })

        if not hot_stocks_result:
            return {"message": f"{reference_date_str} 기준 조건에 맞는 관심 종목이 없습니다."}
            
        return hot_stocks_result

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Error fetching hot stocks: {e}")
        raise HTTPException(status_code=500, detail=f"관심 종목 조회 중 오류 발생: {e}")