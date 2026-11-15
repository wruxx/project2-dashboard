import os
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Windows 한글 폰트 설정 (맑은 고딕) 및 마이너스 기호 깨짐 방지
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def run_pearson_correlation_analysis():
    os.makedirs("reports/figures", exist_ok=True)
    artifact_dir = r"C:\Users\hongy\.gemini\antigravity\brain\f7a479ab-83d3-446b-8f88-62adb26ba22d"
    os.makedirs(artifact_dir, exist_ok=True)

    # 주간(Weekly) 및 월간(Monthly) 통합 DB 로드
    df_w = pd.read_csv("data/petrochem_integrated_weekly_db.csv", parse_dates=["Date"], index_col="Date")
    df_m = pd.read_csv("data/petrochem_integrated_monthly_db.csv", parse_dates=["Date"], index_col="Date")

    # =========================================================================
    # 1. 전체 기간(2016~2026, 주간 568주) 15대 핵심 요인 피어슨 상관계수 히트맵
    # =========================================================================
    col_map_full = {
        "Dubai_Crude_USD_bbl": "두바이유 ($/bbl)",
        "Brent_Crude_USD_bbl": "브렌트유 ($/bbl)",
        "WTI_Crude_USD_bbl": "WTI유 ($/bbl)",
        "HenryHub_Gas_USD_MMBtu": "천연가스 ($/MMBtu)",
        "Oil_to_Gas_Ratio": "유가/가스 비율 (배)",
        "USD_KRW": "원/달러 환율 (KRW)",
        "USD_CNY": "위안/달러 환율 (CNY)",
        "Naphtha_Spot_USD_MT": "납사 현물가 ($/톤)",
        "Naphtha_Customs_USD_MT": "납사 통관단가 ($/톤)",
        "Ethylene_USD_MT": "에틸렌 ($/톤)",
        "Propylene_USD_MT": "프로필렌 ($/톤)",
        "Butadiene_USD_MT": "부타디엔 ($/톤)",
        "Ethylene_Naphtha_Spread_USD_MT": "에틸렌-납사 스프레드",
        "Naphtha_Imp_Vol_MT": "납사 수입물량 (톤)",
        "BDI_Index": "BDI 벌크운임지수",
        "KOBC_KDCI_Index": "KOBC 건화물운임(KDCI)",
    }

    df_corr_full = df_w[list(col_map_full.keys())].rename(columns=col_map_full).corr(method="pearson")
    df_corr_full.to_csv("data/pearson_corr_full_2016_2026.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(15, 12), dpi=180)
    mask = np.triu(np.ones_like(df_corr_full, dtype=bool), k=1)
    sns.heatmap(
        df_corr_full,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        center=0,
        square=True,
        linewidths=0.6,
        cbar_kws={"shrink": 0.82, "label": "Pearson 상관계수 (r)"},
        annot_kws={"size": 9, "weight": "bold"},
        ax=ax,
    )
    ax.set_title(
        "[전체 기간: 2016~2026] 원유·가스·환율·석유화학(납사/C2/C3/C4)·운임 피어슨 상관계수 히트맵 (n=568주)",
        fontsize=15,
        fontweight="bold",
        pad=18,
    )
    plt.xticks(rotation=35, ha="right", fontsize=10, fontweight="bold")
    plt.yticks(rotation=0, fontsize=10, fontweight="bold")
    plt.tight_layout()

    fig1_path = "reports/figures/pearson_heatmap_full_2016_2026.png"
    plt.savefig(fig1_path, dpi=180)
    shutil.copyfile(fig1_path, os.path.join(artifact_dir, "pearson_heatmap_full_2016_2026.png"))
    plt.close(fig)

    # =========================================================================
    # 2. 해운 운임(SCFI, KOBC_KCCI, BDI) 집중 구간(2021.05~2026.11) + 시차(Lag) 상관관계 히트맵
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8.5), dpi=180, gridspec_kw={"width_ratios": [1.35, 1.0]})

    # (좌측 패널) SCFI / KCCI 포함 구간 피어슨 상관계수 히트맵
    col_map_freight = {
        "Dubai_Crude_USD_bbl": "두바이유",
        "Naphtha_Spot_USD_MT": "납사 현물가",
        "Ethylene_USD_MT": "에틸렌",
        "Propylene_USD_MT": "프로필렌",
        "Butadiene_USD_MT": "부타디엔",
        "Ethylene_Naphtha_Spread_USD_MT": "에틸렌 스프레드",
        "Naphtha_Imp_Vol_MT": "납사 수입물량",
        "USD_KRW": "원/달러 환율",
        "USD_CNY": "위안/달러 환율",
        "SCFI_Index": "SCFI 컨테이너운임",
        "KOBC_KCCI_Index": "KOBC 컨테이너(KCCI)",
        "BDI_Index": "BDI 벌크운임",
    }
    df_sub = df_w.loc["2021-05-21":, list(col_map_freight.keys())].rename(columns=col_map_freight)
    corr_freight = df_sub.corr(method="pearson")
    corr_freight.to_csv("data/pearson_corr_freight_2021_2026.csv", encoding="utf-8-sig")

    sns.heatmap(
        corr_freight,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        center=0,
        linewidths=0.6,
        cbar_kws={"shrink": 0.8, "label": "Pearson r"},
        annot_kws={"size": 9, "weight": "bold"},
        ax=ax1,
    )
    ax1.set_title(
        "(A) 해운운임(SCFI·KCCI·BDI) 포함 피어슨 상관계수 (2021.05~2026.11)",
        fontsize=13,
        fontweight="bold",
        pad=14,
    )
    ax1.tick_params(axis="x", rotation=35)
    for label in ax1.get_xticklabels():
        label.set_horizontalalignment("right")
        label.set_fontweight("bold")
    for label in ax1.get_yticklabels():
        label.set_fontweight("bold")

    # (우측 패널) 원유·가스·환율·운임의 시차(Lag 0주 ~ 8주)별 납사 & 에틸렌 가격 상관계수 히트맵
    lags = [0, 1, 2, 3, 4, 6, 8]
    drivers = {
        "Dubai_Crude_USD_bbl": "두바이유 -> 납사 현물가",
        "Brent_Crude_USD_bbl": "브렌트유 -> 납사 현물가",
        "Dubai_Crude_KRW_bbl": "원화환산 두바이유 -> 납사 현물가",
    }
    eth_drivers = {
        "Naphtha_Spot_USD_MT": "납사 현물가 -> 에틸렌 단가",
        "Dubai_Crude_USD_bbl": "두바이유 -> 에틸렌 단가",
        "Propylene_USD_MT": "프로필렌 -> 에틸렌 단가",
        "Butadiene_USD_MT": "부타디엔 -> 에틸렌 단가",
        "BDI_Index": "BDI 운임 -> 에틸렌 단가",
        "SCFI_Index": "SCFI 운임 -> 에틸렌 단가",
        "USD_KRW": "원/달러 환율 -> 에틸렌 스프레드",
        "Oil_to_Gas_Ratio": "유가/가스 비율 -> 에틸렌 스프레드",
    }

    lag_matrix = {}
    for col, label in drivers.items():
        row_vals = {}
        for l in lags:
            row_vals[f"Lag {l}주"] = df_w["Naphtha_Spot_USD_MT"].corr(df_w[col].shift(l))
        lag_matrix[label] = row_vals

    for col, label in eth_drivers.items():
        target_col = "Ethylene_Naphtha_Spread_USD_MT" if "스프레드" in label else "Ethylene_USD_MT"
        row_vals = {}
        for l in lags:
            row_vals[f"Lag {l}주"] = df_w[target_col].corr(df_w[col].shift(l))
        lag_matrix[label] = row_vals

    df_lag_corr = pd.DataFrame(lag_matrix).T
    df_lag_corr.to_csv("data/pearson_lag_correlation_matrix.csv", encoding="utf-8-sig")

    sns.heatmap(
        df_lag_corr,
        annot=True,
        fmt=".3f",
        cmap="YlOrRd" if df_lag_corr.min().min() > 0 else "coolwarm",
        vmin=-0.6,
        vmax=1.0,
        center=0.2,
        linewidths=0.6,
        cbar_kws={"shrink": 0.8, "label": "시차별 Pearson r"},
        annot_kws={"size": 9.5, "weight": "bold"},
        ax=ax2,
    )
    ax2.set_title(
        "(B) 선행 시차(Lag 0~8주)별 납사·에틸렌 피어슨 상관계수 추이",
        fontsize=13,
        fontweight="bold",
        pad=14,
    )
    ax2.tick_params(axis="x", rotation=0)
    for label in ax2.get_xticklabels():
        label.set_fontweight("bold")
    for label in ax2.get_yticklabels():
        label.set_fontweight("bold")

    plt.tight_layout()
    fig2_path = "reports/figures/pearson_heatmap_lag_and_freight.png"
    plt.savefig(fig2_path, dpi=180)
    shutil.copyfile(fig2_path, os.path.join(artifact_dir, "pearson_heatmap_lag_and_freight.png"))
    plt.close(fig)

    # =========================================================================
    # 3. 계층적 군집 클러스터맵 (Clustermap) 생성
    # =========================================================================
    g = sns.clustermap(
        df_corr_full,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        center=0,
        figsize=(13, 11),
        linewidths=0.5,
        annot_kws={"size": 8.5, "weight": "bold"},
        cbar_kws={"label": "Pearson r"},
    )
    g.fig.suptitle(
        "석유화학 밸류체인 16대 요인 계층적 군집(Clustermap) 피어슨 상관구조",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig3_path = "reports/figures/pearson_clustermap_hierarchy.png"
    g.savefig(fig3_path, dpi=180, bbox_inches="tight")
    shutil.copyfile(fig3_path, os.path.join(artifact_dir, "pearson_clustermap_hierarchy.png"))
    plt.close("all")

    print("=== 1. Top Correlations with Naphtha_Spot_USD_MT ===")
    print(df_corr_full["납사 현물가 ($/톤)"].sort_values(ascending=False).round(4))
    print("\n=== 2. Top Correlations with Ethylene_USD_MT ===")
    print(df_corr_full["에틸렌 ($/톤)"].sort_values(ascending=False).round(4))
    print("\n=== 3. Top Correlations with Ethylene_Naphtha_Spread_USD_MT ===")
    print(df_corr_full["에틸렌-납사 스프레드"].sort_values(ascending=False).round(4))
    print("\n=== 4. Freight Correlations (2021.05~2026.11) ===")
    print(corr_freight[["납사 현물가", "에틸렌", "에틸렌 스프레드", "납사 수입물량", "SCFI 컨테이너운임", "KOBC 컨테이너(KCCI)", "BDI 벌크운임"]].round(4))
    print("\n=== 5. Lag Correlation Matrix ===")
    print(df_lag_corr.round(4).to_string())


if __name__ == "__main__":
    run_pearson_correlation_analysis()
