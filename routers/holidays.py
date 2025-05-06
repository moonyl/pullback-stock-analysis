from fastapi import APIRouter, HTTPException, Body
from datetime import datetime, date as DateObject
import holidays
import os

from models import HolidayItem # models.py에서 HolidayItem 임포트
from database import db # database.py에서 db 임포트

router = APIRouter()

# 공휴일 캐시 (연도별로 관리)
_kr_holidays_cache = {}
_custom_holidays_cache = {} # 사용자 지정 공휴일 캐시 추가

def get_custom_holidays(year: int) -> set[DateObject]:
    """지정된 연도의 사용자 지정 공휴일 정보를 Firestore에서 가져오거나 캐시에서 로드합니다."""
    if year not in _custom_holidays_cache:
        custom_holidays_set = set()
        try:
            collection_ref = db.collection('custom_holidays')
            query = collection_ref.where('year', '==', year)
            docs = query.stream()
            for doc in docs:
                holiday_data = doc.to_dict()
                holiday_date_str = holiday_data.get('date')
                if holiday_date_str:
                    try:
                        custom_holidays_set.add(datetime.strptime(holiday_date_str, '%Y-%m-%d').date())
                    except ValueError:
                        print(f"Warning: Invalid date format '{holiday_date_str}' in custom_holidays collection for year {year}.")
            _custom_holidays_cache[year] = custom_holidays_set
            print(f"Loaded {len(custom_holidays_set)} custom holidays for {year} from Firestore.")
        except Exception as e:
            print(f"Error fetching custom holidays for {year} from Firestore: {e}")
            _custom_holidays_cache[year] = set()
    return _custom_holidays_cache[year]

def get_kr_holidays(year: int) -> holidays.HolidayBase:
    """지정된 연도의 한국 공휴일 정보를 캐시에서 가져오거나 로드합니다."""
    if year not in _kr_holidays_cache:
        _kr_holidays_cache[year] = holidays.KR(years=year)
    return _kr_holidays_cache[year]

def is_business_day(target_date: DateObject) -> bool:
    """주어진 날짜가 영업일인지 (주말, 표준 공휴일, 사용자 지정 공휴일 제외) 확인합니다."""
    if target_date.weekday() >= 5: # 주말 체크
        return False
    
    kr_holidays = get_kr_holidays(target_date.year)
    if target_date in kr_holidays:
        return False
        
    custom_holidays = get_custom_holidays(target_date.year)
    if target_date in custom_holidays:
        return False
        
    return True

@router.post("/holidays", tags=["holidays"])
def add_custom_holiday(holiday: HolidayItem = Body(...)):
    """사용자 지정 공휴일을 Firestore에 등록합니다."""
    try:
        holiday_date = datetime.strptime(holiday.date, '%Y-%m-%d').date()
        year = holiday_date.year

        holiday_data = {
            'date': holiday.date,
            'description': holiday.description,
            'year': year
        }

        doc_ref = db.collection('custom_holidays').document(holiday.date)
        doc_ref.set(holiday_data)

        if year in _custom_holidays_cache:
            del _custom_holidays_cache[year]
            print(f"Custom holiday cache for year {year} invalidated.")

        return {"message": f"사용자 지정 공휴일 '{holiday.description}' ({holiday.date}) 등록 완료"}

    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 날짜 형식입니다. 'YYYY-MM-DD' 형식을 사용해주세요.")
    except Exception as e:
        print(f"Error adding custom holiday: {e}")
        raise HTTPException(status_code=500, detail=f"사용자 지정 공휴일 등록 중 오류 발생: {e}")