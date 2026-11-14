# Project 2 Dashboard

제조 품질 검사(입고검사 EDA), 협력사 재계약 종합 검토, 생산 공정조건 상관분석 인터랙티브 대시보드 웹 서비스입니다.
Cloudflare Pages를 통해 자동 배포되도록 구성되어 있습니다.

## 📁 배포 폴더 구조 (`dashboard/`)

```text
dashboard/
├── index.html                                        ← 대시보드 허브 메인 페이지
├── inspection-eda/
│   └── inspection_dashboard.html                     ← 02회차 입고검사 품질 대시보드
├── supplier-review/
│   ├── supplier_review_extended.html                 ← 03회차 협력사 재계약 품질검토 대시보드 (Extended)
│   └── supplier_review.html                          ← 03회차 협력사 재계약 대시보드 (기본)
└── process-correlation/
    └── correlation_dashboard.html                    ← 04회차 협력사 생산조건 및 공정 상관분석 대시보드
```

## 🚀 Cloudflare Pages 배포 설정
- **Production branch**: `main`
- **Build setting**: None (정적 사이트)
- **Build output directory**: `dashboard`
