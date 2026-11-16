import os
import shutil
import tempfile
import certifi

# Windows 한글 경로('공부')에서 curl_cffi(yfinance) SSL 인증서 로드 오류 해결:
# 영문 경로(Temp)로 cacert.pem 복사 후 환경변수 지정
temp_ca_path = os.path.join(tempfile.gettempdir(), "cacert.pem")
if not os.path.exists(temp_ca_path):
    shutil.copyfile(certifi.where(), temp_ca_path)
os.environ["CURL_CA_BUNDLE"] = temp_ca_path
os.environ["SSL_CERT_FILE"] = temp_ca_path

import yfinance as yf
import pandas as pd

def fetch_macro_energy_base_table(start_date="2016-01-01", output_dir="data"):
    os.makedirs(output_dir, exist_ok=True)
    
    # 1단계 핵심 티커 정의
    tickers = {
        "WTI_Crude_USD_bbl": "CL=F",       # WTI 원유 선물 ($/배럴)
        "Brent_Crude_USD_bbl": "BZ=F",     # 브렌트유 선물 ($/배럴)
        "HenryHub_Gas_USD_MMBtu": "NG=F",  # 미국 헨리허브 천연가스 선물 ($/MMBtu)
        "USD_KRW": "KRW=X",                # 원/달러 환율 (KRW per USD)
        "USD_CNY": "CNY=X",                # 위안/달러 환율 (CNY per USD)
    }
    
    print("Downloading time-series data from Yahoo Finance...")
    series_dict = {}
    for col_name, ticker in tickers.items():
        df_ticker = yf.download(ticker, start=start_date, progress=False)
        if not df_ticker.empty:
            close_col = df_ticker["Close"]
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]
            close_col.name = col_name
            close_col.index = pd.to_datetime(close_col.index).tz_localize(None).normalize()
            close_col = close_col[~close_col.index.duplicated(keep="last")]
            series_dict[col_name] = close_col
            print(f"  - {col_name} ({ticker}): {len(close_col)} rows fetched ({close_col.index.min().date()} ~ {close_col.index.max().date()})")
    
    # 전체 영업일 기준 병합 (Outer Join)
    raw_df = pd.DataFrame(series_dict)
    raw_df.index.name = "Date"
    raw_df = raw_df.sort_index()
    
    # 원본 데이터 저장 (결측치 및 마이너스 유가 이상치 포함 상태)
    raw_path = os.path.join(output_dir, "stage1_macro_energy_raw.csv")
    raw_df.to_csv(raw_path, encoding="utf-8-sig")
    
    # 전처리:
    # 1) 2020-04-20 WTI 마이너스 유가(-37.63$/bbl)와 같은 선물 만기 롤오버 왜곡치(<=0)는 직전 정상 영업일 가격으로 보정(클리핑/결측 처리 후 ffill)
    clean_df = raw_df.copy()
    neg_wti_dates = clean_df[clean_df["WTI_Crude_USD_bbl"] <= 0].index.tolist()
    if neg_wti_dates:
        print(f"\n[Anomaly Detected] Negative/Zero WTI prices on {[str(d.date()) for d in neg_wti_dates]} -> Replaced via ffill for Base Table.")
        clean_df.loc[clean_df["WTI_Crude_USD_bbl"] <= 0, "WTI_Crude_USD_bbl"] = pd.NA
    
    # 2) 국가/거래소별 휴장일 차이에 따른 결측치 Forward-Fill 후 초기 결측 Backward-Fill
    base_df = clean_df.ffill().bfill().round(2)
    
    # 석유화학 실무 핵심 파생 변수 추가
    # 1) Brent - WTI 스프레드 ($/배럴): 북미 원유 대비 글로벌(유럽/아시아) 원유 프리미엄
    base_df["Brent_WTI_Spread_USD"] = (base_df["Brent_Crude_USD_bbl"] - base_df["WTI_Crude_USD_bbl"]).round(2)
    # 2) Oil-to-Gas Ratio (WTI / Henry Hub): 배럴당 유가 대비 백만BTU당 천연가스 비율
    #    (열량 등가 기준 6:1, 이 비율이 높을수록 미국 ECC가 아시아 NCC 대비 원가 경쟁력 우위 극대화)
    base_df["Oil_to_Gas_Ratio"] = (base_df["WTI_Crude_USD_bbl"] / base_df["HenryHub_Gas_USD_MMBtu"]).round(2)
    # 3) 원화 환산 브렌트유 가격 (KRW/배럴): 국내 정유/석화사가 체감하는 실질 원유 도입 원가
    base_df["Brent_Crude_KRW_bbl"] = (base_df["Brent_Crude_USD_bbl"] * base_df["USD_KRW"]).round(0)
    
    base_path = os.path.join(output_dir, "stage1_macro_energy_base.csv")
    base_df.to_csv(base_path, encoding="utf-8-sig")
    
    # 주간(Weekly - 금요일 기준 평균) 리샘플링 테이블 생성 (향후 납사/에틸렌/SCFI 주간 데이터와 병합용)
    weekly_df = base_df.resample("W-FRI").mean().round(2)
    weekly_path = os.path.join(output_dir, "stage1_macro_energy_weekly.csv")
    weekly_df.to_csv(weekly_path, encoding="utf-8-sig")
    
    print("\n=== Data Quality & Summary ===")
    print(f"Raw Shape: {raw_df.shape}")
    print(f"Base Shape (Daily): {base_df.shape}")
    print(f"Weekly Shape (W-FRI): {weekly_df.shape}")
    print("\nMissing values in Raw Data:")
    print(raw_df.isna().sum())
    print("\nMin/Max/Mean/Median in Raw Data:")
    print(raw_df.agg(["min", "max", "mean", "median"]).round(2))
    print("\nMin/Max/Mean/Median in Base Data:")
    print(base_df.agg(["min", "max", "mean", "median"]).round(2))
    print("\nTop 5 rows of Base Data:")
    print(base_df.head(5).to_string())
    print("\nLast 5 rows of Base Data:")
    print(base_df.tail(5).to_string())

if __name__ == "__main__":
    fetch_macro_energy_base_table()
