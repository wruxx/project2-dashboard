"""
일일 자동 업데이트 마스터 파이프라인 (Daily Auto-Update Master Pipeline)
=======================================================================
매일 오전 8:00 (Asia/Seoul) 자동 실행되어 다음 4단계를 수행합니다:
1. [Step 1] 최신 시계열 데이터 수집 및 DB 누적 (yfinance WTI/Brent/NG/FX/OVX/VIX + 두바이유/석화단가/운임지수/Google News RSS NLP 감성점수)
2. [Step 2] LG화학 AOT + NLP 하이브리드 AI 모델 재추론 (P10~P90 예측 밴드, TreeSHAP, 스팟 납사 구매 시그널 갱신)
3. [Step 3] 대시보드 HTML 및 차트 이미지 최신화 (`reports/interactive_petrochem_dashboard.html` 및 `김주영 개인 Project/`)
4. [Step 4] GitHub 저장소(`wruxx/project2-dashboard`) 자동 Commit & Push (-> Cloudflare Pages & GitHub Pages 무중단 자동 배포)
"""

import argparse
import base64
import json
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYTHON = sys.executable

PIPELINE_STEPS = [
    ("1단계: 글로벌 유가·가스·환율(yfinance) 최신 데이터 수집", ROOT / "scripts" / "fetch_stage1_macro_energy.py"),
    ("2단계: 두바이유·관세청 석화단가·해상운임(SCFI/KCCI/BDI) 크롤링 및 병합", ROOT / "scripts" / "build_full_petrochem_database.py"),
    ("3단계: LG화학 AOT 하이브리드 앙상블 모델링", ROOT / "scripts" / "stage6_lgchem_aot_upgrade.py"),
    ("4단계: 석유화학 뉴스 RSS 크롤링 & NLP 감성분석", ROOT / "scripts" / "stage7_nlp_sentiment_and_direction_boost.py"),
    ("5단계: 4-Tab 핵심 의사결정 대시보드(유가·납사·LG화학 NCC 가동률) 렌더링", ROOT / "scripts" / "generate_tabbed_dashboard.py"),
]


def run_step(title: str, script_path: pathlib.Path) -> bool:
    print(f"\n[실행 중] {title} ({script_path.name})")
    if not script_path.exists():
        print(f"  [경고] 스크립트를 찾을 수 없습니다: {script_path}")
        return False
    res = subprocess.run([PYTHON, str(script_path)], cwd=str(ROOT))
    if res.returncode != 0:
        print(f"  [오류] {script_path.name} 실행 실패 (코드: {res.returncode})")
        return False
    print(f"  [완료] {title}")
    return True


def stamp_update_badge(html_text: str, now_str: str) -> str:
    """대시보드 상단에 최종 자동 업데이트 시각(KST) 배지를 삽입하거나 갱신합니다."""
    badge_pattern = r"<!-- AUTO_UPDATE_BADGE_START -->.*?<!-- AUTO_UPDATE_BADGE_END -->"
    badge_html = (
        f'<!-- AUTO_UPDATE_BADGE_START -->'
        f'<div style="display:inline-flex;align-items:center;gap:8px;background:rgba(16,185,129,0.15);'
        f'border:1px solid rgba(16,185,129,0.45);color:#34d399;padding:5px 12px;border-radius:999px;'
        f'font-size:12px;font-weight:700;margin-top:8px;">'
        f'<span>🔄 일일 자동 업데이트 가동 중 (매일 08:00 KST)</span>'
        f'<span style="color:#a7f3d0;">| 최종 동기화: {now_str}</span>'
        f'</div>'
        f'<!-- AUTO_UPDATE_BADGE_END -->'
    )
    if re.search(badge_pattern, html_text, flags=re.DOTALL):
        return re.sub(badge_pattern, badge_html, html_text, flags=re.DOTALL)
    # 첫 <header ...> 내부 혹은 <h1> 아래에 삽입
    if "</h1>" in html_text:
        return html_text.replace("</h1>", f"</h1>\n      {badge_html}", 1)
    return html_text


def sync_project_folder() -> str:
    """최신 데이터, 차트, 대시보드 HTML을 '김주영 개인 Project' 폴더 및 배포용 ZIP에 동기화합니다."""
    proj_dir = ROOT / "김주영 개인 Project"
    proj_dir.mkdir(exist_ok=True)
    for sub in ["figures", "reports", "data", "scripts"]:
        (proj_dir / sub).mkdir(exist_ok=True)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M KST")

    src_html = ROOT / "reports" / "interactive_petrochem_dashboard.html"
    if src_html.exists():
        raw_html = src_html.read_text(encoding="utf-8")
        stamped_html = stamp_update_badge(raw_html, now_str)
        src_html.write_text(stamped_html, encoding="utf-8")

        html_fixed = stamped_html.replace("../figures/", "./figures/")
        (proj_dir / "interactive_petrochem_dashboard.html").write_text(html_fixed, encoding="utf-8")
        (proj_dir / "index.html").write_text(html_fixed, encoding="utf-8")
        print(f"  [동기화 완료] 대시보드 HTML 갱신 ({now_str})")

    for f in (ROOT / "figures").glob("*.png"):
        shutil.copy2(f, proj_dir / "figures" / f.name)
    for f in (ROOT / "data").glob("*.csv"):
        shutil.copy2(f, proj_dir / "data" / f.name)
    for f in (ROOT / "reports").glob("*.md"):
        shutil.copy2(f, proj_dir / "reports" / f.name)
    for f in (ROOT / "scripts").glob("*.py"):
        shutil.copy2(f, proj_dir / "scripts" / f.name)

    zip_path = ROOT / "김주영_개인_Project_Cloudflare_배포패키지.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in proj_dir.rglob("*"):
            if p.is_file():
                zf.write(p, str(p.relative_to(proj_dir)))
    print(f"  [동기화 완료] Cloudflare 배포용 ZIP 갱신 ({zip_path.name})")
    return now_str


def push_to_github(now_str: str):
    """gh CLI를 통해 최신화된 대시보드와 데이터를 wruxx/project2-dashboard에 자동 Push합니다."""
    proj_dir = ROOT / "김주영 개인 Project"
    targets = [
        (proj_dir / "index.html", "김주영 개인 Project/index.html"),
        (proj_dir / "interactive_petrochem_dashboard.html", "김주영 개인 Project/interactive_petrochem_dashboard.html"),
        (proj_dir / "interactive_petrochem_dashboard.html", "dashboard/김주영 개인 Project/interactive_petrochem_dashboard.html"),
        (proj_dir / "data" / "petrochem_integrated_weekly_db.csv", "김주영 개인 Project/data/petrochem_integrated_weekly_db.csv"),
        (proj_dir / "data" / "petrochem_news_sentiment_crawled.csv", "김주영 개인 Project/data/petrochem_news_sentiment_crawled.csv"),
        (proj_dir / "figures" / "stage7_nlp_sentiment_and_accuracy_jump.png", "김주영 개인 Project/figures/stage7_nlp_sentiment_and_accuracy_jump.png"),
    ]
    print("\n[GitHub 동기화] wruxx/project2-dashboard 원격 저장소 업데이트 중...")
    for local_path, remote_path in targets:
        if not local_path.exists():
            continue
        b64 = base64.b64encode(local_path.read_bytes()).decode("ascii")
        r = subprocess.run(
            ["gh", "api", f"repos/wruxx/project2-dashboard/contents/{remote_path}"],
            capture_output=True,
            text=True,
        )
        payload = {
            "message": f"chore(auto-update): daily petrochem DB & dashboard update ({now_str})",
            "content": b64,
            "branch": "main",
        }
        if r.returncode == 0:
            try:
                sha = json.loads(r.stdout).get("sha")
                if sha:
                    payload["sha"] = sha
            except Exception:
                pass
        p = subprocess.run(
            ["gh", "api", "--method", "PUT", f"repos/wruxx/project2-dashboard/contents/{remote_path}", "--input", "-"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        status = "성공" if p.returncode == 0 else f"실패({p.returncode})"
        print(f"  - {remote_path}: {status}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push-github", action="store_true", help="업데이트 결과를 GitHub 저장소에 즉시 Push")
    parser.add_argument("--sync-only", action="store_true", help="크롤링 생략 후 대시보드 패키징 및 GitHub 동기화만 수행")
    args = parser.parse_args()

    print("=" * 72)
    print(f"🚀 석유화학 AI 대시보드 일일 자동 업데이트 시작 ({datetime.now():%Y-%m-%d %H:%M:%S})")
    print("=" * 72)

    if not args.sync_only:
        for title, script in PIPELINE_STEPS:
            run_step(title, script)

    now_str = sync_project_folder()

    if args.push_github:
        push_to_github(now_str)

    print("\n✅ 전 과정 업데이트 및 패키징이 완료되었습니다!")


if __name__ == "__main__":
    main()
