import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("📊 ROSCA Forecast App v15.1 – Full Lifecycle with Rejoining")

# Sidebar Config
with st.sidebar:
    st.header("TAM & Growth Settings")
    total_market = st.number_input("Total Market Size", value=20000000)
    tam_pct = st.slider("TAM % of Market", 1, 100, 10)
    start_pct = st.slider("Starting TAM %", 1, 100, 10)
    monthly_growth = st.number_input("Monthly Growth Rate (%)", value=2.0)
    annual_growth = st.number_input("Annual TAM Growth (%)", value=5.0)
    rest_period = st.number_input("Rest Period (months)", min_value=0, value=1)
    kibor = st.number_input("KIBOR (%)", value=11.0)
    spread = st.number_input("Spread (%)", value=5.0)
    default_rate = st.number_input("Default Rate (%)", value=1.0)
    penalty_pct = st.number_input("Pre-Payout Penalty Refund (%)", value=10.0)

# Yearly Duration Share
st.subheader("📅 Yearly Duration Allocation")
yearly_duration_share = {}
for y in range(1, 6):
    with st.expander(f"Year {y} Duration %"):
        yearly_duration_share[y] = {}
        total = 0
        for d in [3, 4, 5, 6, 8, 10]:
            val = st.number_input(f"{d}M – Year {y}", 0, 100, key=f"dur_{y}_{d}")
            yearly_duration_share[y][d] = val
            total += val
        if total != 100:
            st.error(f"Year {y} ≠ 100%")

# Slab Distribution
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
slab_map = {}
st.subheader("💰 Slab Distribution")
for d in [3, 4, 5, 6, 8, 10]:
    with st.expander(f"{d}M Slabs"):
        slab_map[d] = {}
        total = 0
        for s in slabs:
            val = st.number_input(f"Slab {s}", 0, 100, 0, key=f"slab_{d}_{s}")
            slab_map[d][s] = val
            total += val
        if total != 100:
            st.error(f"{d}M ≠ 100%")

# Slot Fees
slot_fees = {}
st.subheader("🎯 Slot Fees and Blocking")
for d in [3, 4, 5, 6, 8, 10]:
    with st.expander(f"{d}M Slots"):
        slot_fees[d] = {}
        for s in range(1, d + 1):
            col1, col2 = st.columns([3, 1])
            fee = col1.number_input(f"Slot {s} Fee %", 0.0, 100.0, 1.0, key=f"fee_{d}_{s}")
            block = col2.checkbox("Block", key=f"block_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": block}

# Initialize
months = 60
initial_tam = int(total_market * tam_pct / 100)
tam_series = [initial_tam]
user_base = [int(initial_tam * start_pct / 100)]
rejoin_tracker = {}
cohort_log = []
forecast = []
deposit_log = []
default_log = []

# TAM Growth Logic
for m in range(1, months):
    if m % 12 == 0:
        tam_series.append(int(tam_series[-1] * (1 + annual_growth / 100)))
    else:
        tam_series.append(tam_series[-1])
    growth = int(user_base[-1] * monthly_growth / 100)
    user_base.append(user_base[-1] + growth)

# Forecast Loop
for m in range(months):
    year = m // 12 + 1
    month_users = user_base[m]

    # Rejoining Logic
    rejoining_users = rejoin_tracker.get(m, 0)
    total_users = month_users + rejoining_users

    # Duration Split
    durations = yearly_duration_share[year]
    for d, dur_pct in durations.items():
        dur_users = int(total_users * dur_pct / 100)

        # Slab Split
        for slab, slab_pct in slab_map[d].items():
            slab_users = int(dur_users * slab_pct / 100)

            # Slot Loop
            for s, meta in slot_fees[d].items():
                if meta["blocked"]:
                    continue
                fee_pct = meta["fee"]
                deposit = slab * d
                fee_amt = deposit * (fee_pct / 100)
                nii_amt = deposit * ((kibor + spread) / 100 / 12)

                # Defaults
                pre_def = int(slab_users * default_rate / 200)
                post_def = int(slab_users * default_rate / 200)
                pre_loss = pre_def * deposit * (1 - penalty_pct / 100)
                post_loss = post_def * deposit
                profit = fee_amt * slab_users + nii_amt * slab_users - pre_loss - post_loss

                forecast.append({
                    "Month": m + 1,
                    "Year": year,
                    "Duration": d,
                    "Slab": slab,
                    "Slot": s,
                    "New Users": month_users,
                    "Rejoining Users": rejoining_users,
                    "Active Users": slab_users,
                    "Deposit/User": deposit,
                    "Fee %": fee_pct,
                    "Fee Collected": fee_amt * slab_users,
                    "NII": nii_amt * slab_users,
                    "Profit": profit
                })

                # Cohort Lifecycle
                rejoin_month = m + d + rest_period
                if rejoin_month < months:
                    rejoin_tracker[rejoin_month] = rejoin_tracker.get(rejoin_month, 0) + slab_users
                cohort_log.append({
                    "Start": m + 1,
                    "Duration": d,
                    "Rest": rest_period,
                    "Rejoin": rejoin_month + 1,
                    "Users": slab_users
                })

                deposit_log.append({
                    "Month": m + 1,
                    "Users": slab_users,
                    "Held": slab_users * deposit,
                    "NII Earned": nii_amt * slab_users
                })

                default_log.append({
                    "Month": m + 1,
                    "Users": slab_users,
                    "Pre Loss": pre_loss,
                    "Post Loss": post_loss,
                    "Total Loss": pre_loss + post_loss
                })

# DataFrames
df = pd.DataFrame(forecast)
monthly_summary = df.groupby("Month")[["Active Users", "Fee Collected", "NII", "Profit"]].sum().reset_index()
yearly_summary = df.groupby("Year")[["Active Users", "Fee Collected", "NII", "Profit"]].sum().reset_index()
df_deposit = pd.DataFrame(deposit_log)
df_default = pd.DataFrame(default_log)
df_lifecycle = pd.DataFrame(cohort_log)

# Display Tables
st.subheader("📈 Forecast Table")
st.dataframe(df)
st.subheader("📊 Monthly Summary")
st.dataframe(monthly_summary)
st.subheader("📆 Yearly Summary")
st.dataframe(yearly_summary)
st.subheader("🏦 Deposit Log")
st.dataframe(df_deposit)
st.subheader("🚫 Default Summary")
st.dataframe(df_default)
st.subheader("♻️ User Lifecycle Log")
st.dataframe(df_lifecycle)

# Excel Export
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Forecast")
    monthly_summary.to_excel(writer, index=False, sheet_name="Monthly Summary")
    yearly_summary.to_excel(writer, index=False, sheet_name="Yearly Summary")
    df_deposit.to_excel(writer, index=False, sheet_name="Deposit Log")
    df_default.to_excel(writer, index=False, sheet_name="Default Log")
    df_lifecycle.to_excel(writer, index=False, sheet_name="Lifecycle Log")
output.seek(0)
st.download_button("📥 Download Excel", data=output, file_name="rosca_forecast_v15_1.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
