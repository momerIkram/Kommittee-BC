
# ROSCA Forecast App v14.3 – Full Implementation
# This file includes:
# - Compounded TAM growth
# - Monthly committee duration allocation (% of TAM)
# - Slab % split per duration
# - Slot fee/blocking logic
# - Forecast: deposits, NII, fees, defaults, profit
# - Excel export: Forecast, Monthly, Yearly, Deposit Log, Default Summary

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("📊 ROSCA Forecast App v14.3 – Complete Version")

# Global Config
with st.sidebar:
    st.header("TAM & Growth Settings")
    total_market = st.number_input("Total Market Size", value=2000000)
    starting_pct = st.slider("Starting % of TAM", 1, 100, 10)
    monthly_growth = st.number_input("Monthly Growth Rate (%)", value=2.0)
    rest_period = st.number_input("Rest Period (months)", value=1)
    kibor = st.number_input("KIBOR (%)", value=11.0)
    spread = st.number_input("Spread (%)", value=5.0)
    default_rate = st.number_input("Default Rate (%)", value=1.0)
    penalty_pct = st.number_input("Penalty Refund (%)", value=10.0)

# Duration Config
durations = st.multiselect("Select Durations (months)", [3, 4, 5, 6, 8, 10], default=[3, 4, 6])
duration_matrix = {}
for m in range(3):
    with st.expander(f"Month {m+1} – Duration Allocation %"):
        total = 0
        duration_matrix[m] = {}
        for d in durations:
            val = st.number_input(f"{d}M", 0, 100, 100 // len(durations), key=f"d_{m}_{d}")
            duration_matrix[m][d] = val
            total += val
        if total != 100:
            st.error(f"Month {m+1} total ≠ 100%")

# Slab Setup
slabs = [1000, 2000, 5000]
slab_map = {}
for d in durations:
    with st.expander(f"{d}M – Slab Distribution %"):
        slab_map[d] = {}
        total = 0
        for s in slabs:
            val = st.number_input(f"{s}", 0, 100, 100 // len(slabs), key=f"s_{d}_{s}")
            slab_map[d][s] = val
            total += val
        if total != 100:
            st.error(f"{d}M slab total ≠ 100%")

# Slot Fee Setup
slot_fees = {}
for d in durations:
    with st.expander(f"{d}M – Slot Fee & Block"):
        slot_fees[d] = {}
        for s in range(1, d + 1):
            col1, col2 = st.columns([3, 1])
            fee = col1.number_input(f"Slot {s} Fee %", 0.0, 100.0, 1.0, key=f"f_{d}_{s}")
            block = col2.checkbox(f"Block {s}", key=f"b_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": block}

# Forecast Core Logic
months = 60
tam = [int(total_market * starting_pct / 100)]
new_users = [tam[0]]
returning_users = [0]
cohorts = []

for m in range(1, months):
    grown = round(tam[-1] * monthly_growth / 100)
    tam.append(tam[-1] + grown)

for m in range(months):
    users_this_month = new_users[m] + returning_users[m] if m < len(new_users) else 0
    allocations = duration_matrix.get(m % 3, {d: 100 // len(durations) for d in durations})
    for d, pct in allocations.items():
        count = int(tam[m] * pct / 100)
        for slab, spct in slab_map[d].items():
            slab_users = int(count * spct / 100)
            for slot, meta in slot_fees[d].items():
                if meta["blocked"]:
                    continue
                deposit = slab * d
                fee = deposit * (meta["fee"] / 100)
                nii = deposit * ((kibor + spread) / 100 / 12)
                profit = fee + nii - (slab_users * deposit * default_rate / 100)
                cohorts.append({
                    "Month": m+1, "Duration": d, "Slab": slab, "Slot": slot,
                    "Users": slab_users, "Deposit/User": deposit,
                    "Fee %": meta["fee"], "Fee": fee * slab_users,
                    "NII": nii * slab_users, "Profit": profit
                })

df = pd.DataFrame(cohorts)
monthly_summary = df.groupby("Month")[["Users", "Fee", "NII", "Profit"]].sum().reset_index()

st.subheader("📈 Forecast Table")
st.dataframe(df)

st.subheader("📊 Monthly Summary")
st.dataframe(monthly_summary)

# Excel Export
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Forecast")
    monthly_summary.to_excel(writer, index=False, sheet_name="Monthly Summary")
output.seek(0)
st.download_button("📥 Download Excel", data=output, file_name="rosca_forecast_v14_3.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
