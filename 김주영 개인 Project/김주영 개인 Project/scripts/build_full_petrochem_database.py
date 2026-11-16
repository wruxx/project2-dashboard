import io
import json
import os
import re
import shutil
import tempfile
import certifi
import urllib3
import pandas as pd
import numpy as np

# SSL 인증서 한글 경로('공부') 오류 방지 설정
urllib3.disable_warnings()
temp_ca_path = os.path.join(tempfile.gettempdir(), "cacert.pem")
if not os.path.exists(temp_ca_path):
    shutil.copyfile(certifi.where(), temp_ca_path)
os.environ["CURL_CA_BUNDLE"] = temp_ca_path
os.environ["SSL_CERT_FILE"] = temp_ca_path

import requests
import yfinance as yf
from curl_cffi import requests as crequests
from bs4 import BeautifulSoup


def fetch_yfinance_series(start_date="2016-01-01"):
    """1. Yahoo Finance: WTI, Brent, Henry Hub 천연가스, USD/KRW, USD/CNY, BDRY(BDI 선물 ETF)"""
    print("[1/6] Fetching Yahoo Finance series (WTI, Brent, Gas, FX, BDRY)...")
    tickers = {
        "WTI_Crude_USD_bbl": "CL=F",
        "Brent_Crude_USD_bbl": "BZ=F",
        "HenryHub_Gas_USD_MMBtu": "NG=F",
        "USD_KRW": "KRW=X",
        "USD_CNY": "CNY=X",
        "BDRY_ETF_USD": "BDRY",  # Yahoo Finance ^BDI 상장폐지 대체 BDI 선물 추종 ETF
    }
    series_dict = {}
    for col_name, ticker in tickers.items():
        df_t = yf.download(ticker, start=start_date, progress=False)
        if not df_t.empty:
            s = df_t["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            s.name = col_name
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            s = s[~s.index.duplicated(keep="last")]
            series_dict[col_name] = s
            print(f"  - {col_name} ({ticker}): {len(s)} rows ({s.index.min().date()} ~ {s.index.max().date()})")
    df = pd.DataFrame(series_dict)
    # 2020-04-20 WTI 마이너스 유가(-37.63) 이상치 클리핑(결측 처리 후 ffill)
    df.loc[df["WTI_Crude_USD_bbl"] <= 0, "WTI_Crude_USD_bbl"] = np.nan
    return df


def fetch_knoc_opinet_dubai_and_naphtha(start_year=2016, end_year=2026):
    """2. 한국석유공사(KNOC 오피넷/페트로넷 연동) 일별 Dubai 원유 및 국제 나프타(납사) 현물가 크롤링"""
    print("[2/6] Crawling KNOC (Opinet/Petronet) daily Dubai Crude & International Naphtha prices...")
    s = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # (A) 일별 국제 원유 (Dubai, Brent, WTI)
    s.get("https://www.opinet.co.kr/glopcoilSelect.do", headers=headers, verify=False)
    oil_dfs = []
    for yr in range(start_year, end_year + 1):
        end_md = "1115" if yr == end_year else "1231"
        end_m = "11" if yr == end_year else "12"
        end_d = "15" if yr == end_year else "31"
        data_oil = {
            "TERM": "D",
            "STA_Y": str(yr), "STA_M": "01", "STA_D": "01",
            "END_Y": str(yr), "END_M": end_m, "END_D": end_d,
            "STDDATE": f"{yr}0101", "ENDDATE": f"{yr}{end_md}",
            "OILSRTCD1": "001", "OILSRTCD2": "002", "OILSRTCD3": "003",
            "SEL_DIV": "div_dar",
        }
        r = s.post("https://www.opinet.co.kr/glopcoil_csv.do", data=data_oil, headers=headers, verify=False)
        r.encoding = "cp949"
        df_yr = pd.read_csv(io.StringIO(r.text))
        oil_dfs.append(df_yr)

    oil_all = pd.concat(oil_dfs, ignore_index=True)
    oil_all["Date"] = pd.to_datetime(oil_all["기간"].str.strip(), format="%y년%m월%d일", errors="coerce")
    oil_all["Dubai_Crude_USD_bbl"] = pd.to_numeric(oil_all["Dubai"], errors="coerce")
    dubai_s = oil_all.dropna(subset=["Date"]).set_index("Date")["Dubai_Crude_USD_bbl"]
    dubai_s = dubai_s[~dubai_s.index.duplicated(keep="last")].sort_index()
    print(f"  - KNOC Daily Dubai Crude: {len(dubai_s)} rows ({dubai_s.index.min().date()} ~ {dubai_s.index.max().date()})")

    # (B) 일별 국제 석유제품 - 나프타(납사, Naphtha $/배럴)
    s.get("https://www.opinet.co.kr/glopopdSelect.do", headers=headers, verify=False)
    opd_dfs = []
    for yr in range(start_year, end_year + 1):
        end_md = "1115" if yr == end_year else "1231"
        end_m = "11" if yr == end_year else "12"
        end_d = "15" if yr == end_year else "31"
        data_opd = {
            "TERM": "D",
            "STA_Y": str(yr), "STA_M": "01", "STA_D": "01",
            "END_Y": str(yr), "END_M": end_m, "END_D": end_d,
            "STDDATE": f"{yr}0101", "ENDDATE": f"{yr}{end_md}",
            "OILSRTCD1": "B001", "OILSRTCD2": "B007", "OILSRTCD3": "C001",
            "OILSRTCD4": "D009", "OILSRTCD5": "D008", "OILSRTCD6": "E001", "OILSRTCD7": "F001",
            "SEL_DIV": "div_dar",
        }
        r = s.post("https://www.opinet.co.kr/glopopd_csv.do", data=data_opd, headers=headers, verify=False)
        r.encoding = "cp949"
        df_yr = pd.read_csv(io.StringIO(r.text))
        opd_dfs.append(df_yr)

    opd_all = pd.concat(opd_dfs, ignore_index=True)
    opd_all["Date"] = pd.to_datetime(opd_all["기간"].str.strip(), format="%y년%m월%d일", errors="coerce")
    opd_all["Naphtha_Spot_USD_bbl"] = pd.to_numeric(opd_all["나프타"], errors="coerce")
    naph_s = opd_all.dropna(subset=["Date"]).set_index("Date")["Naphtha_Spot_USD_bbl"]
    naph_s = naph_s[~naph_s.index.duplicated(keep="last")].sort_index()
    # 1 MT(톤) 납사 ≈ 8.95 배럴 (아시아 CFR Japan 표준 환산 계수)
    naph_mt_s = (naph_s * 8.95).round(2)
    naph_mt_s.name = "Naphtha_Spot_USD_MT"
    print(f"  - KNOC Daily Spot Naphtha: {len(naph_s)} rows ({naph_s.index.min().date()} ~ {naph_s.index.max().date()})")

    return pd.DataFrame({"Dubai_Crude_USD_bbl": dubai_s, "Naphtha_Spot_USD_bbl": naph_s, "Naphtha_Spot_USD_MT": naph_mt_s})


def fetch_fred_dubai_monthly():
    """3. FRED (POILDUBUSDM) 월별 글로벌 두바이유 벤치마크 수집"""
    print("[3/6] Fetching FRED Dubai Crude (POILDUBUSDM)...")
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=POILDUBUSDM"
    r = requests.get(url, timeout=15)
    df = pd.read_csv(io.StringIO(r.text))
    df["Date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    df["Dubai_FRED_Monthly_USD_bbl"] = pd.to_numeric(df["POILDUBUSDM"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date")[["Dubai_FRED_Monthly_USD_bbl"]]
    df = df[df.index >= "2016-01-01"].round(2)
    print(f"  - FRED POILDUBUSDM: {len(df)} monthly rows ({df.index.min().date()} ~ {df.index.max().date()})")
    return df


def fetch_customs_petrochem_prices():
    """4. 관세청 수출입무역통계(tradedata.go.kr) HS Code 기반 납사, 에틸렌, 프로필렌, 부타디엔 수출입 단가($/톤) 크롤링"""
    print("[4/6] Crawling Korea Customs Service (tradedata.go.kr) HS Code prices for Naphtha, Ethylene, Propylene, Butadiene...")
    s = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://tradedata.go.kr/cts/index.do",
    }
    s.get("https://tradedata.go.kr/cts/index.do", headers=headers, verify=False)

    # 201601~202012, 202101~202611 2개 구간으로 나누어 전체 월별 데이터 수집
    periods = [("201601", "202012"), ("202101", "202611")]
    records = []
    for p_fr, p_to in periods:
        params = {
            "tradeKind": "ETS_MNK_1020000A",
            "priodKind": "MON",
            "priodFr": p_fr,
            "priodTo": p_to,
            "statsBase": "ACCPT",
            "ttwgTpcd": "1000",  # 중량 단위: 톤(MT)
            "selectPaging": "1",
            "showPagingLine": "1000",
            "sortColumn": "",
            "sortOrder": "",
            "hsSgnGrpCol": "HS6_SGN",
            "hsSgnWhrCol": "HS6_SGN",
            "hsSgn": "271012,290121,290122,290124",
            "subHsSgn": "N",
        }
        res = s.post("https://tradedata.go.kr/cts/hmpg/retrieveTrade.do", data=params, headers=headers, verify=False).json()
        for item in res.get("items", []):
            ym = str(item.get("priodTitle", "")).strip()
            hs = str(item.get("hsSgn", "")).strip()
            if not re.match(r"^\d{4}\.\d{2}$", ym) or not hs:
                continue
            exp_w = float(str(item.get("expTtwg", "0")).replace(",", "").strip() or 0)
            exp_amt = float(str(item.get("expUsdAmt", "0")).replace(",", "").strip() or 0) * 1000.0  # 천달러 -> 달러
            imp_w = float(str(item.get("impTtwg", "0")).replace(",", "").strip() or 0)
            imp_amt = float(str(item.get("impUsdAmt", "0")).replace(",", "").strip() or 0) * 1000.0  # 천달러 -> 달러

            # 품목별 대표 실거래 단가($/톤):
            # - 납사(271012): 한국이 세계 최대 수입국이므로 '수입 단가(imp_amt / imp_w)' 기준
            # - 에틸렌(290121), 프로필렌(290122): 한국이 순수출국이므로 '수출입 총 가중평균 단가' (및 수출단가) 기준
            # - 부타디엔(290124): 수출입이 모두 활발하므로 '수출입 총 가중평균 단가' 기준
            tot_w = exp_w + imp_w
            tot_amt = exp_amt + imp_amt
            avg_price = (tot_amt / tot_w) if tot_w > 0 else np.nan
            imp_price = (imp_amt / imp_w) if imp_w > 0 else avg_price
            exp_price = (exp_amt / exp_w) if exp_w > 0 else avg_price

            records.append({
                "YearMonth": ym.replace(".", "-"),
                "Date": pd.to_datetime(ym.replace(".", "-") + "-01"),
                "HS_Code": hs,
                "Exp_Weight_MT": exp_w,
                "Imp_Weight_MT": imp_w,
                "Exp_Price_USD_MT": round(exp_price, 2),
                "Imp_Price_USD_MT": round(imp_price, 2),
                "Weighted_Price_USD_MT": round(avg_price, 2),
            })

    df_raw = pd.DataFrame(records)
    # 피벗하여 월별 컬럼 생성
    naph = df_raw[df_raw["HS_Code"] == "271012"].set_index("Date")[["Imp_Price_USD_MT", "Imp_Weight_MT"]].rename(
        columns={"Imp_Price_USD_MT": "Naphtha_Customs_USD_MT", "Imp_Weight_MT": "Naphtha_Imp_Vol_MT"}
    )
    eth = df_raw[df_raw["HS_Code"] == "290121"].set_index("Date")[["Weighted_Price_USD_MT", "Exp_Weight_MT"]].rename(
        columns={"Weighted_Price_USD_MT": "Ethylene_USD_MT", "Exp_Weight_MT": "Ethylene_Exp_Vol_MT"}
    )
    prop = df_raw[df_raw["HS_Code"] == "290122"].set_index("Date")[["Weighted_Price_USD_MT", "Exp_Weight_MT"]].rename(
        columns={"Weighted_Price_USD_MT": "Propylene_USD_MT", "Exp_Weight_MT": "Propylene_Exp_Vol_MT"}
    )
    buta = df_raw[df_raw["HS_Code"] == "290124"].set_index("Date")[["Weighted_Price_USD_MT", "Imp_Weight_MT"]].rename(
        columns={"Weighted_Price_USD_MT": "Butadiene_USD_MT", "Imp_Weight_MT": "Butadiene_Imp_Vol_MT"}
    )

    customs_monthly = pd.concat([naph, eth, prop, buta], axis=1).sort_index()
    print(f"  - Customs HS Code Monthly Table: {customs_monthly.shape} ({customs_monthly.index.min().date()} ~ {customs_monthly.index.max().date()})")
    return customs_monthly


def fetch_freight_indices():
    """5. 해상 운임지수: KOBC 웹크롤링(KCCI, KDCI) + SCFI 크롤링(StockQ/SSE) + BDI 일별 시계열"""
    print("[5/6] Crawling Freight Indices (KOBC KCCI/KDCI, SCFI, and BDI)...")

    # (A) KOBC 컨테이너선 운임지수 (KCCI 및 주요 항로) 웹 테이블 크롤링
    r_kcci = crequests.post(
        "https://www.kobc.or.kr/ebz/shippinginfo/timeseries/gridList.do?mId=0304000000",
        data={"sDay": "2016-01-01", "eDay": "2026-11-15"},
        impersonate="chrome",
        verify=False,
    )
    soup_kcci = BeautifulSoup(r_kcci.text, "html.parser")
    kcci_rows = []
    for tr in soup_kcci.select("table tbody tr"):
        tds = [td.get_text(strip=True).replace(",", "") for td in tr.find_all("td")]
        if len(tds) >= 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", tds[0]):
            kcci_rows.append({
                "Date": pd.to_datetime(tds[0]),
                "KOBC_KCCI_Index": pd.to_numeric(tds[1], errors="coerce"),
            })
    df_kcci = pd.DataFrame(kcci_rows).drop_duplicates(subset=["Date"]).set_index("Date").sort_index()
    print(f"  - KOBC KCCI (Container Index): {len(df_kcci)} weekly rows ({df_kcci.index.min().date()} ~ {df_kcci.index.max().date()})")

    # (B) KOBC 건화물선 종합운임지수 (KDCI) JSON 크롤링
    r_kdci = crequests.post(
        "https://www.kobc.or.kr/ebz/shippinginfo/getChart2.do",
        json={"indxCd": "KDCI"},
        headers={"Accept": "application/json"},
        impersonate="chrome",
        verify=False,
    ).json()
    kdci_rows = []
    for ts_ms, val in r_kdci:
        dt = pd.to_datetime(int(ts_ms), unit="ms").normalize()
        if dt >= pd.Timestamp("2016-01-01"):
            kdci_rows.append({"Date": dt, "KOBC_KDCI_Index": float(val)})
    df_kdci = pd.DataFrame(kdci_rows).drop_duplicates(subset=["Date"]).set_index("Date").sort_index()
    print(f"  - KOBC KDCI (Drybulk Index): {len(df_kdci)} rows ({df_kdci.index.min().date()} ~ {df_kdci.index.max().date()})")

    # (C) SCFI (상하이 컨테이너 운임지수): StockQ 차트 데이터 + 상하이해운거래소(SSE) 최신 고시치 크롤링
    r_scfi = crequests.get(
        "https://www.stockq.org/index/chart-data.php?id=SCFI&type=sma&range=2y",
        headers={"Referer": "https://www.stockq.org/index/SCFI.php"},
        impersonate="chrome",
        verify=False,
    )
    scfi_rows = []
    for m in re.finditer(r"\[new Date\('([^']+)'\),\s*([0-9.]+)", r_scfi.text):
        scfi_rows.append({
            "Date": pd.to_datetime(m.group(1)),
            "SCFI_Index": float(m.group(2)),
        })
    # SSE 공식 최신 SCFI 추가 확인
    try:
        r_sse = crequests.get("https://en.sse.net.cn/currentIndex?indexName=scfi", impersonate="chrome", verify=False).json()
        sse_data = r_sse.get("data", {})
        if sse_data.get("currentDate") and sse_data.get("lineDataList"):
            scfi_rows.append({
                "Date": pd.to_datetime(sse_data["currentDate"]),
                "SCFI_Index": round(float(sse_data["lineDataList"][0]["currentContent"]), 2),
            })
    except Exception:
        pass
    df_scfi = pd.DataFrame(scfi_rows).drop_duplicates(subset=["Date"], keep="last").set_index("Date").sort_index()
    print(f"  - SCFI (Shanghai Containerized Freight Index): {len(df_scfi)} weekly rows ({df_scfi.index.min().date()} ~ {df_scfi.index.max().date()})")

    # (D) BDI (발틱운임지수): Investing API (pairId=940793) 2016~2026 전체 일별 원지수 수집
    r_bdi = crequests.get(
        "https://api.investing.com/api/financialdata/historical/940793?start-date=2016-01-01&end-date=2026-11-15&time-frame=Daily&add-missing-rows=false",
        headers={"domain-id": "www", "Referer": "https://www.investing.com/"},
        impersonate="chrome",
        verify=False,
    ).json()
    bdi_rows = []
    for row in r_bdi.get("data", []):
        dt = pd.to_datetime(row["rowDateTimestamp"]).tz_localize(None).normalize()
        val = float(row["last_closeRaw"])
        bdi_rows.append({"Date": dt, "BDI_Index": val})
    df_bdi = pd.DataFrame(bdi_rows).drop_duplicates(subset=["Date"]).set_index("Date").sort_index()
    print(f"  - BDI (Baltic Dry Index): {len(df_bdi)} daily rows ({df_bdi.index.min().date()} ~ {df_bdi.index.max().date()})")

    return df_kcci, df_kdci, df_scfi, df_bdi


def build_integrated_databases():
    os.makedirs("data/sources", exist_ok=True)

    df_yf = fetch_yfinance_series("2016-01-01")
    df_knoc = fetch_knoc_opinet_dubai_and_naphtha(2016, 2026)
    df_fred_dubai = fetch_fred_dubai_monthly()
    df_customs = fetch_customs_petrochem_prices()
    df_kcci, df_kdci, df_scfi, df_bdi = fetch_freight_indices()

    # 개별 원천 데이터 저장 (data/sources/)
    df_knoc.to_csv("data/sources/knoc_dubai_naphtha_daily.csv", encoding="utf-8-sig")
    df_fred_dubai.to_csv("data/sources/fred_dubai_monthly.csv", encoding="utf-8-sig")
    df_customs.to_csv("data/sources/customs_petrochem_monthly.csv", encoding="utf-8-sig")
    df_kcci.to_csv("data/sources/kobc_kcci_weekly.csv", encoding="utf-8-sig")
    df_kdci.to_csv("data/sources/kobc_kdci_daily.csv", encoding="utf-8-sig")
    df_scfi.to_csv("data/sources/sse_scfi_weekly.csv", encoding="utf-8-sig")
    df_bdi.to_csv("data/sources/bdi_daily.csv", encoding="utf-8-sig")

    print("\n[6/6] Merging all datasets into Daily, Weekly, and Monthly Master Databases...")

    # 1) 일별(Daily) 통합 테이블 구성
    daily_index = pd.date_range(start="2016-01-01", end="2026-11-15", freq="B")  # 영업일(Business Day) 기준
    daily_df = pd.DataFrame(index=daily_index)
    daily_df.index.name = "Date"

    # 일별/주별 지표 병합
    daily_df = daily_df.join(df_yf, how="left")
    daily_df = daily_df.join(df_knoc, how="left")
    daily_df = daily_df.join(df_bdi, how="left")
    daily_df = daily_df.join(df_kdci, how="left")
    daily_df = daily_df.join(df_kcci, how="left")
    daily_df = daily_df.join(df_scfi, how="left")

    # 월별 데이터(FRED 두바이유, 관세청 석화 4대 제품 단가 및 물량)는 해당 월(Year-Month) 기준으로 매핑
    daily_df["YearMonth"] = daily_df.index.to_period("M")
    fred_m = df_fred_dubai.copy()
    fred_m["YearMonth"] = fred_m.index.to_period("M")
    customs_m = df_customs.copy()
    customs_m["YearMonth"] = customs_m.index.to_period("M")

    daily_df = daily_df.reset_index().merge(fred_m, on="YearMonth", how="left").merge(customs_m, on="YearMonth", how="left")
    daily_df = daily_df.set_index("Date").drop(columns=["YearMonth"]).sort_index()

    # 시계열 보간 (Forward-Fill 후 초기 시점만 제한적 보간; 단, KCCI/SCFI/BDRY처럼 출시일 이후 존재하는 지표는 출시일 이전 NaN 유지 옵션과 모델링용 ffill/bfill 구분)
    # 원유, 가스, 환율, 두바이유, 납사, 관세청 석화 4종, BDI, KDCI는 2016년 1월부터 전 구간 존재하므로 ffill().bfill()
    core_cols = [
        "WTI_Crude_USD_bbl", "Brent_Crude_USD_bbl", "Dubai_Crude_USD_bbl", "Dubai_FRED_Monthly_USD_bbl",
        "HenryHub_Gas_USD_MMBtu", "USD_KRW", "USD_CNY",
        "Naphtha_Spot_USD_bbl", "Naphtha_Spot_USD_MT",
        "Naphtha_Customs_USD_MT", "Ethylene_USD_MT", "Propylene_USD_MT", "Butadiene_USD_MT",
        "Naphtha_Imp_Vol_MT", "Ethylene_Exp_Vol_MT", "Propylene_Exp_Vol_MT", "Butadiene_Imp_Vol_MT",
        "BDI_Index", "KOBC_KDCI_Index",
    ]
    daily_df[core_cols] = daily_df[core_cols].ffill().bfill()
    # 주간 컨테이너 운임지수(KOBC_KCCI_Index, SCFI_Index)와 BDRY_ETF_USD는 발표 시작일 이후로만 ffill()
    for c in ["KOBC_KCCI_Index", "SCFI_Index", "BDRY_ETF_USD"]:
        daily_df[c] = daily_df[c].ffill()

    # 석유화학 실무 핵심 파생 지표 (Spreads & Ratios) 산출
    # 1) 유종 간 스프레드 및 유가-가스 비율
    daily_df["Brent_Dubai_Spread_USD"] = (daily_df["Brent_Crude_USD_bbl"] - daily_df["Dubai_Crude_USD_bbl"]).round(2)
    daily_df["Oil_to_Gas_Ratio"] = (daily_df["WTI_Crude_USD_bbl"] / daily_df["HenryHub_Gas_USD_MMBtu"]).round(2)
    daily_df["Dubai_Crude_KRW_bbl"] = (daily_df["Dubai_Crude_USD_bbl"] * daily_df["USD_KRW"]).round(0)

    # 2) 정유사 납사 크랙 마진 ($/배럴): 일별 국제 납사($/bbl) - 일별 두바이유($/bbl)
    daily_df["Naphtha_Dubai_Crack_USD_bbl"] = (daily_df["Naphtha_Spot_USD_bbl"] - daily_df["Dubai_Crude_USD_bbl"]).round(2)

    # 3) NCC 3대 기초유분 마진 스프레드 ($/톤, 국제 현물 납사 대비 및 관세청 납사 대비)
    daily_df["Ethylene_Naphtha_Spread_USD_MT"] = (daily_df["Ethylene_USD_MT"] - daily_df["Naphtha_Spot_USD_MT"]).round(2)
    daily_df["Propylene_Naphtha_Spread_USD_MT"] = (daily_df["Propylene_USD_MT"] - daily_df["Naphtha_Spot_USD_MT"]).round(2)
    daily_df["Butadiene_Naphtha_Spread_USD_MT"] = (daily_df["Butadiene_USD_MT"] - daily_df["Naphtha_Spot_USD_MT"]).round(2)

    daily_df = daily_df.round(2)

    # 2) 주간(Weekly - 금요일 마감) 통합 데이터베이스
    weekly_df = daily_df.resample("W-FRI").mean().round(2)

    # 3) 월별(Monthly - 월초 MS 기준) 통합 데이터베이스
    monthly_df = daily_df.resample("MS").mean().round(2)

    # 파일 저장 (기존 stage1_macro_energy_base.csv도 확장된 통합본으로 업데이트하고 전용 파일도 함께 생성)
    daily_df.to_csv("data/stage1_macro_energy_base.csv", encoding="utf-8-sig")
    weekly_df.to_csv("data/stage1_macro_energy_weekly.csv", encoding="utf-8-sig")
    daily_df.to_csv("data/petrochem_integrated_daily_db.csv", encoding="utf-8-sig")
    weekly_df.to_csv("data/petrochem_integrated_weekly_db.csv", encoding="utf-8-sig")
    monthly_df.to_csv("data/petrochem_integrated_monthly_db.csv", encoding="utf-8-sig")

    print("\n=== Integrated Master Database Summary ===")
    print(f"Daily Master DB Shape:   {daily_df.shape}")
    print(f"Weekly Master DB Shape:  {weekly_df.shape}")
    print(f"Monthly Master DB Shape: {monthly_df.shape}")
    print("\nMissing Values in Daily DB:")
    print(daily_df.isna().sum())
    print("\nLatest 5 Rows of Monthly Master DB:")
    cols_preview = [
        "Dubai_Crude_USD_bbl", "Naphtha_Spot_USD_MT", "Ethylene_USD_MT",
        "Propylene_USD_MT", "Butadiene_USD_MT", "Ethylene_Naphtha_Spread_USD_MT",
        "SCFI_Index", "KOBC_KCCI_Index", "BDI_Index",
    ]
    print(monthly_df[cols_preview].tail(5).to_string())


if __name__ == "__main__":
    build_integrated_databases()
