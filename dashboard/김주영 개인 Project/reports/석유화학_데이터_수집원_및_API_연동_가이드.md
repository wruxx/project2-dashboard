# [석유화학·에너지 데이터 수집 가이드]
## 유가·가스·환율·석화제품(납사/에틸렌/프로필렌/부타디엔)·운임 데이터 소스 분류 및 수집 전략

---

### Executive Summary (요약)
석유화학 및 에너지 시계열 분석을 위해 필요한 데이터는 크게 **(1) 거래소 상장 금융/원자재 데이터 (API로 즉시 수집 가능)**와 **(2) 장외(OTC) 현물 고시가 및 해운 운임 데이터 (공공 API, 무료 통계 사이트, 또는 웹 크롤링 필요)**의 두 가지 영역으로 나뉩니다.

본 문서는 각 데이터 항목별 **공식 API 여부, 무료 제공처, 파이썬 패키지(`yfinance`, `fredapi`), 웹 크롤링 난이도, 그리고 현업 실무진의 대체 데이터 수집 노하우**를 체계적으로 정리합니다.

---

## 1. 데이터 항목별 수집 경로 매트릭스 한눈에 보기

| 데이터 범주 | 세부 품목 | API 직접 수집 가능 여부 | 추천 수집 소스 | 수집 방식 |
| :--- | :--- | :---: | :--- | :--- |
| **원유 (Crude Oil)** | WTI 선물 | ✅ 가능 | Yahoo Finance / FRED | `yfinance` 티커 `CL=F` 또는 FRED API |
| | Brent 선물 | ✅ 가능 | Yahoo Finance / FRED | `yfinance` 티커 `BZ=F` 또는 FRED API |
| | Dubai 현물 | ⚠️ 제한적 (유료/대체) | 한국석유공사 페트로넷 / FRED | 페트로넷 크롤링 또는 FRED 월별 데이터 |
| **천연가스 (Gas)** | Henry Hub (미국) | ✅ 가능 | Yahoo Finance / FRED | `yfinance` 티커 `NG=F` 또는 FRED API |
| | TTF 가스 (유럽) | ✅ 가능 | Yahoo Finance / ICE | `yfinance` 티커 `TTF=F` |
| **환율 (FX)** | USD/KRW (원달러) | ✅ 가능 | Yahoo Finance / 한국은행 ECOS | `yfinance` 티커 `KRW=X` 또는 ECOS API |
| | USD/CNY (달러위안) | ✅ 가능 | Yahoo Finance / FRED | `yfinance` 티커 `CNY=X` |
| **석유화학 제품** | 납사 (Naphtha) | ❌ 공식 무료 API 없음 | 페트로넷 / 관세청 TRASS / 인베스팅 | 웹 크롤링 또는 관세청 HS코드 수출입 단가 API |
| | 에틸렌 (Ethylene) | ❌ 공식 무료 API 없음 | 관세청 TRASS / SunSirs / 인베스팅 | 관세청 품목별 단가 API 또는 화학 포털 크롤링 |
| | 프로필렌 (Propylene)| ❌ 공식 무료 API 없음 | 관세청 TRASS / SunSirs | 관세청 품목별 단가 API 또는 화학 포털 크롤링 |
| | 부타디엔 (Butadiene)| ❌ 공식 무료 API 없음 | 관세청 TRASS / SunSirs | 관세청 품목별 단가 API 또는 화학 포털 크롤링 |
| **해상 운임지수** | SCFI (상하이컨테이너) | ⚠️ 반자동 (웹 공개) | 한국해양진흥공사(KOBC) / SSE | 해진공 해운통계 웹 크롤링 |
| | BDI (발틱운임지수) | ✅ 가능 | Yahoo Finance / TradingEconomics| `yfinance` 티커 `^BDI` 또는 크롤링 |
| | 탱커 운임 (MR/LR) | ⚠️ 반자동 (웹 공개) | 한국해양진흥공사(KOBC) 주간동향 | KOBC 리포트 크롤링 또는 PDF 파싱 |

---

## 2. 세부 항목별 수집 가이드 및 파이썬 코드 예시

### [카테고리 A] API로 1줄 만에 즉시 가져올 수 있는 데이터 (무료 & 초간편)

#### 1) Yahoo Finance (`yfinance` 라이브러리)
가장 쉽고 빠르게 30년 이상의 일별/주별 시계열 데이터를 받을 수 있는 방법입니다.
* 설치: `uv pip install yfinance`

```python
import yfinance as yf
import pandas as pd

# 핵심 티커 정의
tickers = {
    'WTI_Crude': 'CL=F',        # WTI 원유 선물 ($/배럴)
    'Brent_Crude': 'BZ=F',      # 브렌트유 선물 ($/배럴)
    'Natural_Gas': 'NG=F',      # 천연가스 선물 ($/MMBtu)
    'USDKRW': 'KRW=X',          # 원달러 환율
    'USDCNY': 'CNY=X',          # 달러위안 환율
}

df_list = []
for name, ticker in tickers.items():
    data = yf.download(ticker, start='2015-01-01', end='2026-11-15', progress=False)['Close']
    data.columns = [name]
    df_list.append(data)

macro_df = pd.concat(df_list, axis=1).ffill()
print(macro_df.tail())
```

#### 2) FRED (미국 연방준비은행 경제 데이터 API)
* 미국 정부 및 글로벌 공식 통계로 신뢰도가 가장 높으며, 무료 API 키만 발급받으면 무제한 수집 가능.
* 패키지: `uv pip install fredapi`
* 주요 시리즈 ID:
  - `DCOILWTICO`: WTI 원유 일별 현물 가격
  - `DCOILBRENTEU`: Brent 원유 일별 현물 가격
  - `POILDUBUSDM`: Dubai 원유 월별 글로벌 가격
  - `DHHNGSP`: Henry Hub 천연가스 일별 현물 가격
  - `DEXKOUS`: 한국 원달러 일별 환율

---

### [카테고리 B] 석유화학 제품 가격 (납사, 에틸렌, 프로필렌, 부타디엔)

석유화학 기초유분은 일반 주식/선물 거래소 상장 품목이 아닙니다. **Platts, ICIS, Argus**와 같은 글로벌 가격평가기관이 장외(OTC) 실거래가를 매일 설문 조사하여 발표하는 **독점 유료 데이터(연간 수천만 원 상당)**입니다.

현업에서 대안으로 사용하는 **무료/실무 수집 3대 전략**은 다음과 같습니다:

#### 전략 1: 관세청 품목별(HS Code) 수출입 통계 API (강력 추천 ⭐️⭐️⭐️)
공공데이터포털(data.go.kr)의 '관세청 품목별 수출입 실적' API를 이용하면, 한국 기업들이 실제 수출입한 **중량(kg)**과 **금액($)**이 매달 공식 집계됩니다.
* **계산 공식**: $\text{단가(\$/톤)} = \frac{\text{수출입 금액(\$)}}{\text{중량(톤)}}$
* **핵심 품목 HS Code**:
  - **납사 (Naphtha)**: `2710.12.3000` (석유화학용 납사)
  - **에틸렌 (Ethylene)**: `2901.21.0000`
  - **프로필렌 (Propylene)**: `2901.22.0000`
  - **부타디엔 (Butadiene)**: `2901.24.0000`
* **장점**: 100% 공식 데이터, 결측치 없음, 무료 오픈 API.
* **단점**: 월별(Monthly) 집계이므로 일별 단기 변동은 파악하기 어려움 (중장기 예측 모델에 최적).

#### 전략 2: 한국석유공사 페트로넷 (Petronet) 및 오피넷 (Opinet)
* **납사(CFR Japan)** 현물 가격 및 정제마진 주간/월간 통계를 무료로 공개합니다.
* 회원가입 후 웹상에서 엑셀 다운로드가 가능하며, `requests` + `BeautifulSoup`으로 주간 단위 자동 크롤링이 가능합니다.

#### 전략 3: 중국 화학 전문 포털 (SunSirs - 生意社) 웹 스크래핑
* 중국 비즈니스 상품 포털 [SunSirs (영문판)](http://www.sunsirs.com/uk/)은 에틸렌, 프로필렌, 부타디엔의 아시아/중국 일별 현물 가격(RMB 또는 USD 환산치)을 차트와 표로 무료 공개합니다.
* 파이썬 스크립트로 일별 고시가를 손쉽게 크롤링할 수 있어 실무 분석가들이 자주 활용하는 소스입니다.

---

### [카테고리 C] 현물 운임지수 (SCFI, 탱커 운임)

#### 1) SCFI (상하이 컨테이너 운임지수)
* **상하이해운거래소(SSE)**에서 매주 금요일 발표.
* **무료 수집 경로**:
  - **한국해양진흥공사(KOBC) 해운정보서비스** (kobc.or.kr): 주간 SCFI 지수를 깔끔한 웹 테이블로 제공.
  - **한국무역협회(KITA)** 및 **인베스팅닷컴**: 웹 크롤링 가능.

#### 2) 탱커 운임 (MR / LR 케미컬 탱커)
* 납사는 유조선으로 운송되므로 탱커 운임(Worldscale)이 중요합니다.
* KOBC에서 매주 발행하는 **'탱커 주간 리포트'** 웹 페이지 또는 관세청의 해상 수입 운임 통계를 파싱하여 수집합니다.

---

## 3. 추천 개발 단계 (Step-by-step Roadmap)

```
[ Step 1: 무료 API 즉시 수집 ]
  - yfinance & FRED API 활용
  - WTI, Brent, 천연가스, USD/KRW, USD/CNY, BDI 수집 (코드 10분 완성)
          ▼
[ Step 2: 납사 및 석화제품 시계열 확보 ]
  - 한국석유공사 페트로넷(납사) + SunSirs 또는 관세청 HS Code(에틸렌/프로필렌/부타디엔) 크롤링/다운로드
          ▼
[ Step 3: SCFI 운임 지수 결합 ]
  - 해진공(KOBC) 주간 지수 병합 (주간 기준 리샘플링/Forward Fill)
          ▼
[ Step 4: 통합 데이터프레임 생성 및 모델링 ]
  - 날짜(Date) 기준으로 결합 -> 시차(Lag) 변수 생성 -> 가격 예측 모델 학습
```

---
*가이드 작성 일자: 2026-11-15*  
*작성: 수석 에너지·석유화학 데이터 분석가*
