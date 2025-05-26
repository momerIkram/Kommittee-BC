import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("📊 ROSCA Forecast App v15.6 – Multi-TAM with Slabs & Slot Fees")

# Step 1: Scenario Selection
scenario_count = st.sidebar.number_input("How many TAM scenarios?", min_value=1, max_value=5, value=2, step=1)

scenarios = []
for i in range(scenario_count):
    with st.sidebar.expander(f"Scenario {i+1} TAM Settings"):
        name = st.text_input(f"Scenario {i+1} Name", value=f"Scenario {i+1}", key=f"name_{i}")
        total_market = st.number_input("Total Market Size", value=20000000, key=f"market_{i}")
        tam_pct = st.slider("TAM % of Market", 1, 100, 10, key=f"tam_pct_{i}")
        start_pct = st.slider("Starting TAM % (Month 1)", 1, 100, 10, key=f"start_pct_{i}")
        monthly_growth = st.number_input("Monthly Growth Rate (%)", value=2.0, key=f"monthly_growth_{i}")
        annual_growth = st.number_input("Annual TAM Growth (%)", value=5.0, key=f"annual_growth_{i}")

        scenarios.append({
            "name": name,
            "total_market": total_market,
            "tam_pct": tam_pct,
            "start_pct": start_pct,
            "monthly_growth": monthly_growth,
            "annual_growth": annual_growth
        })

# Step 2: Shared Parameters
st.sidebar.header("📈 Shared Settings")
rest_period = st.sidebar.number_input("Rest Period (months)", min_value=0, value=1)
kibor = st.sidebar.number_input("KIBOR (%)", value=11.0)
spread = st.sidebar.number_input("Spread (%)", value=5.0)
default_rate = st.sidebar.number_input("Default Rate (%)", value=1.0)
penalty_pct = st.sidebar.number_input("Pre-Payout Refund (%)", value=10.0)

# Step 3: Annual Duration Allocation
st.subheader("📅 Annual Duration Share")
yearly_duration_share = {}
for y in range(1, 6):
    with st.expander(f"Year {y} Allocation"):
        yearly_duration_share[y] = {}
        total = 0
        for d in [3, 4, 5, 6, 8, 10]:
            val = st.number_input(f"{d}M – Year {y}", 0, 100, 0, key=f"dur_{y}_{d}")
            yearly_duration_share[y][d] = val
            total += val
        if total != 100:
            st.error(f"Year {y} total ≠ 100%")

# Step 4: Slab Distribution
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
slab_map = {}
st.subheader("💰 Slab Distribution Per Duration")
for d in [3, 4, 5, 6, 8, 10]:
    with st.expander(f"{d}M Slabs"):
        slab_map[d] = {}
        total = 0
        for s in slabs:
            val = st.number_input(f"Slab {s} – {d}M", 0, 100, 0, key=f"slab_{d}_{s}")
            slab_map[d][s] = val
            total += val
        if total != 100:
            st.error(f"{d}M slab total ≠ 100%")

# Step 5: Slot Fee and Blocking
slot_fees = {}
st.subheader("🎯 Slot Fees and Blocking")
for d in [3, 4, 5, 6, 8, 10]:
    with st.expander(f"{d}M Slot Fees"):
        slot_fees[d] = {}
        for s in range(1, d + 1):
            col1, col2 = st.columns([3, 1])
            fee = col1.number_input(f"Slot {s} Fee % – {d}M", 0.0, 100.0, 1.0, key=f"fee_{d}_{s}")
            block = col2.checkbox("Block", key=f"block_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": block}

# Step 6: Forecast per Scenario
def run_forecast(config):
    months = 60
    initial_tam = int(config['total_market'] * config['tam_pct'] / 100)
    tam_series = [initial_tam]
    new_users = [int(initial_tam * config['start_pct'] / 100)]
    rejoin_tracker = {}
    forecast = []

    for m in range(1, months):
        if m in [12, 24, 36, 48]:
            tam_series.append(int(tam_series[-1] * (1 + config['annual_growth'] / 100)))
        else:
            tam_series.append(tam_series[-1])

    for m in range(months):
        year = m // 12 + 1
        durations = yearly_duration_share[year]
        rejoining = rejoin_tracker.get(m, 0)
        current_new = new_users[m] if m < len(new_users) else 0
        active_total = current_new + rejoining

        for d, dur_pct in durations.items():
            dur_users = int(active_total * dur_pct / 100)
            for slab, slab_pct in slab_map[d].items():
                slab_users = int(dur_users * slab_pct / 100)
                for s, meta in slot_fees[d].items():
                    if meta['blocked']: continue
                    fee_pct = meta['fee']
                    deposit = slab * d
                    fee_amt = deposit * (fee_pct / 100)
                    nii_amt = deposit * ((kibor + spread) / 100 / 12)
                    total = slab_users

                    pre_def = int(total * default_rate / 200)
                    post_def = int(total * default_rate / 200)
                    pre_loss = pre_def * deposit * (1 - penalty_pct / 100)
                    post_loss = post_def * deposit
                    profit = fee_amt * total + nii_amt * total - pre_loss - post_loss

                    forecast.append({
                        "Month": m + 1,
                        "Year": year,
                        "Duration": d,
                        "Slab": slab,
                        "Slot": s,
                        "Users": total,
                        "Deposit/User": deposit,
                        "Fee %": fee_pct,
                        "Fee Collected": fee_amt * total,
                        "NII": nii_amt * total,
                        "Profit": profit
                    })

                    rejoin_month = m + d + rest_period
                    if rejoin_month < months:
                        rejoin_tracker[rejoin_month] = rejoin_tracker.get(rejoin_month, 0) + total

        if m + 1 < months:
            next_growth = int(active_total * config['monthly_growth'] / 100)
            new_users.append(next_growth)

    return pd.DataFrame(forecast)

# Run and display
results = {}
for scenario in scenarios:
    df = run_forecast(scenario)
    results[scenario['name']] = df
    st.subheader(f"📘 {scenario['name']} Forecast")
    st.dataframe(df)

# Excel Export
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    for name, df in results.items():
        df.to_excel(writer, index=False, sheet_name=name[:31])
output.seek(0)
st.download_button("📥 Download All Scenarios (Excel)", data=output, file_name="multi_tam_forecasts_v15_6.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
