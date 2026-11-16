import os
import shutil
import subprocess

BASE_DIR = r"c:\Users\hongy\Desktop\공부\AI\portfolio"
PROJ_FOLDER_NAME = "김주영 개인 Project"
LOCAL_PROJ_DIR = os.path.join(BASE_DIR, PROJ_FOLDER_NAME)

# 1. 로컬 '김주영 개인 Project' 폴더 생성 및 대시보드/차트/데이터/보고서/스크립트 완비
if os.path.exists(LOCAL_PROJ_DIR):
    shutil.rmtree(LOCAL_PROJ_DIR)

os.makedirs(os.path.join(LOCAL_PROJ_DIR, "figures"), exist_ok=True)
os.makedirs(os.path.join(LOCAL_PROJ_DIR, "reports"), exist_ok=True)
os.makedirs(os.path.join(LOCAL_PROJ_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(LOCAL_PROJ_DIR, "scripts"), exist_ok=True)

# 대시보드 HTML 복사 (interactive_petrochem_dashboard.html 및 index.html 두 이름으로 모두 배치)
dash_src = os.path.join(BASE_DIR, "reports", "interactive_petrochem_dashboard.html")
shutil.copy2(dash_src, os.path.join(LOCAL_PROJ_DIR, "interactive_petrochem_dashboard.html"))
shutil.copy2(dash_src, os.path.join(LOCAL_PROJ_DIR, "index.html"))

# figures/ 복사
fig_src_dir = os.path.join(BASE_DIR, "reports", "figures")
if os.path.exists(fig_src_dir):
    for f in os.listdir(fig_src_dir):
        if f.endswith(".png"):
            shutil.copy2(os.path.join(fig_src_dir, f), os.path.join(LOCAL_PROJ_DIR, "figures", f))

# reports/ 마크다운 보고서 복사
rep_src_dir = os.path.join(BASE_DIR, "reports")
for f in os.listdir(rep_src_dir):
    if f.endswith(".md") or f.endswith(".html"):
        shutil.copy2(os.path.join(rep_src_dir, f), os.path.join(LOCAL_PROJ_DIR, "reports", f))

# data/ 핵심 CSV 복사
data_src_dir = os.path.join(BASE_DIR, "data")
for f in os.listdir(data_src_dir):
    if f.endswith(".csv"):
        shutil.copy2(os.path.join(data_src_dir, f), os.path.join(LOCAL_PROJ_DIR, "data", f))

# scripts/ 파이썬 스크립트 복사
scr_src_dir = os.path.join(BASE_DIR, "scripts")
for f in os.listdir(scr_src_dir):
    if f.endswith(".py"):
        shutil.copy2(os.path.join(scr_src_dir, f), os.path.join(LOCAL_PROJ_DIR, "scripts", f))

# 프로젝트 전용 README.md 작성
readme_content = """# 김주영 개인 Project — 석유화학 원유·납사·에틸렌 AI 가격 예측 및 NCC 생산량(가동률) 최적화 대시보드

> **LG화학 AOT(선행최적화기술) 스타일 2-Stage 동적 하이브리드 앙상블 + 뉴스 NLP 감성 결합 실전 AI 시스템**

## 🚀 주요 성과 요약 (80% 학습 451주 / 20% 검증 113주 홀드아웃 테스트)
- **납사(Naphtha) 1주 등락 방향 적중 확률**: `78.8%` (기존 58.4% 대비 `+20.4%p` 향상)
- **납사(Naphtha) 4주 중기 추세 적중 확률**: `90.3%`
- **납사 가격 수준 일치율 (`100% - MAPE`)**: `97.20%` (`MAPE 2.80%`, $R^2 = 0.9265$)
- **에틸렌(Ethylene) 가격 수준 일치율 (`100% - MAPE`)**: `97.79%` (`MAPE 2.21%`, $R^2 = 0.9260$)
- **스팟 납사 AI 매수 타이밍(`Buy Now vs Wait`) 원가 절감**: 톤당 `-3.16 $/MT` 절감 (연간 200만톤 조달 기준 **연간 `+87.1억 원` 이익 창출**)

## 📂 폴더 구조
- `index.html` / `interactive_petrochem_dashboard.html`: 실시간 6대 시나리오 슬라이더(유가·환율·운임·가스·뉴스 NLP), `P10~P90` 분위수 팬 차트, `XAI TreeSHAP` 폭포수 분해 및 차트 갤러리가 탑재된 셀프 컨테인드 웹 대시보드
- `figures/`: 피어슨 상관계수 히트맵, Seaborn 기초·심화 4대 차트, 80:20 검증 및 NLP 고도화 고해상도 PNG 차트 (8종)
- `reports/`: Stage 1 ~ Stage 7 단계별 상세 데이터 분석 및 모델링 마크다운 보고서 (7종)
- `data/`: 원유·천연가스·환율·석유화학(납사/C2/C3/C4)·운임(SCFI/KCCI/BDI/KDCI)·뉴스 NLP 통합 데이터베이스 (CSV)
- `scripts/`: 데이터 수집, 피어슨 상관분석, Seaborn 시각화, 2-Stage 하이브리드 모델링 및 NLP 감성분석 파이썬 코드
"""

with open(os.path.join(LOCAL_PROJ_DIR, "README.md"), "w", encoding="utf-8") as f:
    f.write(readme_content)

print(f"[로컬 프로젝트 패키징 완료] {LOCAL_PROJ_DIR}")
