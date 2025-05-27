import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt

# === SCENARIO & UI SETUP ===
st.set_page_config(layout="wide")
st.title("📊BACHAT-KOMMITTEE Business Case/Pricing")

scenarios = []
scenario_count = st.sidebar.number_input("Number of Scenarios", min_value=1, max_value=3, value=1)

for i in range(scenario_count):
    with st.sidebar.expander(f"Scenario {i+1} Settings"):
        name = st.text_input(f"Scenario Name {i+1}", value=f"Scenario {i+1}", key=f"name_{i}")
        total_market = st.number_input("Total Market Size", value=20000000, key=f"market_{i}")
        tam_pct = st.number_input("TAM % of Market", min_value=1, max_value=100, value=10, key=f"tam_pct_{i}")
        start_pct = st.number_input("Starting TAM % (Month 1)", min_value=1, max_value=100, value=10, key=f"start_pct_{i}")
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
collection_day = st.sidebar.number_input("Collection Day of Month", min_value=1, max_value=28, value=1)
payout_day = st.sidebar.number_input("Payout Day of Month", min_value=1, max_value=28, value=20)
profit_split = st.sidebar.number_input("Profit Share for Party A (%)", min_value=0, max_value=100, value=50)
party_a_pct = profit_split / 100
party_b_pct = 1 - party_a_pct
kibor = st.sidebar.number_input("KIBOR (%)", value=11.0)
spread = st.sidebar.number_input("Spread (%)", value=5.0)
rest_period = st.sidebar.number_input("Rest Period (months)", value=1)
default_rate = st.sidebar.number_input("Default Rate (%)", value=1.0)
default_pre_pct = st.sidebar.number_input("Pre-Payout Default %", min_value=0, max_value=100, value=50)
default_post_pct = 100 - default_pre_pct
penalty_pct = st.sidebar.number_input("Pre-Payout Refund (%)", value=10.0)

# === DURATION/SLAB/SLOT CONFIGURATION ===
validation_messages = []
durations = st.multiselect("Select Durations (months)", [3, 4, 5, 6, 8, 10], default=[3, 4, 6])
yearly_duration_share = {}
slab_map = {}
slot_fees = {}
slot_distribution = {}

for y in range(1, 6):
    with st.expander(f"Year {y} Duration Share"):
        yearly_duration_share[y] = {}
        total_dur_share = 0
        for d in durations:
            d = int(d)
            key = f"yds_{y}_{d}"
            val = st.number_input(f"{d}M – Year {y} (%)", min_value=0, max_value=100, value=0, step=1, key=key)
            yearly_duration_share[y][d] = val
            total_dur_share += val
        if total_dur_share > 100:
            validation_messages.append(f"⚠️ Year {y} duration share total is {total_dur_share}%. It must not exceed 100%.")

for d in durations:
    d = int(d)
    with st.expander(f"{d}M Slab Distribution"):
        slab_map[d] = {}
        total_slab_pct = 0
        for slab in [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]:
            key = f"slab_{d}_{slab}"
            val = st.number_input(f"Slab {slab} – {d}M (%)", min_value=0, max_value=100, value=0, step=1, key=key)
            slab_map[d][slab] = val
            total_slab_pct += val
        if total_slab_pct > 100:
            validation_messages.append(f"⚠️ Slab distribution for {d}M totals {total_slab_pct}%. It must not exceed 100%.")

    with st.expander(f"{d}M Slot Fees & Blocking"):
        if d not in slot_fees:
            slot_fees[d] = {}
        if d not in slot_distribution:
            slot_distribution[d] = {}
        for s in range(1, d + 1):
            d_int, s_int = int(d), int(s)
            deposit_per_user = d * 1000
            avg_nii = deposit_per_user * ((kibor + spread) / 100 / 12) * sum(range(1, d + 1)) / d
            pre_def_loss = deposit_per_user * default_rate * (default_pre_pct / 100) * (1 - penalty_pct / 100)
            post_def_loss = deposit_per_user * default_rate * (default_post_pct / 100)
            avg_loss = (pre_def_loss + post_def_loss) / 100
            suggested_fee_pct = ((avg_nii + avg_loss) / deposit_per_user) * 100

            key_fee = f"fee_{d}_{s}"
            key_block = f"block_{d}_{s}"
            key_pct = f"slot_pct_d{d}_s{s}"

            fee = st.number_input(f"Slot {s} Fee %", 0.0, 100.0, 1.0, key=key_fee, help=f"Suggested ≥ {suggested_fee_pct:.2f}%")
            blocked = st.checkbox(f"Block Slot {s}", key=key_block)
            slot_pct = st.number_input(
                label=f"Slot {s} % of Users (Duration {d}M)",
                min_value=0, max_value=100, value=0,
                step=1,
                key=key_pct
            )

            slot_fees[d][s] = {"fee": fee, "blocked": blocked}
            slot_distribution[d][s] = slot_pct

for d in durations:
    d = int(d)
    total_slot_pct = sum(slot_distribution[d].values())
    if total_slot_pct > 100:
        validation_messages.append(f"⚠️ Slot distribution for {d}M totals {total_slot_pct}%. It must not exceed 100%.")

if validation_messages:
    for msg in validation_messages:
        st.warning(msg)
    st.stop()

# === FORECASTING LOGIC ===
def run_forecast(config):
    months = 60
    initial_tam = int(config['total_market'] * config['tam_pct'] / 100)
    new_users = [int(initial_tam * config['start_pct'] / 100)]
    rejoin_tracker, rest_tracker = {}, {}
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
                    held_days = max(payout_day - collection_day, 1)
                    nii_amt = deposit * ((config['kibor'] + config['spread']) / 100 / 365) * held_days
                    slot_pct = slot_distribution[d].get(s, 0)
                    total = int(slab_users * slot_pct / 100)

                    from_rejoin = min(total, rejoining)
                    from_new = total - from_rejoin
                    rejoining -= from_rejoin

                    pre_def = int(total * config['default_rate'] * default_pre_pct / 10000)
                    post_def = int(total * config['default_rate'] * default_post_pct / 10000)
                    pre_loss = pre_def * deposit * (1 - config['penalty_pct'] / 100)
                    post_loss = post_def * deposit
                    gross_income = fee_amt * total + nii_amt * total
                    loss_total = pre_loss + post_loss
                    profit = gross_income - loss_total
                    investment = total * deposit

                    forecast.append({"Month": m + 1, "Year": year, "Duration": d, "Slab": slab, "Slot": s,
                                     "Users": total, "Deposit/User": deposit, "Fee %": fee_pct,
                                     "Fee Collected": fee_amt * total, "NII": nii_amt * total,
                                     "Profit": profit, "Held Capital": investment,
                                     "Payout Day": payout_day, "Cash In": total * deposit,
                                     "Cash Out": total * deposit if s == d else 0})

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

# === EXPORT AND DISPLAY ===
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    for scenario in scenarios:
        config = scenario.copy()
        config.update({"kibor": kibor, "spread": spread, "rest_period": rest_period,
                       "default_rate": default_rate, "penalty_pct": penalty_pct})
        df_forecast, df_deposit, df_default, df_lifecycle = run_forecast(config)

        st.subheader(f"📘 {scenario['name']} Forecast Table")
        st.dataframe(df_forecast.style.format("{:,.0f}"))

        # Monthly Summary
        df_monthly_summary = df_forecast.groupby("Month")[["Users", "Fee Collected", "NII", "Profit", "Cash In", "Cash Out"]].sum().reset_index()
        df_monthly_summary["Deposit"] = df_monthly_summary["Cash In"]
        df_monthly_summary["Payout Txns"] = df_forecast[df_forecast["Slot"] == df_forecast["Duration"]].groupby("Month")["Users"].sum().reindex(df_monthly_summary["Month"], fill_value=0).values
        df_monthly_summary["Total Txns"] = df_monthly_summary["Users"] + df_monthly_summary["Payout Txns"]
        df_monthly_summary = df_monthly_summary.merge(df_default.groupby("Month")["Loss"].sum().reset_index(), on="Month", how="left")
        st.subheader("📊 Monthly Summary")
        st.dataframe(df_monthly_summary.style.format("{:,.0f}"))

        # Yearly Summary
        df_yearly_summary = df_forecast.groupby("Year")[["Users", "Fee Collected", "NII", "Profit", "Cash In", "Cash Out"]].sum().reset_index()
        df_yearly_summary["Deposit"] = df_yearly_summary["Cash In"]
        df_yearly_summary["Payout Txns"] = df_forecast[df_forecast["Slot"] == df_forecast["Duration"]].groupby("Year")["Users"].sum().reindex(df_yearly_summary["Year"], fill_value=0).values
        df_yearly_summary["Total Txns"] = df_yearly_summary["Users"] + df_yearly_summary["Payout Txns"]
        df_yearly_summary = df_yearly_summary.merge(df_default.groupby("Year")["Loss"].sum().reset_index(), on="Year", how="left")

        df_profit_share = pd.DataFrame({
            "Year": df_yearly_summary["Year"],
            "Deposit": df_yearly_summary["Deposit"],
            "NII": df_yearly_summary["NII"],
            "Default": df_yearly_summary["Loss"],
            "Fee": df_yearly_summary["Fee Collected"],
            "Total Profit": df_yearly_summary["Profit"],
            "Part-A Profit Share": df_yearly_summary["Profit"] * party_a_pct,
            "Part-B Profit Share": df_yearly_summary["Profit"] * party_b_pct
        })
        st.subheader("💰 Profit Share Summary")
        st.dataframe(df_profit_share.style.format("{:,.0f}"))

        
        st.subheader("📆 Yearly Summary")
        st.dataframe(df_yearly_summary.style.format("{:,.0f}"))

        df_forecast.to_excel(writer, index=False, sheet_name=f"{scenario['name'][:28]}_Forecast")
        df_deposit.to_excel(writer, index=False, sheet_name=f"{scenario['name'][:28]}_Deposit")
        df_default.to_excel(writer, index=False, sheet_name=f"{scenario['name'][:28]}_Defaults")
        df_lifecycle.to_excel(writer, index=False, sheet_name=f"{scenario['name'][:28]}_Lifecycle")

output.seek(0)
st.download_button("📥 Download Forecast Excel", data=output, file_name="rosca_forecast_export.xlsx")

# === 📊 VISUAL CHARTS ===
# Simulated 60-month summary DataFrame
df_chart = pd.DataFrame({
    "Month": list(range(1, 61)),
    "Active Pools": np.random.randint(100, 1000, 60),
    "Deposits": np.random.randint(1000000, 10000000, 60),
    "Total Users": np.random.randint(500, 1500, 60),
    "Profit": np.random.randint(100000, 1000000, 60),
    "Year": [(i // 12) + 1 for i in range(60)]
})

# Chart 1: Active Pools + Deposits (Monthly)
st.subheader("📊 Chart 1: Active Pools vs Total Deposits (Monthly)")
fig1, ax1 = plt.subplots(figsize=(6, 2), dpi=100, facecolor='#f9f9f9')
fig1.patch.set_facecolor('#f8f9fa')
ax1.set_facecolor('#ffffff')
ax2 = ax1.twinx()
ax1.bar(df_chart["Month"], df_chart["Active Pools"], color="skyblue", label="Active Pools", edgecolor="#888", linewidth=0.5, zorder=3)
ax2.plot(df_chart["Month"], df_chart["Deposits"], color="green", label="Deposits", linewidth=2.5, marker='o', zorder=4)
ax1.set_ylabel("Active Pools")
ax2.set_ylabel("Deposits")
ax2.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
ax1.tick_params(axis='x', labelsize=6, rotation=0)
fig1.tight_layout()
fig1.patch.set_linewidth(1.5)
fig1.patch.set_edgecolor("#ccc")
fig1.legend(loc="lower center", bbox_to_anchor=(0.5, -0.3), ncol=2)
st.pyplot(fig1)

# Chart 2: Total Users + Profit (Monthly)
st.subheader("📊 Chart 2: Total Users vs Total Profit (Monthly)")
fig2, ax3 = plt.subplots(figsize=(6, 2), dpi=100, facecolor='#f9f9f9')
fig2.patch.set_facecolor('#f8f9fa')
ax3.set_facecolor('#ffffff')
ax4 = ax3.twinx()
max_users = df_chart["Total Users"].max()
ax3.bar(df_chart["Month"], df_chart["Total Users"], color="cornflowerblue", label="Total Users", edgecolor="#777", linewidth=0.5, zorder=3)
ax3.set_ylim(0, max(1000, max_users * 1.1))
ax3.set_ylim(0, df_chart["Total Users"].max() * 1.1)
ax4.plot(df_chart["Month"], df_chart["Profit"], color="darkgreen", label="Profit", linewidth=2.5, marker='o', zorder=4)
ax3.set_ylabel("Total Users")
ax4.set_ylabel("Profit")
ax4.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
ax3.tick_params(axis='x', labelsize=6, rotation=0)
fig2.tight_layout()
fig2.patch.set_linewidth(1.5)
fig2.patch.set_edgecolor("#ccc")
fig2.legend(loc="lower center", bbox_to_anchor=(0.5, -0.3), ncol=2)
st.pyplot(fig2)

# CHARTS FOR YEARS 1 TO 5
df_yearly_chart = df_chart.groupby("Year")[["Active Pools", "Deposits", "Total Users", "Profit"]].sum().reset_index()
df_yearly_chart["Year"] = df_yearly_chart["Year"].astype(str)

# Chart 3: Active Pools + Deposits (Yearly)
st.subheader("📊 Chart 3: Active Pools vs Total Deposits (Yearly)")
fig3, ax5 = plt.subplots(figsize=(6, 2), dpi=100, facecolor='#f9f9f9')
fig3.patch.set_facecolor('#f8f9fa')
ax5.set_facecolor('#ffffff')
ax6 = ax5.twinx()
ax5.bar(df_yearly_chart["Year"], df_yearly_chart["Active Pools"], color="lightblue", label="Active Pools", edgecolor="#777", linewidth=0.5, zorder=3)
ax6.plot(df_yearly_chart["Year"], df_yearly_chart["Deposits"], color="green", marker='o', label="Deposits", linewidth=2.5, zorder=4)
ax5.set_ylabel("Active Pools")
ax6.set_ylabel("Deposits")
ax6.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
fig3.tight_layout()
fig3.patch.set_linewidth(1.5)
fig3.patch.set_edgecolor("#ccc")
fig3.legend(loc="lower center", bbox_to_anchor=(0.5, -0.3), ncol=2)
st.pyplot(fig3)

# Chart 4: Total Users + Profit (Yearly)
st.subheader("📊 Chart 4: Total Users vs Total Profit (Yearly)")
fig4, ax7 = plt.subplots(figsize=(6, 2), dpi=100, facecolor='#f9f9f9')
fig4.patch.set_facecolor('#f8f9fa')
ax7.set_facecolor('#ffffff')
ax8 = ax7.twinx()
ax7.bar(df_yearly_chart["Year"], df_yearly_chart["Total Users"], color="cornflowerblue", label="Total Users", edgecolor="#777", linewidth=0.5, zorder=3)
ax8.plot(df_yearly_chart["Year"], df_yearly_chart["Profit"], color="darkgreen", marker='o', label="Profit", linewidth=2.5, zorder=4)
ax7.set_ylabel("Total Users")
ax8.set_ylabel("Profit")
ax8.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
fig4.tight_layout()
fig4.patch.set_linewidth(1.5)
fig4.patch.set_edgecolor("#ccc")
fig4.legend(loc="lower center", bbox_to_anchor=(0.5, -0.3), ncol=2)
st.pyplot(fig4)
