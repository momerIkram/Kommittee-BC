
import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("🧪 ROSCA Forecast App v14.1 – Full Test Mode")

# Simulate config
config = {
    "monthly_growth": 2.0,
    "rest_period": 1,
    "kibor": 11.0,
    "spread": 5.0,
    "default_rate": 1.0,
    "penalty_pct": 10.0
}

# Simulate durations, slab map, slot fees
durations = [3, 4]
monthly_duration_allocation = {
    0: {3: 60, 4: 40},
    1: {3: 50, 4: 50},
    2: {3: 40, 4: 60},
}
slab_map = {
    3: {1000: 70, 2000: 30},
    4: {2000: 50, 5000: 50}
}
slot_fees = {
    3: {1: {"fee": 1.0, "blocked": False}, 2: {"fee": 1.0, "blocked": False}, 3: {"fee": 1.0, "blocked": False}},
    4: {1: {"fee": 1.0, "blocked": False}, 2: {"fee": 1.0, "blocked": False}, 3: {"fee": 1.0, "blocked": False}, 4: {"fee": 1.0, "blocked": False}},
}

# Simulate user base
months = 12
cohorts = []
monthly_new_users = []
monthly_returning_users = []
monthly_total_users = []

initial_users = 1000
new = initial_users

for month in range(months):
    # Rejoining
    returning = 0
    for cohort in cohorts:
        if month == cohort["start"] + cohort["duration"] + config["rest_period"]:
            returning += cohort["users"]

    # New Users
    if month == 0:
        new = initial_users
    else:
        total_prev = monthly_total_users[-1]
        new = round(total_prev * (config["monthly_growth"] / 100))

    total = new + returning

    cohorts.append({
        "start": month,
        "duration": 3,  # Simplified
        "users": new
    })

    monthly_new_users.append(new)
    monthly_returning_users.append(returning)
    monthly_total_users.append(total)

# Output table
df = pd.DataFrame({
    "Month": list(range(1, months + 1)),
    "New Users": monthly_new_users,
    "Returning Users": monthly_returning_users,
    "Total Users": monthly_total_users
})

st.subheader("📈 Simulated User Growth + Return")
st.dataframe(df)

# Monthly Summary
df["Fee Collected"] = df["Total Users"] * 100
df["NII"] = df["Total Users"] * 50
df["Profit"] = df["Fee Collected"] + df["NII"] - df["Total Users"] * 20
summary = df[["Month", "Total Users", "Fee Collected", "NII", "Profit"]]

st.subheader("📊 Monthly Summary")
st.dataframe(summary)

# Excel export
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Users")
    summary.to_excel(writer, index=False, sheet_name="Summary")
output.seek(0)
st.download_button("📥 Download Test Excel", data=output, file_name="rosca_test_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
