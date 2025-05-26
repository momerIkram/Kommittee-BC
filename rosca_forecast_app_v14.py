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
            avg_nii = deposit_per_user * ((kibor + spread) / 100 / 12) * sum(range(1, d + 1)) / d
            pre_def_loss = deposit_per_user * default_rate * (default_pre_pct / 100) * (1 - penalty_pct / 100)
            post_def_loss = deposit_per_user * default_rate * (default_post_pct / 100)
            avg_loss = (pre_def_loss + post_def_loss) / 100
            suggested_fee_pct = ((avg_nii + avg_loss) / deposit_per_user) * 100
            fee = st.number_input(f"Slot {s} Fee %", 0.0, 100.0, 1.0, key=f"fee_{d}_{s}", help=f"Suggested ≥ {suggested_fee_pct:.2f}% to break even on NII + default")
            blocked = st.checkbox(f"Block Slot {s}", key=f"block_{d}_{s}")
            slot_fees[d][s] = {"fee": fee, "blocked": blocked}
                                    slot_pct = st.slider(f"Slot {s} % of Users", 0, 100, 0, key=f"slot_pct_{d}_{s}")
