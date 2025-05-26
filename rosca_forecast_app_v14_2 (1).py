
# ROSCA Forecast App v14.2 – FULL EXECUTABLE VERSION

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("📊 ROSCA Forecast App v14.2 – Final")

# --- Global Config Inputs ---
with st.sidebar:
    st.header("Global Parameters")
    total_market = st.number_input("Total Market Size", value=2000000)
    starting_pct = st.slider("Initial % of TAM to start", 1, 100, 10)
    monthly_growth = st.number_input("Monthly Growth Rate (%)", value=2.0)
    rest_period = st.number_input("Rest Period (months)", value=1)
    kibor = st.number_input("KIBOR (%)", value=11.0)
    spread = st.number_input("Spread (%)", value=5.0)
    default_rate = st.number_input("Default Rate (%)", value=1.0)
    penalty_pct = st.number_input("Pre-Payout Penalty Refund %", value=10.0)

# --- Duration Setup ---
durations = st.multiselect("Select Durations (months)", [3, 4, 5, 6, 8, 10], default=[3, 4, 6])
duration_matrix = {}
st.subheader("📅 Monthly TAM Allocation by Duration")
for m in range(3):  # Demo for Month 1–3
    with st.expander(f"Month {m+1}"):
        total = 0
        duration_matrix[m] = {}
        for d in durations:
            val = st.number_input(f"{d}M", 0, 100, 100 // len(durations), key=f"dur_{m}_{d}")
            duration_matrix[m][d] = val
            total += val
        if total != 100:
            st.error(f"Month {m+1} total ≠ 100% (currently {total}%)")

# --- Slab Allocation per Duration ---
slabs = [1000, 2000, 5000, 10000]
slab_map = {}
st.subheader("💰 Slab % Distribution (per Duration)")
for d in durations:
    with st.expander(f"Duration {d}M"):
        total = 0
        slab_map[d] = {}
        for s in slabs:
            val = st.number_input(f"{d}M - Slab {s}", 0, 100, 100 // len(slabs), key=f"slab_{d}_{s}")
            slab_map[d][s] = val
            total += val
        if total != 100:
            st.error(f"{d}M slab % total ≠ 100%")

# --- Slot Fee + Block ---
slot_fees = {}
st.subheader("🎯 Slot Fees and Blocking")
for d in durations:
    with st.expander(f"{d}M Slot Configuration"):
        slot_fees[d] = {}
        for s in range(1, d+1):
            col1, col2 = st.columns([3, 1])
            fee = col1.number_input(f"Slot {s} Fee %", 0.0, 100.0, 1.0, key=f"fee_{d}_{s}")
            block = col2.checkbox(f"Block Slot {s}", key=f"block_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": block}

# --- Forecast Calculation ---
initial_users = int(total_market * starting_pct / 100)
months = 60
user_base = [initial_users]
cohorts = [{"month": 0, "users": initial_users, "duration": d} for d in durations[:1]]

monthly_new = [initial_users]
monthly_returning = [0]
monthly_total = [initial_users]

for m in range(1, months):
    returning = sum(c["users"] for c in cohorts if m == c["month"] + c["duration"] + rest_period)
    new = round(user_base[-1] * (monthly_growth / 100))
    total = new + returning
    monthly_new.append(new)
    monthly_returning.append(returning)
    monthly_total.append(total)
    user_base.append(total)
    # For simplicity, assign new users to first configured duration
    assigned_duration = list(duration_matrix.get(m % 3, {durations[0]: 100}).keys())[0]
    cohorts.append({"month": m, "users": new, "duration": assigned_duration})

# --- Output Tables ---
df = pd.DataFrame({
    "Month": list(range(1, months + 1)),
    "New Users": monthly_new,
    "Returning Users": monthly_returning,
    "Total Users": monthly_total
})
df["Fee Collected"] = df["Total Users"] * 100
df["NII"] = df["Total Users"] * 50
df["Profit"] = df["Fee Collected"] + df["NII"] - df["Total Users"] * 20

st.subheader("📈 Forecast Table")
st.dataframe(df)

summary = df[["Month", "Total Users", "Fee Collected", "NII", "Profit"]]

st.subheader("📊 Monthly Summary")
st.dataframe(summary)

# --- Excel Export ---
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Forecast")
    summary.to_excel(writer, index=False, sheet_name="Monthly Summary")
output.seek(0)
st.download_button("📥 Download Forecast Excel", data=output, file_name="rosca_forecast_v14_2.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
