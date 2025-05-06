import os
from google.cloud import firestore

# 환경 변수 확인
if not os.getenv('FIRESTORE_PROJECT_ID'):
    raise ValueError(
        "FIRESTORE_PROJECT_ID 환경 변수가 설정되지 않았습니다.\n"
        "프로젝트를 사용하기 전에 FIRESTORE_PROJECT_ID 환경 변수를 설정해야 합니다.\n"
        "Windows: $env:FIRESTORE_PROJECT_ID=\"your-project-id\"\n"
        "macOS/Linux: export FIRESTORE_PROJECT_ID=\"your-project-id\"\n"
        "자세한 설정 방법은 README.md 파일을 참조하세요."
    )

# Firestore 클라이언트 초기화
db = firestore.Client(project=os.getenv('FIRESTORE_PROJECT_ID'))