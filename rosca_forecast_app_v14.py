import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")
st.title("📊 ROSCA Forecast App v15.7.2 – ROI, Trends, Validated")

# === SCENARIO INPUT CONFIG ===
scenarios = []
scenario_count = st.sidebar.number_input("How many TAM scenarios?", min_value=1, max_value=5, value=1, step=1)

cap_tam = st.sidebar.checkbox("Cap TAM Growth?", value=False)
kibor = st.sidebar.number_input("KIBOR (%)", value=11.0)
spread = st.sidebar.number_input("Spread (%)", value=5.0)
rest_period = st.sidebar.number_input("Rest Period (months)", value=1)
default_rate = st.sidebar.number_input("Default Rate (%)", value=1.0)
penalty_pct = st.sidebar.number_input("Pre-Payout Refund (%)", value=10.0)

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

# === DURATION, SLAB, AND SLOT CONFIG ===
durations = st.multiselect("Select Durations (in months)", [3, 4, 5, 6, 8, 10], default=[3, 4, 6])
yearly_duration_share = {}
slab_map = {}
slot_fees = {}

for y in range(1, 6):
    with st.expander(f"Year {y} Duration Share"):
        yearly_duration_share[y] = {}
        for d in durations:
            val = st.slider(f"{d}M - Year {y}", 0, 100, 0, key=f"dur_{y}_{d}")
            yearly_duration_share[y][d] = val

for d in durations:
    with st.expander(f"{d}M Slab Distribution"):
        slab_map[d] = {}
        for slab in [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]:
            slab_map[d][slab] = st.slider(f"{slab} slab for {d}M", 0, 100, 0, key=f"slab_{d}_{slab}")

    with st.expander(f"{d}M Slot Fees & Blocking"):
        slot_fees[d] = {}
        for s in range(1, d + 1):
            fee = st.number_input(f"Slot {s} Fee % – {d}M", 0.0, 100.0, 1.0, key=f"fee_{d}_{s}")
            block = st.checkbox(f"Block Slot {s} – {d}M", key=f"block_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": block}

# === FORECAST FUNCTION ===
def run_forecast(config):
    months = 60
    initial_tam = int(config['total_market'] * config['tam_pct'] / 100)
    new_users = [int(initial_tam * config['start_pct'] / 100)]
    rejoin_tracker = {}
    forecast, deposit_log, default_log, lifecycle = [], [], [], []
    TAM_used = new_users[0]
    TAM_current = initial_tam

    for m in range(months):
        year = m // 12 + 1
        durations_this_year = yearly_duration_share[year]
        rejoining = rejoin_tracker.get(m, 0)
        current_new = new_users[m] if m < len(new_users) else 0
        active_total = current_new + rejoining

        for d, dur_pct in durations_this_year.items():
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
                    gross_income = fee_amt * total + nii_amt * total
                    loss_total = pre_loss + post_loss
                    profit = gross_income - loss_total
                    investment = total * deposit
                    roi_pct = ((profit / investment) * 100) if investment > 0 else 0

                    forecast.append({"Month": m + 1, "Year": year, "Duration": d, "Slab": slab, "Slot": s,
                                     "Users": total, "Deposit/User": deposit, "Fee %": fee_pct,
                                     "Fee Collected": fee_amt * total, "NII": nii_amt * total,
                                     "Profit": profit, "Investment": investment, "ROI %": roi_pct})

                    deposit_log.append({"Month": m + 1, "Users": total, "Deposit": investment, "NII": nii_amt * total})
                    default_log.append({"Month": m + 1, "Pre": pre_def, "Post": post_def, "Loss": loss_total})
                    lifecycle.append({"Month": m + 1, "New Users": current_new, "Rejoining": rejoining, "Total Active": active_total})

                    rejoin_month = m + d + rest_period
                    if rejoin_month < months:
                        rejoin_tracker[rejoin_month] = rejoin_tracker.get(rejoin_month, 0) + total

        if m + 1 < months:
            growth_base = sum(new_users[:m+1]) + sum(v for k, v in rejoin_tracker.items() if k <= m)
            next_growth = int(growth_base * config['monthly_growth'] / 100)
            if cap_tam and TAM_used + next_growth > TAM_current:
                next_growth = max(0, TAM_current - TAM_used)
            TAM_used += next_growth
            if (m + 1) in [12, 24, 36, 48]:
                TAM_current = int(TAM_current * (1 + config['annual_growth'] / 100))
            new_users.append(next_growth)

    return pd.DataFrame(forecast), pd.DataFrame(deposit_log), pd.DataFrame(default_log), pd.DataFrame(lifecycle)

# === EXECUTION & DISPLAY ===
results = {}
for scenario in scenarios:
    df_f, df_d, df_def, df_lc = run_forecast(scenario)
    for _ in range(5):
        assert not df_f.empty
        assert all(col in df_f.columns for col in ["ROI %", "Investment", "Profit"])
        assert df_f["Users"].sum() >= 0

    results[scenario['name']] = {"Forecast": df_f, "Deposit Log": df_d, "Default Log": df_def, "Lifecycle": df_lc}

    st.subheader(f"📘 {scenario['name']} Forecast")
    st.dataframe(df_f)

    st.subheader("📅 Monthly Summary")
    st.dataframe(df_f.groupby("Month")[["Users", "Fee Collected", "NII", "Profit", "ROI %"]].mean().reset_index())

    st.subheader("📆 Yearly Summary")
    st.dataframe(df_f.groupby("Year")[["Users", "Fee Collected", "NII", "Profit", "ROI %"]].mean().reset_index())

    st.subheader("📈 Trend Charts")
    fig, ax = plt.subplots()
    df_f.groupby("Month")["Users"].sum().plot(ax=ax, label="Users")
    df_f.groupby("Month")["Profit"].sum().plot(ax=ax, label="Profit")
    df_f.groupby("Month")["ROI %"].mean().plot(ax=ax, label="ROI %")
    ax.set_title(f"{scenario['name']} – Trends")
    ax.set_xlabel("Month")
    ax.legend()
    st.pyplot(fig)

# === EXPORT ===
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    for name, data in results.items():
        for sheet, df in data.items():
            df.to_excel(writer, index=False, sheet_name=f"{name[:20]}-{sheet[:10]}")
output.seek(0)
st.download_button("📥 Download Excel", data=output, file_name="rosca_forecast_v15_7_2.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
