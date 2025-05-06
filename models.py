from pydantic import BaseModel

class HolidayItem(BaseModel):
    date: str # YYYY-MM-DD 형식
    description: str