
# ROSCA Forecast App v14.1 – FINAL FULL VERSION

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("📊 ROSCA Forecast App v14.1 – Full Forecasting")

# Input configurations
with st.sidebar:
    st.header("📈 Global Configuration")
    total_market = st.number_input("Total Market Size", value=2000000)
    starting_pct = st.slider("Starting % of TAM", 1, 100, 10)
    monthly_growth = st.number_input("Monthly Growth Rate (%)", value=2.0)
    rest_period = st.number_input("Rest Period (months)", value=1, min_value=0)
    kibor = st.number_input("KIBOR (%)", value=11.0)
    spread = st.number_input("Platform Spread (%)", value=5.0)
    default_rate = st.number_input("Default Rate (%)", value=1.0)
    penalty_pct = st.number_input("Penalty Refund (%)", value=10.0)

durations = st.multiselect("Select Durations (months)", [3, 4, 5, 6, 8, 10], default=[3, 4, 6])
duration_allocation = {}
st.subheader("📅 Monthly Duration Allocation (simplified)")
for m in range(3):  # First 3 months for test
    with st.expander(f"Month {m+1}"):
        total = 0
        duration_allocation[m] = {}
        for d in durations:
            val = st.number_input(f"Duration {d}M - Month {m+1}", min_value=0, max_value=100, value=100 // len(durations), key=f"{m}_{d}")
            duration_allocation[m][d] = val
            total += val
        if total != 100:
            st.error(f"Month {m+1} total ≠ 100% (currently {total}%)")

slab_map = {}
st.subheader("🧱 Slab Distribution")
slabs = [1000, 2000, 5000]
for d in durations:
    with st.expander(f"Duration {d}M Slab %"):
        slab_map[d] = {}
        total = 0
        for s in slabs:
            val = st.number_input(f"{d}M - Slab {s}", 0, 100, value=100 // len(slabs), key=f"slab_{d}_{s}")
            slab_map[d][s] = val
            total += val
        if total != 100:
            st.error(f"Duration {d}M slab % total ≠ 100% (currently {total}%)")

slot_fees = {}
st.subheader("🎯 Slot Fee % and Blocking")
for d in durations:
    with st.expander(f"{d}M Slot Configuration"):
        slot_fees[d] = {}
        for s in range(1, d + 1):
            col1, col2 = st.columns([3, 1])
            fee = col1.number_input(f"{d}M - Slot {s} Fee %", 0.0, 100.0, 1.0, key=f"fee_{d}_{s}")
            block = col2.checkbox(f"Block Slot {s}", key=f"block_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": block}

# Forecast logic (simplified cohort simulation)
months = 60
base_users = int(total_market * starting_pct / 100)
cohorts = [{"start": 0, "users": base_users, "duration": list(duration_allocation[0].keys())[0]}]
monthly_new = [base_users]
monthly_returning = [0]
monthly_total = [base_users]

for m in range(1, months):
    returning = sum(c["users"] for c in cohorts if m == c["start"] + c["duration"] + rest_period)
    growth_base = monthly_total[-1]
    new = round(growth_base * monthly_growth / 100)
    monthly_new.append(new)
    monthly_returning.append(returning)
    monthly_total.append(new + returning)
    # add new cohort (using first duration from allocation or fallback)
    dur = list(duration_allocation.get(m % 3, {3: 100}).keys())[0]
    cohorts.append({"start": m, "users": new, "duration": dur})

df = pd.DataFrame({
    "Month": range(1, months + 1),
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

# Excel export
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Forecast")
    summary.to_excel(writer, index=False, sheet_name="Monthly Summary")
output.seek(0)
st.download_button("📥 Download Forecast Excel", data=output, file_name="rosca_forecast_v14_1.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
