from datetime import datetime, timedelta
from routers.holidays import is_business_day


def get_previous_business_days(n: int, end_date_str: str) -> list[str]:
    """주어진 종료 날짜 이전의 n개 영업일(주말 및 공휴일 제외) 리스트를 반환합니다."""
    business_days = []
    current_date = datetime.strptime(end_date_str, '%Y%m%d').date() # date 객체 사용

    while len(business_days) < n:
        current_date -= timedelta(days=1)
        if is_business_day(current_date):
            business_days.append(current_date.strftime('%Y%m%d'))
    return business_days