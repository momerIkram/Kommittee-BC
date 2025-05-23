
# ROSCA Forecast App v11 – Fully Integrated & Deployable

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import xlsxwriter

# Sidebar Configurations
st.sidebar.header("TAM & Growth Settings")
total_market = st.sidebar.number_input("Total Market Size", value=20000000)
tam_percent = st.sidebar.slider("TAM %", 1, 100, 10)
start_percent = st.sidebar.slider("Starting TAM %", 1, 100, 10)
growth_rate = st.sidebar.slider("Monthly Growth Rate (%)", 0.0, 10.0, 2.0)
kibor = st.sidebar.number_input("KIBOR (%)", value=14.0)
spread = st.sidebar.number_input("Spread (%)", value=3.0)
default_rate = st.sidebar.slider("Default Rate (%)", 0.0, 100.0, 5.0)
default_penalty = st.sidebar.slider("Default Penalty (%)", 0.0, 100.0, 20.0)

durations = st.multiselect("Select Committee Durations", [3, 4, 5, 6, 8, 10], default=[3, 4, 6])
slab_values = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]

slab_allocations = {}
slot_fees = {}
slot_blocks = {}

for d in durations:
    with st.expander(f"Slab Allocation for {d}M"):
        slab_alloc = {}
        total = 0
        for val in slab_values:
            pct = st.slider(f"{val} PKR", 0, 100, 0, key=f"{d}_{val}")
            slab_alloc[val] = pct
            total += pct
        if total != 100:
            st.error(f"Total slab allocation for {d}M must be 100%.")
        slab_allocations[d] = slab_alloc

    with st.expander(f"Slot Fees and Blocking for {d}M"):
        slot_fees[d] = {}
        slot_blocks[d] = {}
        for s in range(1, d + 1):
            col1, col2 = st.columns(2)
            slot_fees[d][s] = col1.number_input(f"Fee % (Slot {s})", 0.0, 100.0, 2.0, key=f"fee_{d}_{s}")
            slot_blocks[d][s] = col2.checkbox(f"Block Slot {s}", False, key=f"block_{d}_{s}")

@st.cache_data
def simulate_forecast():
    start_users = int(total_market * tam_percent / 100 * start_percent / 100)
    monthly_growth = growth_rate / 100
    forecast = []
    users = start_users

    for i in range(60):
        month_label = pd.Timestamp("2025-01-01") + pd.DateOffset(months=i)
        month_str = month_label.strftime("%b %Y")

        for d in durations:
            for slab, pct in slab_allocations[d].items():
                if pct == 0:
                    continue
                num_users = int(users * pct / 100)
                for slot in range(1, d + 1):
                    if slot_blocks[d][slot]:
                        continue
                    deposit = slab * d
                    fee_pct = slot_fees[d][slot] / 100
                    fee_collected = num_users * deposit * fee_pct
                    nii = num_users * deposit * ((kibor + spread) / 100 / 12)
                    defaults = num_users * deposit * (default_rate / 100)
                    refund_penalty = defaults * (default_penalty / 100)
                    profit = fee_collected + nii - (defaults - refund_penalty)
                    forecast.append({
                        "Month": month_str,
                        "Duration": d,
                        "Slab": slab,
                        "Slot": slot,
                        "Users": num_users,
                        "Deposit/User": deposit,
                        "Fee %": fee_pct * 100,
                        "Fee Collected": fee_collected,
                        "NII": nii,
                        "Defaults": defaults,
                        "Penalty Refund": refund_penalty,
                        "Profit": profit
                    })
        users = int(users * (1 + monthly_growth))
    return pd.DataFrame(forecast)

df = simulate_forecast()
st.subheader("📊 Forecast Table")
st.dataframe(df)

st.subheader("📈 Monthly Trend Chart")
metric = st.selectbox("Select metric", ["Fee Collected", "NII", "Profit"])
chart_df = df.groupby("Month")[metric].sum().reset_index()

fig, ax = plt.subplots()
ax.plot(chart_df["Month"], chart_df[metric], marker='o')
plt.xticks(rotation=45)
plt.title(metric)
plt.tight_layout()
st.pyplot(fig)

def export_excel(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name="Forecast", index=False)
        df.groupby("Month")[["Users", "Fee Collected", "NII", "Profit"]].sum().reset_index().to_excel(writer, sheet_name="Monthly Summary", index=False)
        df.groupby(df["Month"].str[-4:])[["Users", "Fee Collected", "NII", "Profit"]].sum().reset_index().to_excel(writer, sheet_name="Yearly Summary", index=False)
        pd.DataFrame({"Input": ["TAM %", "Start %", "Growth %", "KIBOR", "Spread", "Default Rate", "Default Penalty"],
                      "Value": [tam_percent, start_percent, growth_rate, kibor, spread, default_rate, default_penalty]}).to_excel(writer, sheet_name="Input Config", index=False)
    out.seek(0)
    return out

if st.button("📥 Export Excel"):
    st.download_button("Download Forecast", data=export_excel(df),
                       file_name="rosca_forecast_v11.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
