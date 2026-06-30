# Nintendo Switch KR eShop Database Scraper & Local Viewer

이 프로젝트는 한국 닌텐도 스토어(`store.nintendo.co.kr`)의 약 9,000개 이상의 상품 데이터를 주기적으로 수집하여 SQLite 데이터베이스 파일(`database.sqlite`)로 축적하고, 로컬 터미널 환경(Termux, macOS, Linux, Windows 등)에서 이를 검색/조회할 수 있는 무료 자작 로컬 어플리케이션입니다.

GitHub Actions(무료 서버리스 크론)를 이용해 원격에서 매일 새벽 자동으로 데이터를 갱신하고 레포지토리에 저장하므로, 로컬 앱에서는 `git pull`만 하면 언제나 최신 할인 및 신작 정보를 매우 빠르게(오프라인 상태에서도) 조회할 수 있습니다.

---

## 📂 프로젝트 구조

*   `sync_eshop.py`: 닌텐도 코리아 스토어 웹페이지를 크롤링하여 `database.sqlite` 데이터베이스를 갱신하는 스크립트 (종속성 없음)
*   `app.py`: SQLite DB와 연동하여 편리하게 검색, 세일율 높은 순 조회, 신작 조회, 통계를 제공하는 터미널 CLI 로컬 어플리케이션
*   `.github/workflows/update.yml`: 매일 새벽 3시(한국 시간) 자동으로 스크롤링 스크립트를 작동시켜 DB를 업데이트하고 레포지토리에 커밋해 주는 GitHub Action 워크플로우

---

## 🚀 시작 가이드 (초기 설정 및 배포)

### 1. GitHub 저장소 생성 및 코드 업로드
1.  본인의 GitHub 계정에 빈 저장소(Repository)를 생성합니다 (예: `nintendo-eshop-kr`).
2.  로컬 터미널(Termux 등)에서 이 디렉토리로 이동한 뒤 Git 저장소를 초기화하고 코드를 푸시합니다.
    ```bash
    cd /data/data/com.termux/files/home/nintendo-eshop-kr
    git init
    git add .
    git commit -m "Initial commit"
    git branch -M main
    git remote add origin https://github.com/본인계정명/nintendo-eshop-kr.git
    git push -u origin main
    ```

### 2. GitHub Actions 권한 설정 (중요)
GitHub Actions가 DB를 갱신하고 레포지토리에 직접 푸시하려면 쓰기 권한이 허용되어야 합니다.
1.  GitHub 저장소 웹 페이지에서 **Settings** > **Actions** > **General**로 이동합니다.
2.  하단의 **Workflow permissions** 섹션에서 **Read and write permissions**를 선택하고 **Save**를 클릭합니다.

이후부터는 매일 한국 시간 새벽 3시(UTC 18:00)에 자동으로 닌텐도 스토어를 스캔하여 레포지토리의 `database.sqlite` 파일을 최신화합니다.

---

## 📱 로컬 실행 및 활용 방법

### 1. 로컬 뷰어 앱 실행
저장소를 클론한 뒤 로컬에서 아래 명령어로 뷰어(CLI)를 바로 실행합니다.
```bash
python3 app.py
```
*   **1번 메뉴 (검색):** 제목의 일부를 입력하면 일치하는 모든 게임과 가격, 할인율을 보여줍니다.
*   **2번 메뉴 (할인 중인 상품):** 현재 할인 중인 모든 게임을 **할인율이 가장 높은 순**으로 보여줍니다.
*   **3번 메뉴 (최신 출시작):** 최근에 발매된 신작 20개를 보여줍니다.
*   **4번 메뉴 (통계):** 수집된 게임 수, 할인 게임 수, 최근 갱신 시간을 한눈에 확인합니다.
*   **5번 메뉴 (로컬 동기화):** GitHub Action을 기다리지 않고 직접 크롤러를 작동시켜 데이터베이스를 최신화합니다. (테스트용 `Quick Sync`는 2페이지 분량만 수집하여 약 5초 내로 완료됩니다.)

### 2. 매일 최신 정보로 업데이트하기 (Git Pull)
GitHub Actions가 갱신해 둔 최신 세일 및 신작 데이터베이스를 가져오려면, 로컬 실행 전에 레포지토리 폴더에서 아래 명령어만 입력하면 됩니다. (단 1초 소요)
```bash
git pull
```
이 방식을 이용하면 닌텐도 서버에 실시간으로 접속하지 않으므로 데이터 패킷 소모도 없고, 로컬 DB 쿼리를 이용해 매우 즉각적이고 유연하게 원하는 정보를 가공/조회할 수 있습니다.
