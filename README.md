# pullback-stock-analysis

## Firestore 설정 가이드

### 1. 환경 변수 설정
프로젝트를 사용하기 전에 FIRESTORE_PROJECT_ID 환경 변수를 설정해야 합니다.

**주의:** FIRESTORE_PROJECT_ID가 설정되지 않으면 애플리케이션이 시작되지 않습니다.
에러 메시지 예시:
```
ValueError: FIRESTORE_PROJECT_ID 환경 변수가 설정되지 않았습니다.
프로젝트를 사용하기 전에 FIRESTORE_PROJECT_ID 환경 변수를 설정해야 합니다.
Windows: $env:FIRESTORE_PROJECT_ID="your-project-id"
macOS/Linux: export FIRESTORE_PROJECT_ID="your-project-id"
```

#### Windows (PowerShell):
```powershell
$env:FIRESTORE_PROJECT_ID="your-project-id"
```

#### macOS/Linux (Terminal):
```bash
export FIRESTORE_PROJECT_ID="your-project-id"
```

### 2. 로컬 개발 환경 (에뮬레이터 사용)
```bash
# Firestore 에뮬레이터 실행
$env:FIRESTORE_EMULATOR_HOST="localhost:8080"
$env:FIRESTORE_PROJECT_ID="your-project-id"
```

### 3. 배포 환경 (실제 Firestore 사용)
```bash
# Google Cloud 프로젝트 ID 설정
$env:FIRESTORE_PROJECT_ID="your-production-project-id"
```

주의: 프로덕션 환경에서는 반드시 실제 Google Cloud 프로젝트 ID를 설정해야 합니다.
