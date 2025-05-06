from database import db

def get_firestore_data(date: str) -> list | None:
    """지정된 날짜의 Top 100 데이터를 Firestore에서 조회합니다."""
    doc_ref = db.collection('daily_top100').document(date)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('data', [])
    else:
        print(f"Warning: Data for {date} not found in Firestore.")
        return None