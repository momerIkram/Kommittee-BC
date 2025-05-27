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
collection_day = st.sidebar.number_input("Collection Day of Month", min_value=1, max_value=28, value=1)
payout_day = st.sidebar.number_input("Payout Day of Month", min_value=1, max_value=28, value=20)
profit_split = st.sidebar.slider("Profit Share for Party A (%)", 0, 100, 50)
party_a_pct = profit_split / 100
party_b_pct = 1 - party_a_pct
kibor = st.sidebar.number_input("KIBOR (%)", value=11.0)
spread = st.sidebar.number_input("Spread (%)", value=5.0)
rest_period = st.sidebar.number_input("Rest Period (months)", value=1)
default_rate = st.sidebar.number_input("Default Rate (%)", value=1.0)
default_pre_pct = st.sidebar.slider("Pre-Payout Default %", 0, 100, 50)
default_post_pct = 100 - default_pre_pct
penalty_pct = st.sidebar.number_input("Pre-Payout Refund (%)", value=10.0)

# === DURATION/SLAB/SLOT CONFIGURATION ===

# === RUN FORECAST AND DISPLAY ===
from matplotlib.ticker import FuncFormatter

if st.button("Run Forecast"):
    if validation_messages:
        for msg in validation_messages:
            st.error(msg)
    else:
        forecasts = generate_forecast(scenarios, durations, slab_map, slot_fees, slot_distribution, yearly_duration_share)
        summaries = summarize_forecast(forecasts)

        for i, df in enumerate(forecasts):
            st.subheader(f"📘 {scenarios[i]['name']} Forecast Table")
            st.dataframe(df)
            st.subheader("📊 Monthly Summary")
            st.dataframe(summaries[i]['monthly'])
            st.subheader("📆 Yearly Summary")
            st.dataframe(summaries[i]['yearly'])

        excel_data = export_forecast_to_excel(forecasts, summaries)
        st.download_button(
            label="📥 Download Excel Report",
            data=excel_data,
            file_name="rosca_forecast_v15.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Display chart for Profit and NII trends
        st.subheader("📈 Profit & NII Trends")
        fig, ax = plt.subplots()
        for i, summary in enumerate(summaries):
            monthly = summary['monthly']
            ax.plot(monthly['Month'], monthly['Profit'], label=f"{scenarios[i]['name']} – Profit")
            ax.plot(monthly['Month'], monthly['NII'], linestyle='--', label=f"{scenarios[i]['name']} – NII")
        ax.set_xlabel("Month")
        ax.set_ylabel("Amount (PKR)")
        ax.set_title("Monthly Profit and NII Over Time")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x):,}"))
        ax.legend()
        st.pyplot(fig)

        # Display chart for Cash In/Out
        st.subheader("💸 Cash In vs Cash Out")
        fig2, ax2 = plt.subplots()
        for i, summary in enumerate(summaries):
            monthly = summary['monthly']
            ax2.plot(monthly['Month'], monthly['Cash In'], label=f"{scenarios[i]['name']} – Cash In")
            ax2.plot(monthly['Month'], monthly['Cash Out'], linestyle='--', label=f"{scenarios[i]['name']} – Cash Out")
        ax2.set_xlabel("Month")
        ax2.set_ylabel("Amount (PKR)")
        ax2.set_title("Monthly Cash Flow")
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x):,}"))
        ax2.legend()
        st.pyplot(fig2)

# === FORECAST FUNCTIONS ===

def summarize_forecast(forecasts):
    summaries = []
    for df in forecasts:
        monthly = df.groupby(["Scenario", "Month"])[["Users", "Cash In", "Cash Out", "Fee Collected", "NII", "Default Loss", "Profit"]].sum().reset_index()
        yearly = df.groupby(["Scenario", "Year"])[["Users", "Cash In", "Cash Out", "Fee Collected", "NII", "Default Loss", "Profit"]].sum().reset_index()
        summaries.append({"monthly": monthly, "yearly": yearly})
    return summaries

def export_forecast_to_excel(forecasts, summaries):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for i, df in enumerate(forecasts):
            df.to_excel(writer, index=False, sheet_name=f"Forecast_{i+1}")
            summaries[i]['monthly'].to_excel(writer, index=False, sheet_name=f"Monthly_{i+1}")
            summaries[i]['yearly'].to_excel(writer, index=False, sheet_name=f"Yearly_{i+1}")

        # Add charts
        workbook = writer.book
        for i, summary in enumerate(summaries):
            worksheet = writer.sheets[f"Monthly_{i+1}"]
            chart = workbook.add_chart({'type': 'line'})
            chart.add_series({
                'name':       f"=Monthly_{i+1}!$E$1",
                'categories': f"=Monthly_{i+1}!$B$2:$B${len(summary['monthly']) + 1}",
                'values':     f"=Monthly_{i+1}!$E$2:$E${len(summary['monthly']) + 1}",
            })
            chart.set_title({'name': 'Profit Trend'})
            chart.set_x_axis({'name': 'Month'})
            chart.set_y_axis({'name': 'PKR'})
            worksheet.insert_chart('K2', chart)

            # Optional: add breakeven analysis placeholder
            worksheet.write("J1", "Breakeven Indicator")
            worksheet.write("J2", "Flag when Profit < 0")

    output.seek(0)
    return output
def generate_forecast(scenarios, durations, slab_map, slot_fees, slot_distribution, yearly_duration_share):
    forecasts = []
    for scenario in scenarios:
        rows = []
        tam = int((scenario['total_market'] * scenario['tam_pct']) / 100)
        active_users = int(tam * scenario['start_pct'] / 100)
        for month in range(1, 61):
            year = (month - 1) // 12 + 1
            if month % 12 == 1 and month > 1:
                if scenario['cap_tam']:
                    tam = tam  # no change
                else:
                    tam = int(tam * (1 + scenario['annual_growth'] / 100))
            new_users = int(active_users * (scenario['monthly_growth'] / 100))
            active_users += new_users

            for d in yearly_duration_share.get(year, {}):
                dur_share = yearly_duration_share[year][d] / 100
                dur_users = int(active_users * dur_share)
                for slab, slab_pct in slab_map[d].items():
                    slab_users = int(dur_users * slab_pct / 100)
                    deposit = slab * d
                    for s in range(1, d + 1):
                        if slot_fees[d][s]['blocked']:
                            continue
                        slot_share = slot_distribution[d].get(s, 0) / 100
                        users = int(slab_users * slot_share)
                        fee_pct = slot_fees[d][s]['fee'] / 100
                        fee_amt = users * deposit * fee_pct
                        cash_in = users * slab
                        cash_out = users * deposit if s == d else 0
                        held_days = max(payout_day - collection_day, 1)
                        nii_amt = users * deposit * ((kibor + spread) / 100 / 365) * held_days
                        defaults = users * default_rate / 100
                        default_loss = defaults * deposit
                        profit = fee_amt + nii_amt - default_loss
                        rows.append({
                            "Scenario": scenario['name'], "Month": month, "Year": year, "Duration": d,
                            "Slab": slab, "Slot": s, "Users": users, "Deposit": deposit, "Fee %": fee_pct * 100,
                            "Fee Collected": fee_amt, "Cash In": cash_in, "Cash Out": cash_out,
                            "NII": nii_amt, "Default Loss": default_loss, "Profit": profit
                        })
        forecasts.append(pd.DataFrame(rows))
    return forecasts
slot_buffer_warning = []
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
        slot_distribution = {}
        slot_distribution[d] = {}
        for s in range(1, d + 1):
                                                deposit_per_user = d * 1000  # base slab assumption for preview
            pre_def_loss = deposit_per_user * default_rate * (default_pre_pct / 100) * (1 - penalty_pct / 100)
            post_def_loss = deposit_per_user * default_rate * (default_post_pct / 100)
            avg_nii = deposit_per_user * ((kibor + spread) / 100 / 12) * sum(range(1, d + 1)) / d
            avg_loss = (pre_def_loss + post_def_loss) / 100
            suggested_fee_pct = ((avg_nii + avg_loss) / deposit_per_user) * 100
            fee = st.number_input(f"Slot {s} Fee %", 0.0, 100.0, 1.0, key=f"fee_{d}_{s}", help=f"Suggested ≥ {suggested_fee_pct:.2f}% to break even on NII + default")
            blocked = st.checkbox(f"Block Slot {s}", key=f"block_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": blocked}
            slot_pct = st.slider(f"Slot {s} % of Users", 0, 100, 0, key=f"slot_pct_{d}_{s}")
            slot_distribution[d][s] = slot_pct
