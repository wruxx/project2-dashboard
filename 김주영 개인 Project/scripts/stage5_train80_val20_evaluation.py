import os
import json
import shutil
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from statsmodels.tsa.stattools import coint
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

warnings.filterwarnings("ignore")

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150

BASE_DIR = r"c:\Users\hongy\Desktop\공부\AI\portfolio"
DATA_DIR = os.path.join(BASE_DIR, "data")
FIG_DIR = os.path.join(BASE_DIR, "reports", "figures")
ARTIFACT_DIR = r"C:\Users\hongy\.gemini\antigravity\brain\f7a479ab-83d3-446b-8f88-62adb26ba22d"

os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# 1. 주간 통합 데이터 로드
df_w = pd.read_csv(os.path.join(DATA_DIR, "petrochem_integrated_weekly_db.csv"), parse_dates=["Date"])
df_w = df_w.sort_values("Date").reset_index(drop=True)

df_w["Dubai_USD"] = df_w["Dubai_Crude_USD_bbl"]
df_w["Brent_USD"] = df_w["Brent_Crude_USD_bbl"]
df_w["WTI_USD"] = df_w["WTI_Crude_USD_bbl"]
df_w["HenryHub_NG_USD"] = df_w["HenryHub_Gas_USD_MMBtu"]
df_w["KOBC_KDCI"] = df_w["KOBC_KDCI_Index"]
df_w["KOBC_KCCI"] = df_w["KOBC_KCCI_Index"]
df_w["Naphtha_Crack_Spread_USD_MT"] = df_w["Naphtha_Spot_USD_MT"] - (df_w["Dubai_USD"] * 7.33)

# 2. 파생 피처 엔지니어링
df_feat = df_w.copy()
df_feat["SCFI_Filled"] = df_feat["SCFI_Index"].bfill().ffill()
df_feat["KCCI_Filled"] = df_feat["KOBC_KCCI"].bfill().ffill()
df_feat["KDCI_Filled"] = df_feat["KOBC_KDCI"].bfill().ffill()
df_feat["BDI_Filled"] = df_feat["BDI_Index"].bfill().ffill()
df_feat["Brent_Dubai_Spread"] = df_feat["Brent_USD"] - df_feat["Dubai_USD"]
df_feat["Month"] = df_feat["Date"].dt.month

# 초기 시점(Lag 1~4주) 생성 전 임시 공적분 추정 (Train 80% 구간에서만 학습하도록 분리 예정)
lag_vars = [
    "Dubai_USD", "Brent_Dubai_Spread", "HenryHub_NG_USD", "Oil_to_Gas_Ratio",
    "USD_KRW", "USD_CNY", "BDI_Filled", "KDCI_Filled", "SCFI_Filled",
    "Naphtha_Spot_USD_MT", "Naphtha_Crack_Spread_USD_MT",
    "Ethylene_USD_MT", "Propylene_USD_MT", "Butadiene_USD_MT", "Ethylene_Naphtha_Spread_USD_MT"
]

for col in lag_vars:
    for l in [1, 2, 3, 4]:
        df_feat[f"{col}_Lag{l}"] = df_feat[col].shift(l)

for col in ["Dubai_USD", "Naphtha_Spot_USD_MT", "Ethylene_USD_MT", "USD_CNY", "BDI_Filled"]:
    df_feat[f"{col}_MA4_Lag1"] = df_feat[f"{col}_Lag1"].rolling(4).mean()
    df_feat[f"{col}_Std4_Lag1"] = df_feat[f"{col}_Lag1"].rolling(4).std()

naphtha_features_base = [
    "Dubai_USD_Lag1", "Dubai_USD_Lag2", "Dubai_USD_Lag3", "Dubai_USD_MA4_Lag1", "Dubai_USD_Std4_Lag1",
    "Brent_Dubai_Spread_Lag1", "HenryHub_NG_USD_Lag1", "Oil_to_Gas_Ratio_Lag1",
    "Naphtha_Spot_USD_MT_Lag1", "Naphtha_Spot_USD_MT_Lag2", "Naphtha_Spot_USD_MT_MA4_Lag1",
    "Naphtha_Crack_Spread_USD_MT_Lag1",
    "USD_KRW_Lag1", "USD_CNY_Lag1", "BDI_Filled_Lag1", "KDCI_Filled_Lag1", "SCFI_Filled_Lag1",
    "Propylene_USD_MT_Lag1", "Month"
]

ethylene_base_features = [
    "Naphtha_Spot_USD_MT_Lag1",
    "Naphtha_Spot_USD_MT_Lag2",
    "Naphtha_Spot_USD_MT_Lag3",
    "Ethylene_USD_MT_Lag1", "Ethylene_USD_MT_Lag2", "Ethylene_USD_MT_MA4_Lag1",
    "Propylene_USD_MT_Lag1", "Butadiene_USD_MT_Lag1",
    "USD_CNY_Lag1", "USD_CNY_Lag2", "USD_KRW_Lag1",
    "SCFI_Filled_Lag1", "BDI_Filled_Lag1",
    "Oil_to_Gas_Ratio_Lag1", "Month"
]

req_cols = list(set(naphtha_features_base + ethylene_base_features + ["Date", "Naphtha_Spot_USD_MT", "Ethylene_USD_MT"]))
df_model = df_feat.dropna(subset=req_cols).reset_index(drop=True)

# ==============================================================================
# 3. 엄격한 80% 학습(Train) : 20% 검증(Validation/Test) 시계열 분할
# ==============================================================================
n_total = len(df_model)
n_train = int(round(n_total * 0.80))
n_val = n_total - n_train

train_df = df_model.iloc[:n_train].copy()
val_df = df_model.iloc[n_train:].copy()

# 데이터 누수(Data Leakage) 방지를 위해 오직 Train 80% 구간에서만 공적분 균형식 추정!
X_coint_tr = np.column_stack([np.ones(len(train_df)), train_df["Dubai_USD_Lag1"].values])
beta_coint = np.linalg.lstsq(X_coint_tr, train_df["Naphtha_Spot_USD_MT_Lag1"].values, rcond=None)[0]

train_df["ECM_Error_Term_Lag1"] = train_df["Naphtha_Spot_USD_MT_Lag1"] - (beta_coint[0] + beta_coint[1] * train_df["Dubai_USD_Lag1"])
val_df["ECM_Error_Term_Lag1"] = val_df["Naphtha_Spot_USD_MT_Lag1"] - (beta_coint[0] + beta_coint[1] * val_df["Dubai_USD_Lag1"])

naphtha_features = naphtha_features_base + ["ECM_Error_Term_Lag1"]

print("=========================================================================")
print(f"[80:20 시계열 데이터 분할 완료] 전체 유효 주수: {n_total}주")
print(f" - 80% 학습 데이터(Train): {n_train}주 ({train_df['Date'].min().date()} ~ {train_df['Date'].max().date()})")
print(f" - 20% 검증 데이터(Val)  : {n_val}주 ({val_df['Date'].min().date()} ~ {val_df['Date'].max().date()})")
print(f" - Train 80% 공적분 균형식: Naphtha = {beta_coint[0]:.2f} + {beta_coint[1]:.4f} * Dubai_USD")
print("=========================================================================")

# ------------------------------------------------------------------------------
# Stage 1: 납사 현물가(Naphtha_Spot_USD_MT) 80% 학습 -> 20% 검증
# ------------------------------------------------------------------------------
X_tr_nap, y_tr_nap = train_df[naphtha_features], train_df["Naphtha_Spot_USD_MT"]
X_va_nap, y_va_nap = val_df[naphtha_features], val_df["Naphtha_Spot_USD_MT"]

model_ecm_nap = Ridge(alpha=1.0).fit(X_tr_nap, y_tr_nap)
pred_nap_ecm = model_ecm_nap.predict(X_va_nap)

model_xgb_nap = XGBRegressor(
    n_estimators=300, max_depth=4, learning_rate=0.03,
    subsample=0.85, colsample_bytree=0.85, random_state=42
).fit(X_tr_nap, y_tr_nap)
pred_nap_xgb = model_xgb_nap.predict(X_va_nap)

model_lgb_nap = LGBMRegressor(
    n_estimators=300, max_depth=4, learning_rate=0.03,
    subsample=0.85, colsample_bytree=0.85, random_state=42, verbose=-1
).fit(X_tr_nap, y_tr_nap)
pred_nap_lgb = model_lgb_nap.predict(X_va_nap)

pred_nap_ens = 0.50 * pred_nap_ecm + 0.25 * pred_nap_xgb + 0.25 * pred_nap_lgb

# ------------------------------------------------------------------------------
# Stage 2: 에틸렌 단가(Ethylene_USD_MT) 80% 학습 -> 20% 검증 (2주 시차 + 예측 납사가 연쇄 투입)
# ------------------------------------------------------------------------------
train_df["Pred_Naphtha_Stage1"] = (
    0.50 * model_ecm_nap.predict(X_tr_nap) +
    0.25 * model_xgb_nap.predict(X_tr_nap) +
    0.25 * model_lgb_nap.predict(X_tr_nap)
)
val_df["Pred_Naphtha_Stage1"] = pred_nap_ens

ethylene_features = ["Pred_Naphtha_Stage1"] + ethylene_base_features

X_tr_eth, y_tr_eth = train_df[ethylene_features], train_df["Ethylene_USD_MT"]
X_va_eth, y_va_eth = val_df[ethylene_features], val_df["Ethylene_USD_MT"]

model_ecm_eth = Ridge(alpha=1.0).fit(X_tr_eth, y_tr_eth)
pred_eth_ecm = model_ecm_eth.predict(X_va_eth)

model_xgb_eth = XGBRegressor(
    n_estimators=300, max_depth=4, learning_rate=0.03,
    subsample=0.85, colsample_bytree=0.85, random_state=42
).fit(X_tr_eth, y_tr_eth)
pred_eth_xgb = model_xgb_eth.predict(X_va_eth)

model_lgb_eth = LGBMRegressor(
    n_estimators=300, max_depth=4, learning_rate=0.03,
    subsample=0.85, colsample_bytree=0.85, random_state=42, verbose=-1
).fit(X_tr_eth, y_tr_eth)
pred_eth_lgb = model_lgb_eth.predict(X_va_eth)

pred_eth_ens = 0.45 * pred_eth_ecm + 0.30 * pred_eth_xgb + 0.25 * pred_eth_lgb

# 마진 스프레드 예측치 (Stage 2 에틸렌 예측치 - Stage 1 납사 예측치)
y_va_spread = val_df["Ethylene_Naphtha_Spread_USD_MT"].values
pred_spread_ecm = pred_eth_ecm - pred_nap_ecm
pred_spread_xgb = pred_eth_xgb - pred_nap_xgb
pred_spread_lgb = pred_eth_lgb - pred_nap_lgb
pred_spread_ens = pred_eth_ens - pred_nap_ens

def calc_eval_row(y_true, y_pred, y_lag1, target_label, model_label):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    mape = np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), 1.0))) * 100
    r2 = r2_score(y_true, y_pred)
    # 주간 등락 방향성 적중률 (Directional Accuracy)
    actual_dir = np.sign(y_true - y_lag1)
    pred_dir = np.sign(y_pred - y_lag1)
    dir_acc = np.mean(actual_dir == pred_dir) * 100
    return {
        "Target": target_label,
        "Model": model_label,
        "Train_Weeks(80%)": n_train,
        "Val_Weeks(20%)": n_val,
        "RMSE ($/MT)": round(float(rmse), 2),
        "MAE ($/MT)": round(float(mae), 2),
        "MAPE (%)": round(float(mape), 2),
        "R2_Score": round(float(r2), 4),
        "Dir_Accuracy (%)": round(float(dir_acc), 1)
    }

nap_lag1 = val_df["Naphtha_Spot_USD_MT_Lag1"].values
eth_lag1 = val_df["Ethylene_USD_MT_Lag1"].values
spr_lag1 = val_df["Ethylene_Naphtha_Spread_USD_MT_Lag1"].values

eval_rows = [
    calc_eval_row(y_va_nap.values, pred_nap_ecm, nap_lag1, "납사 현물가 (Naphtha)", "1. 공인기관 공적분 오차수정 (ECM-Ridge)"),
    calc_eval_row(y_va_nap.values, pred_nap_xgb, nap_lag1, "납사 현물가 (Naphtha)", "2. AI 트리 부스팅 (XGBoost)"),
    calc_eval_row(y_va_nap.values, pred_nap_lgb, nap_lag1, "납사 현물가 (Naphtha)", "3. AI 경량 부스팅 (LightGBM)"),
    calc_eval_row(y_va_nap.values, pred_nap_ens, nap_lag1, "납사 현물가 (Naphtha)", "4. 하이브리드 앙상블 (ECM+XGB+LGB)"),
    calc_eval_row(y_va_eth.values, pred_eth_ecm, eth_lag1, "에틸렌 단가 (Ethylene)", "1. 공인기관 선형 전가 모형 (Chained Ridge)"),
    calc_eval_row(y_va_eth.values, pred_eth_xgb, eth_lag1, "에틸렌 단가 (Ethylene)", "2. 2주 시차 반영 연쇄 XGBoost"),
    calc_eval_row(y_va_eth.values, pred_eth_lgb, eth_lag1, "에틸렌 단가 (Ethylene)", "3. 2주 시차 반영 연쇄 LightGBM"),
    calc_eval_row(y_va_eth.values, pred_eth_ens, eth_lag1, "에틸렌 단가 (Ethylene)", "4. 2-Stage 하이브리드 연쇄 앙상블"),
    calc_eval_row(y_va_spread, pred_spread_ecm, spr_lag1, "에틸렌-납사 스프레드 (Spread)", "1. 공적분 선형 스프레드 예측"),
    calc_eval_row(y_va_spread, pred_spread_xgb, spr_lag1, "에틸렌-납사 스프레드 (Spread)", "2. 연쇄 XGBoost 스프레드 예측"),
    calc_eval_row(y_va_spread, pred_spread_lgb, spr_lag1, "에틸렌-납사 스프레드 (Spread)", "3. 연쇄 LightGBM 스프레드 예측"),
    calc_eval_row(y_va_spread, pred_spread_ens, spr_lag1, "에틸렌-납사 스프레드 (Spread)", "4. 2-Stage 하이브리드 스프레드 앙상블"),
]

df_eval = pd.DataFrame(eval_rows)
print("\n[80% Train (451주) / 20% Validation (113주: 2024.09~2026.11) 검증 결과표]")
print(df_eval.to_string(index=False))
df_eval.to_csv(os.path.join(DATA_DIR, "stage5_train80_val20_metrics.csv"), index=False, encoding="utf-8-sig")

# 검증 구간 예측 데이터프레임 저장
val_out = pd.DataFrame({
    "Date": val_df["Date"].dt.strftime("%Y-%m-%d"),
    "Dubai_USD": val_df["Dubai_USD"].round(2),
    "USD_KRW": val_df["USD_KRW"].round(1),
    "USD_CNY": val_df["USD_CNY"].round(3),
    "SCFI_Index": val_df["SCFI_Filled"].round(1),
    "Actual_Naphtha": y_va_nap.round(2),
    "Pred_Naphtha_ECM": np.round(pred_nap_ecm, 2),
    "Pred_Naphtha_XGB": np.round(pred_nap_xgb, 2),
    "Pred_Naphtha_LGB": np.round(pred_nap_lgb, 2),
    "Pred_Naphtha_Ensemble": np.round(pred_nap_ens, 2),
    "Actual_Ethylene": y_va_eth.round(2),
    "Pred_Ethylene_ECM": np.round(pred_eth_ecm, 2),
    "Pred_Ethylene_XGB": np.round(pred_eth_xgb, 2),
    "Pred_Ethylene_LGB": np.round(pred_eth_lgb, 2),
    "Pred_Ethylene_Ensemble": np.round(pred_eth_ens, 2),
    "Actual_Spread": np.round(y_va_spread, 2),
    "Pred_Spread_Ensemble": np.round(pred_spread_ens, 2),
})
val_out.to_csv(os.path.join(DATA_DIR, "stage5_val20_predictions.csv"), index=False, encoding="utf-8-sig")

# ==============================================================================
# 4. 80:20 분할 검증 시각화 차트 생성
# ==============================================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 11))

# (A) 전체 시계열(80% Train vs 20% Validation 분할 구조 및 납사 예측)
ax = axes[0, 0]
ax.plot(train_df["Date"], train_df["Naphtha_Spot_USD_MT"], color="#64748b", linewidth=1.5, alpha=0.8, label=f"80% 학습 데이터 (Train: {n_train}주, 2016.01~2024.09)")
ax.plot(val_df["Date"], y_va_nap, color="#111827", linewidth=2.0, label=f"20% 검증 실제값 (Val Actual: {n_val}주, 2024.09~2026.11)")
ax.plot(val_df["Date"], pred_nap_ens, color="#e11d48", linewidth=1.8, linestyle="--", label=f"20% 하이브리드 앙상블 예측 (MAPE={df_eval.iloc[3]['MAPE (%)']}%)")
ax.axvline(val_df["Date"].iloc[0], color="#2563eb", linestyle="-.", linewidth=2.0, label="80:20 분할 기준선 (2024-09-20)")
ax.axvspan(val_df["Date"].iloc[0], val_df["Date"].iloc[-1], color="#dbeafe", alpha=0.35)
ax.set_title("(A) 전체 564주 80% 학습(Train) : 20% 검증(Validation) 분할 및 납사 예측", fontsize=12.5, fontweight="bold")
ax.set_ylabel("납사 현물가 (USD/MT)", fontsize=10.5, fontweight="bold")
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper left", fontsize=8.8)

# (B) 20% 검증 구간(113주) 확대: 납사 현물가 모델별 예측 비교
ax = axes[0, 1]
ax.plot(val_df["Date"], y_va_nap, color="#111827", linewidth=2.3, marker="o", markersize=2.8, label="실제 납사 현물가 (Actual)")
ax.plot(val_df["Date"], pred_nap_ens, color="#e11d48", linewidth=2.0, linestyle="--", label=f"하이브리드 앙상블 (MAPE={df_eval.iloc[3]['MAPE (%)']}%, R²={df_eval.iloc[3]['R2_Score']})")
ax.plot(val_df["Date"], pred_nap_ecm, color="#0284c7", linewidth=1.3, alpha=0.75, linestyle=":", label=f"공적분 ECM-Ridge (MAPE={df_eval.iloc[0]['MAPE (%)']}%)")
ax.plot(val_df["Date"], pred_nap_xgb, color="#f59e0b", linewidth=1.3, alpha=0.75, linestyle="-.", label=f"XGBoost (MAPE={df_eval.iloc[1]['MAPE (%)']}%)")
ax.fill_between(val_df["Date"], pred_nap_ens - 25, pred_nap_ens + 25, color="#e11d48", alpha=0.14, label="앙상블 신뢰구간 (±25 USD)")
ax.set_title("(B) [20% 검증 구간(113주) 확대] Stage 1 납사 가격 모델별 예측 정확도", fontsize=12.5, fontweight="bold")
ax.set_ylabel("납사 현물가 (USD/MT)", fontsize=10.5, fontweight="bold")
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper left", fontsize=8.8)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))

# (C) 20% 검증 구간(113주) 확대: 에틸렌 단가 2주 시차 연쇄 예측 비교
ax = axes[1, 0]
ax.plot(val_df["Date"], y_va_eth, color="#111827", linewidth=2.3, marker="o", markersize=2.8, label="실제 에틸렌 단가 (Actual)")
ax.plot(val_df["Date"], pred_eth_ens, color="#2563eb", linewidth=2.0, linestyle="--", label=f"2-Stage 연쇄 앙상블 (MAPE={df_eval.iloc[7]['MAPE (%)']}%, R²={df_eval.iloc[7]['R2_Score']})")
ax.plot(val_df["Date"], pred_eth_ecm, color="#059669", linewidth=1.3, alpha=0.75, linestyle=":", label=f"선형 전가 Ridge (MAPE={df_eval.iloc[4]['MAPE (%)']}%)")
ax.plot(val_df["Date"], pred_eth_xgb, color="#d97706", linewidth=1.3, alpha=0.75, linestyle="-.", label=f"연쇄 XGBoost (MAPE={df_eval.iloc[5]['MAPE (%)']}%)")
ax.fill_between(val_df["Date"], pred_eth_ens - 25, pred_eth_ens + 25, color="#2563eb", alpha=0.14, label="앙상블 신뢰구간 (±25 USD)")
ax.set_title("(C) [20% 검증 구간(113주) 확대] Stage 2 에틸렌 2주 시차 연쇄 예측 정확도", fontsize=12.5, fontweight="bold")
ax.set_ylabel("에틸렌 단가 (USD/MT)", fontsize=10.5, fontweight="bold")
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper left", fontsize=8.8)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))

# (D) 20% 검증 구간(113주): 에틸렌-납사 마진 스프레드 실제 vs 예측 및 가동률 의사결정 구간
ax = axes[1, 1]
ax.plot(val_df["Date"], y_va_spread, color="#111827", linewidth=2.2, label="실제 에틸렌-납사 스프레드 (Actual)")
ax.plot(val_df["Date"], pred_spread_ens, color="#7c3aed", linewidth=2.0, linestyle="--", label=f"2-Stage 예측 스프레드 (MAE={df_eval.iloc[11]['MAE ($/MT)']} USD)")
ax.axhline(250, color="#10b981", linestyle="--", linewidth=1.8, label="손익분기점 (BEP = 250 USD/MT)")
ax.axhline(200, color="#ef4444", linestyle=":", linewidth=1.8, label="감산 임계선 (200 USD/MT)")
ax.fill_between(val_df["Date"], y_va_spread, 200, where=(y_va_spread < 200), color="#ef4444", alpha=0.18, label="실제 적자 감산 구간 (<200 USD)")
ax.set_title("(D) [20% 검증 구간(113주)] 에틸렌-납사 마진 스프레드 예측 및 감산 구간 포착", fontsize=12.5, fontweight="bold")
ax.set_ylabel("에틸렌-납사 스프레드 (USD/MT)", fontsize=10.5, fontweight="bold")
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper left", fontsize=8.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))

plt.tight_layout()
p_val_fig = os.path.join(FIG_DIR, "stage5_train80_val20_validation.png")
plt.savefig(p_val_fig, dpi=180, bbox_inches="tight")
shutil.copy(p_val_fig, os.path.join(ARTIFACT_DIR, "stage5_train80_val20_validation.png"))
plt.close()

print("\n[80:20 검증 차트 및 CSV 저장 완료!]")
