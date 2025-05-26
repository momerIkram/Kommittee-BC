
import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🧪 ROSCA Forecast App v14.1 – Test Mode")

# Simulated test inputs
durations = [3, 4]
slab_map = {
    3: {1000: 50, 2000: 50},
    4: {2000: 100}
}
slot_fees = {
    3: {1: {"fee": 1.0, "blocked": False}, 2: {"fee": 1.0, "blocked": False}, 3: {"fee": 1.0, "blocked": False}},
    4: {1: {"fee": 1.0, "blocked": False}, 2: {"fee": 1.0, "blocked": False}, 3: {"fee": 1.0, "blocked": False}, 4: {"fee": 1.0, "blocked": False}},
}

# Dummy forecast
forecast = []
for m in range(1, 6):
    for d in durations:
        for slab, pct in slab_map[d].items():
            forecast.append({
                "Month": m,
                "Duration": d,
                "Slab": slab,
                "Users": 10 * m,
                "Fee Collected": 1000 + 50 * m,
                "NII": 500 + 20 * m,
                "Profit": 1500 + 70 * m
            })

df_forecast = pd.DataFrame(forecast)
df_monthly = df_forecast.groupby("Month")[["Users", "Fee Collected", "NII", "Profit"]].sum().reset_index()

st.subheader("📈 Forecast Table (Sample)")
st.dataframe(df_forecast)

st.subheader("📅 Monthly Summary (Sample)")
st.dataframe(df_monthly)
