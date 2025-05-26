import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt

# === SCENARIO & UI SETUP ===
st.set_page_config(layout="wide")
st.title("📊 ROSCA Forecast App v15 – Full Implementation")

scenarios = []
scenario_count = st.sidebar.number_input("Number of Scenarios", min_value=1, max_value=3, value=1)

for i in range(scenario_count):
    with st.sidebar.expander(f"Scenario {i+1} Settings"):
        name = st.text_input(f"Scenario Name {i+1}", value=f"Scenario {i+1}", key=f"name_{i}")
        total_market = st.number_input("Total Market Size", value=20000000, key=f"market_{i}")
        tam_pct = st.slider("TAM % of Market", 1, 100, 10, key=f"tam_pct_{i}")
        start_pct = st.slider("Starting TAM % (Month 1)", 1, 100, 10, key=f"start_pct_{i}")
        monthly_growth = st.number_input("Monthly Growth Rate (%)", value=2.0, key=f"growth_{i}")
        annual_growth = st.number_input("Annual TAM Growth (%)", value=5.0, key=f"annual_{i}")
        cap_tam = st.checkbox("Cap TAM Growth?", value=False, key=f"cap_toggle_{i}")

        scenarios.append({
            "name": name,
            "total_market": total_market,
            "tam_pct": tam_pct,
            "start_pct": start_pct,
            "monthly_growth": monthly_growth,
            "annual_growth": annual_growth,
            "cap_tam": cap_tam
        })

# === GLOBAL INPUTS ===
profit_split = st.sidebar.slider("Profit Share for Party A (%)", 0, 100, 50)
party_a_pct = profit_split / 100
party_b_pct = 1 - party_a_pct
kibor = st.sidebar.number_input("KIBOR (%)", value=11.0)
spread = st.sidebar.number_input("Spread (%)", value=5.0)
rest_period = st.sidebar.number_input("Rest Period (months)", value=1)
default_rate = st.sidebar.number_input("Default Rate (%)", value=1.0)
penalty_pct = st.sidebar.number_input("Pre-Payout Refund (%)", value=10.0)

# === DURATION/SLAB/SLOT CONFIGURATION ===
validation_messages = []
durations = st.multiselect("Select Durations (months)", [3, 4, 5, 6, 8, 10], default=[3, 4, 6])
yearly_duration_share = {}
slab_map = {}
slot_fees = {}

for y in range(1, 6):
    with st.expander(f"Year {y} Duration Share"):
        yearly_duration_share[y] = {}
        total_dur_share = 0
        for d in durations:
            val = st.slider(f"{d}M – Year {y}", 0, 100, 0, key=f"yds_{y}_{d}")
            yearly_duration_share[y][d] = val
            total_dur_share += val
        if total_dur_share != 100:
            validation_messages.append(f"⚠️ Year {y} duration share total is {total_dur_share}%. It must equal 100%.")

for d in durations:
    with st.expander(f"{d}M Slab Distribution"):
        slab_map[d] = {}
        total_slab_pct = 0
        for slab in [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]:
            val = st.slider(f"Slab {slab} – {d}M", 0, 100, 0, key=f"slab_{d}_{slab}")
            slab_map[d][slab] = val
            total_slab_pct += val
        if total_slab_pct != 100:
            validation_messages.append(f"⚠️ Slab distribution for {d}M totals {total_slab_pct}%. It must equal 100%.")

    with st.expander(f"{d}M Slot Fees & Blocking"):
        slot_fees[d] = {}
        for s in range(1, d + 1):
            fee = st.number_input(f"Slot {s} Fee %", 0.0, 100.0, 1.0, key=f"fee_{d}_{s}")
            blocked = st.checkbox(f"Block Slot {s}", key=f"block_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": blocked}

if validation_messages:
    for msg in validation_messages:
        st.warning(msg)
    st.stop()

# === RUN FORECAST FUNCTION ===
def run_forecast(config):
    months = 60
    initial_tam = int(config['total_market'] * config['tam_pct'] / 100)
    new_users = [int(initial_tam * config['start_pct'] / 100)]
    rejoin_tracker = {}
    rest_tracker = {}
    forecast, deposit_log, default_log, lifecycle = [], [], [], []
    TAM_used = new_users[0]
    TAM_current = initial_tam
    enforce_cap = config.get("cap_tam", False)

    for m in range(months):
        year = m // 12 + 1
        durations_this_year = yearly_duration_share[year]
        rejoining = rejoin_tracker.get(m, 0)
        resting = rest_tracker.get(m, 0)
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
                    nii_amt = deposit * ((config['kibor'] + config['spread']) / 100 / 12)
                    total = slab_users

                    from_rejoin = min(total, rejoining)
                    from_new = total - from_rejoin
                    rejoining -= from_rejoin

                    pre_def = int(total * config['default_rate'] / 200)
                    post_def = int(total * config['default_rate'] / 200)
                    pre_loss = pre_def * deposit * (1 - config['penalty_pct'] / 100)
                    post_loss = post_def * deposit
                    gross_income = fee_amt * total + nii_amt * total
                    loss_total = pre_loss + post_loss
                    profit = gross_income - loss_total
                    investment = total * deposit
                    forecast.append({"Month": m + 1, "Year": year, "Duration": d, "Slab": slab, "Slot": s,
                                     "Users": total, "Deposit/User": deposit, "Fee %": fee_pct,
                                     "Fee Collected": fee_amt * total, "NII": nii_amt * total,
                                     "Profit": profit, "Investment": investment})

                    deposit_log.append({"Month": m + 1, "Users": total, "Deposit": investment, "NII": nii_amt * total})
                    default_log.append({"Month": m + 1, "Year": year, "Pre": pre_def, "Post": post_def, "Loss": loss_total})
                    lifecycle.append({"Month": m + 1, "New Users": from_new, "Rejoining": from_rejoin,
                                      "Resting": resting, "Total Active": active_total})

                    rejoin_month = m + d + config['rest_period']
                    if rejoin_month < months:
                        rejoin_tracker[rejoin_month] = rejoin_tracker.get(rejoin_month, 0) + total

                    rest_month = m + d
                    if rest_month < months:
                        rest_tracker[rest_month] = rest_tracker.get(rest_month, 0) + total

        if m + 1 < months:
            growth_base = sum(new_users[:m+1]) + sum(v for k, v in rejoin_tracker.items() if k <= m)
            next_growth = int(growth_base * config['monthly_growth'] / 100)
            if enforce_cap and TAM_used + next_growth > TAM_current:
                next_growth = max(0, TAM_current - TAM_used)
            TAM_used += next_growth
            if (m + 1) in [12, 24, 36, 48]:
                TAM_current = int(TAM_current * (1 + config['annual_growth'] / 100))
            new_users.append(next_growth)

    return pd.DataFrame(forecast), pd.DataFrame(deposit_log), pd.DataFrame(default_log), pd.DataFrame(lifecycle)

# === RUN FORECAST PER SCENARIO ===
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    for scenario in scenarios:
        config = scenario.copy()
        config.update({"kibor": kibor, "spread": spread, "rest_period": rest_period,
                       "default_rate": default_rate, "penalty_pct": penalty_pct})
        df_forecast, df_deposit, df_default, df_lifecycle = run_forecast(config)

        st.subheader(f"📘 {scenario['name']} Forecast Table")
        st.dataframe(df_forecast)

        df_monthly_summary = df_forecast.groupby("Month")[["Users", "Deposit/User", "Fee Collected", "NII", "Profit"]].sum().reset_index()
        df_monthly_summary["Deposit Txns"] = df_forecast.groupby("Month")["Users"].sum().values
        df_monthly_summary["Payout Txns"] = df_forecast[df_forecast["Slot"] == df_forecast["Duration"]].groupby("Month")["Users"].sum().reindex(df_monthly_summary["Month"], fill_value=0).values
        df_monthly_summary["Total Txns"] = df_monthly_summary["Deposit Txns"] + df_monthly_summary["Payout Txns"]
        df_monthly_summary = df_monthly_summary.merge(df_default.groupby("Month")["Loss"].sum().reset_index(), on="Month", how="left")
        st.subheader("📊 Monthly Summary")
        st.dataframe(df_monthly_summary.reset_index(drop=True))

        df_yearly_summary = df_forecast.groupby("Year")[["Users", "Deposit/User", "Fee Collected", "NII", "Profit"]].sum().reset_index()
        df_yearly_summary["Deposit Txns"] = df_forecast.groupby("Year")["Users"].sum().values
        df_yearly_summary["Payout Txns"] = df_forecast[df_forecast["Slot"] == df_forecast["Duration"]].groupby("Year")["Users"].sum().reindex(df_yearly_summary["Year"], fill_value=0).values
        df_yearly_summary["Total Txns"] = df_yearly_summary["Deposit Txns"] + df_yearly_summary["Payout Txns"]
        df_yearly_summary = df_yearly_summary.merge(df_default.groupby("Year")["Loss"].sum().reset_index(), on="Year", how="left")
                st.subheader("📆 Yearly Summary")
        st.dataframe(df_yearly_summary.reset_index(drop=True))

        # Profit Share Breakdown
        df_profit_share = pd.DataFrame({
            "Year": df_yearly_summary["Year"],
            "Deposit": df_yearly_summary["Deposit/User"],
            "NII": df_yearly_summary["NII"],
            "Default": df_yearly_summary["Loss"],
            "Fee": df_yearly_summary["Fee Collected"],
            "Total Profit": df_yearly_summary["Profit"],
            "Part-A Profit Share": df_yearly_summary["Profit"] * party_a_pct,
            "Part-B Profit Share": df_yearly_summary["Profit"] * party_b_pct
        })
        st.subheader("💰 Profit Share Summary")
        st.dataframe(df_profit_share.reset_index(drop=True))

        df_forecast.to_excel(writer, index=False, sheet_name=f"{scenario['name'][:28]}_Forecast")
        df_deposit.to_excel(writer, index=False, sheet_name=f"{scenario['name'][:28]}_Deposit")
        df_default.to_excel(writer, index=False, sheet_name=f"{scenario['name'][:28]}_Defaults")
        df_lifecycle.to_excel(writer, index=False, sheet_name=f"{scenario['name'][:28]}_Lifecycle")

output.seek(0)
st.download_button("📥 Download Forecast Excel", data=output, file_name="rosca_forecast_export.xlsx")
