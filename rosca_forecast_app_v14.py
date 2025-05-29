import streamlit as st
st.set_page_config(layout="wide", page_title="ROSCA Forecast App", page_icon="📊", initial_sidebar_state="expanded")

import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import math # For ceil
from datetime import date, timedelta

# --- Modern Chart Styling Setup ---
# ... (Styling setup remains the same) ...
TEXT_COLOR = '#333333'; GRID_COLOR = '#D8D8D8'; PLOT_BG_COLOR = '#FFFFFF'; FIG_BG_COLOR = '#F8F9FA'
COLOR_PRIMARY_BAR = '#3B75AF'; COLOR_SECONDARY_LINE = '#4CAF50'; COLOR_ACCENT_BAR = '#FFC107'
COLOR_ACCENT_LINE = '#9C27B0'; COLOR_HIGHLIGHT_BAR = '#E91E63'
plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica Neue', 'DejaVu Sans', 'Liberation Sans', 'sans-serif'],
    'axes.labelcolor': TEXT_COLOR, 'xtick.color': TEXT_COLOR, 'ytick.color': TEXT_COLOR, 'axes.titlecolor': TEXT_COLOR,
    'figure.facecolor': FIG_BG_COLOR, 'axes.facecolor': PLOT_BG_COLOR, 'axes.edgecolor': GRID_COLOR,
    'axes.grid': True, 'grid.color': GRID_COLOR, 'grid.linestyle': '--', 'grid.linewidth': 0.7,
    'legend.frameon': False, 'legend.fontsize': 9, 'legend.title_fontsize': 10, 'figure.dpi': 100,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.spines.left': True, 'axes.spines.bottom': True,
    'axes.titlesize': 13, 'axes.labelsize': 11, 'xtick.labelsize': 9, 'ytick.labelsize': 9,
    'lines.linewidth': 2, 'lines.markersize': 5, 'patch.edgecolor': 'none'})

# Helper function to calculate days between two dates
def days_between_specific_dates(start_month_idx, start_day_of_month, end_month_idx, end_day_of_month, base_year=2024):
    if start_month_idx > end_month_idx or (start_month_idx == end_month_idx and start_day_of_month >= end_day_of_month):
        return 0
    start_actual_month = (start_month_idx % 12) + 1; start_actual_year = base_year + (start_month_idx // 12)
    end_actual_month = (end_month_idx % 12) + 1; end_actual_year = base_year + (end_month_idx // 12)
    try:
        date_start = date(start_actual_year, start_actual_month, start_day_of_month)
        date_end = date(end_actual_year, end_actual_month, end_day_of_month)
        return max(0, (date_end - date_start).days)
    except ValueError:
        return max(0, (end_month_idx - start_month_idx) * 30 + (end_day_of_month - start_day_of_month))

# === SCENARIO & UI SETUP ===
st.title("📊 BACHAT-KOMMITTEE Business Case/Pricing")

# ... (Scenario setup remains the same) ...
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
            "name": name, "total_market": total_market, "tam_pct": tam_pct,
            "start_pct": start_pct, "monthly_growth": monthly_growth,
            "annual_growth": annual_growth, "cap_tam": cap_tam
        })

# === GLOBAL INPUTS ===
# ... (Global inputs remain the same, ADDING target profit margin) ...
global_collection_day = st.sidebar.number_input("Collection Day of Month", min_value=1, max_value=28, value=1)
global_payout_day = st.sidebar.number_input("Payout Day of Month", min_value=1, max_value=28, value=20)
profit_split = st.sidebar.number_input("Profit Share for Party A (%)", min_value=0, max_value=100, value=50)
party_a_pct = profit_split / 100; party_b_pct = 1 - party_a_pct
kibor = st.sidebar.number_input("KIBOR (%)", value=11.0) # KIBOR is 11.0 as per image, previous was 11.5
spread = st.sidebar.number_input("Spread (%)", value=1.0) # Spread is 1.0 as per image
rest_period = st.sidebar.number_input("Rest Period (months)", value=1)
default_rate = st.sidebar.number_input("Default Rate (%)", value=10.0) # Default Rate 10.0 as per image
default_pre_pct = st.sidebar.number_input("Pre-Payout Default % (of total defaulters)", min_value=0, max_value=100, value=50)
default_post_pct = 100 - default_pre_pct
global_pre_payout_recovery_pct = st.sidebar.number_input(
    "Pre-Payout Default Recovery % (of Total Commitment)", min_value=0.0, max_value=100.0, value=10.0, step=1.0,
    help="Percentage of the user's TOTAL COMMITMENT value recovered/not lost by the platform if they default pre-payout.")
global_target_profit_margin_pct = st.sidebar.number_input( # NEW INPUT
    "Target Profit Margin % (on Total Commitment)", min_value=0.0, max_value=50.0, value=5.0, step=0.5,
    help="Desired profit margin from each user's total commitment, after NII and covering default losses.")


# === FEE SUGGESTION CALCULATOR (NEW SECTION) ===
with st.expander("💡 Fee Suggestion Calculator", expanded=False):
    st.markdown("""
    This tool helps estimate a suitable fee percentage for a ROSCA product
    based on your global risk, NII, and target profit margin settings.
    """)
    
    fee_calc_cols = st.columns(2)
    # Get available durations from the main configuration section
    # For simplicity, if main 'durations' is empty, provide a default list
    # However, it's better if 'Durations' is selected first in main config.
    available_durations_for_calc = durations if durations else [3, 6, 10] # Use configured or defaults
    selected_duration_for_calc = fee_calc_cols[0].selectbox(
        "Select Duration (Months) for Fee Calc", 
        options=available_durations_for_calc, 
        key="fee_calc_duration"
    )
    
    # Use standard slab amounts for selection
    standard_slabs_for_calc = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
    selected_slab_for_calc = fee_calc_cols[1].selectbox(
        "Select Slab Installment Amount for Fee Calc", 
        options=standard_slabs_for_calc, 
        index=2, # Default to 5000
        key="fee_calc_slab"
    )

    if selected_duration_for_calc and selected_slab_for_calc:
        calc_d = int(selected_duration_for_calc)
        calc_slab = int(selected_slab_for_calc)
        calc_total_commitment = calc_d * calc_slab

        # 1. Expected Default Loss per User
        calc_loss_pre = calc_total_commitment * (1 - (global_pre_payout_recovery_pct / 100))
        calc_loss_post = calc_total_commitment
        calc_avg_loss_per_user = ( (default_rate / 100) * (default_pre_pct / 100) * calc_loss_pre ) + \
                                 ( (default_rate / 100) * ((100 - default_pre_pct) / 100) * calc_loss_post )

        # 2. Expected Granular NII per User
        # For NII suggestion, assume an average payout slot (e.g., halfway through duration)
        calc_avg_payout_slot = math.ceil(calc_d / 2) # 1-indexed slot
        calc_avg_payout_due_month_idx = 0 + calc_avg_payout_slot - 1 # Assuming joining in month_idx 0

        calc_expected_nii_per_user = 0
        calc_daily_rate = (kibor/100 + spread/100) / 365
        for j_inst_calc in range(calc_d): # 0 to d_config-1
            collection_month_idx_inst_calc = 0 + j_inst_calc
            days_held_inst_calc = days_between_specific_dates(
                collection_month_idx_inst_calc, global_collection_day,
                calc_avg_payout_due_month_idx, global_payout_day
            )
            nii_from_inst_calc = calc_slab * calc_daily_rate * days_held_inst_calc
            calc_expected_nii_per_user += nii_from_inst_calc
            
        # 3. Target Profit per User
        calc_target_profit_per_user = calc_total_commitment * (global_target_profit_margin_pct / 100)
        
        # 4. Calculate Suggested Total Fee Amount per User
        calc_suggested_total_fee_amount = calc_avg_loss_per_user + calc_target_profit_per_user - calc_expected_nii_per_user
        
        # 5. Convert to Fee Percentage
        calc_suggested_fee_pct = 0
        if calc_total_commitment > 0:
            calc_suggested_fee_pct = (calc_suggested_total_fee_amount / calc_total_commitment) * 100
        calc_suggested_fee_pct = max(0, calc_suggested_fee_pct)

        st.markdown("---")
        st.markdown(f"**For a {calc_d}M duration, {calc_slab:,} PKR slab product:**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Est. Default Loss / User", value=f"{calc_avg_loss_per_user:,.0f} PKR")
            st.metric(label="Target Profit / User", value=f"{calc_target_profit_per_user:,.0f} PKR")
        with col2:
            st.metric(label="Est. NII / User (Lifetime)", value=f"{calc_expected_nii_per_user:,.0f} PKR")
            st.metric(label="Required Fee / User (Lifetime)", value=f"{calc_suggested_total_fee_amount:,.0f} PKR")
        
        st.success(f"**Suggested Fee Percentage (on Total Commitment): ≥ {calc_suggested_fee_pct:.2f}%**")
        st.caption(f"Based on {default_rate}% DR, {global_pre_payout_recovery_pct}% Pre-Recov, {kibor}% KIBOR, {spread}% Spread, {global_target_profit_margin_pct}% Target Profit.")

# === DURATION/SLAB/SLOT CONFIGURATION ===
# ... (This section remains the same as your last full code version. The fee suggestion is now separate) ...
validation_messages = [] # Reset for main config
durations_input_main = st.multiselect("Select Durations (months) for Simulation", [3, 4, 5, 6, 8, 10], default=[3, 4, 6], key="main_durations")
durations = [int(d) for d in durations_input_main] # Ensure these are int

yearly_duration_share = {}
slab_map = {}
slot_fees = {}
slot_distribution = {}
first_year_defaults = {}

# --- Fee Suggestion Text (to be used in slot fee inputs) ---
# This part needs to be inside the loop where d_config is defined, or we calculate it once
# based on some average/representative values if we want a single suggestion text.
# For now, let's keep the simpler original fee suggestion logic for the help text in the main config,
# as the new calculator provides a more detailed tool.
def get_simple_fee_suggestion_text(d_config_val, current_kibor, current_spread, current_default_rate, current_default_pre_pct, current_recovery_pct):
    example_slab_sugg = 1000
    total_commit_sugg = d_config_val * example_slab_sugg
    if total_commit_sugg == 0: return "N/A"
    # Simplified NII for fee suggestion (e.g., average holding for half duration)
    avg_nii_sugg_for_fee = total_commit_sugg * ((current_kibor + current_spread) / 100 / 12) * (d_config_val / 2)
    # Simplified default loss for fee suggestion
    pre_def_loss_sugg = total_commit_sugg * (current_default_rate/100) * (current_default_pre_pct / 100) * (1 - current_recovery_pct / 100)
    post_def_loss_sugg = total_commit_sugg * (current_default_rate/100) * ((100-current_default_pre_pct) / 100)
    avg_loss_sugg = pre_def_loss_sugg + post_def_loss_sugg
    # Simple target profit (e.g. 5% of commitment)
    simple_target_profit = total_commit_sugg * 0.05 
    
    required_fee_amount = avg_loss_sugg + simple_target_profit - avg_nii_sugg_for_fee
    suggested_pct = (required_fee_amount / total_commit_sugg) * 100 if total_commit_sugg > 0 else 0
    return f"Simple sugg. (1k slab, 5% profit target): ≥ {max(0,suggested_pct):.2f}%"

for y_config in range(1, 6):
    with st.expander(f"Year {y_config} Duration Share"):
        yearly_duration_share[y_config] = {}
        total_dur_share_config = 0
        for d_config in durations: # Use main durations here
            key_config = f"yds_{y_config}_{d_config}"
            if y_config == 1:
                val_config = st.number_input(f"{d_config}M – Year {y_config} (%)", min_value=0, max_value=100, value=0, step=1, key=key_config)
                first_year_defaults[d_config] = val_config
            else:
                default_val_config = first_year_defaults.get(d_config, 0)
                val_config = st.number_input(f"{d_config}M – Year {y_config} (%)", min_value=0, max_value=100, value=default_val_config, step=1, key=key_config)
            yearly_duration_share[y_config][d_config] = val_config
            total_dur_share_config += val_config
        if total_dur_share_config > 100:
            validation_messages.append(f"⚠️ Year {y_config} duration share total is {total_dur_share_config}%. It must not exceed 100%.")

for d_config in durations: # Use main durations here
    with st.expander(f"{d_config}M Slab Distribution"):
        slab_map[d_config] = {}
        total_slab_pct_config = 0
        for slab_amount_config in [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]:
            key_config = f"slab_{d_config}_{slab_amount_config}"
            val_config = st.number_input(f"Slab {slab_amount_config} – {d_config}M (%)", min_value=0, max_value=100, value=0, step=1, key=key_config)
            slab_map[d_config][slab_amount_config] = val_config
            total_slab_pct_config += val_config
        if total_slab_pct_config > 100:
            validation_messages.append(f"⚠️ Slab distribution for {d_config}M totals {total_slab_pct_config}%. It must not exceed 100%.")
    
    # Get simple suggestion text for this duration
    simple_help_text = get_simple_fee_suggestion_text(d_config, kibor, spread, default_rate, default_pre_pct, global_pre_payout_recovery_pct)

    with st.expander(f"{d_config}M Slot Fees & Blocking"):
        if d_config not in slot_fees: slot_fees[d_config] = {}
        if d_config not in slot_distribution: slot_distribution[d_config] = {}
        for s_config in range(1, d_config + 1):
            key_fee_config = f"fee_{d_config}_{s_config}"
            key_block_config = f"block_{d_config}_{s_config}"
            key_pct_config = f"slot_pct_d{d_config}_s{s_config}"
            fee_input_val = st.number_input(f"Slot {s_config} Fee % (on total commitment)", 0.0, 100.0, 1.0, key=key_fee_config, help=simple_help_text) # Using simple help text
            blocked_input_val = st.checkbox(f"Block Slot {s_config}", key=key_block_config)
            slot_pct_input_val = st.number_input(
                label=f"Slot {s_config} % of Users (Duration {d_config}M)", min_value=0, max_value=100, value=0, step=1, key=key_pct_config)
            slot_fees[d_config][s_config] = {"fee": fee_input_val, "blocked": blocked_input_val}
            slot_distribution[d_config][s_config] = slot_pct_input_val
for d_config in durations: # Use main durations here
    if d_config in slot_distribution and slot_distribution[d_config]: # Check if d_config is a key
        total_slot_dist_pct = sum(slot_distribution[d_config].values())
        if total_slot_dist_pct > 100:
            validation_messages.append(f"⚠️ Slot distribution for {d_config}M totals {total_slot_dist_pct}%. It must not exceed 100%.")
if validation_messages:
    for msg_val in validation_messages: st.warning(msg_val)
    st.stop()


# === FORECASTING LOGIC ===
# ... (run_forecast function remains the same as your last version with simplified default logic) ...
def run_forecast(config_param_fc):
    months_fc = 60
    initial_tam_fc = int(config_param_fc['total_market'] * config_param_fc['tam_pct'] / 100)
    new_users_monthly_fc = [int(initial_tam_fc * config_param_fc['start_pct'] / 100)]
    rejoin_tracker_fc = {}
    forecast_data_fc, deposit_log_data_fc, default_log_data_fc, lifecycle_data_fc = [], [], [], []
    TAM_used_cumulative_fc = new_users_monthly_fc[0]
    TAM_current_year_fc = initial_tam_fc
    enforce_cap_growth_fc = config_param_fc.get("cap_tam", False)
    current_kibor_rate_fc = config_param_fc['kibor'] / 100
    current_spread_rate_fc = config_param_fc['spread'] / 100
    daily_interest_rate_fc = (current_kibor_rate_fc + current_spread_rate_fc) / 365
    current_rest_period_months_fc = config_param_fc['rest_period']
    current_default_frac_fc = config_param_fc['default_rate'] / 100
    current_pre_payout_recovery_frac_fc = config_param_fc['pre_payout_recovery_pct'] / 100
    global_default_pre_frac_fc = default_pre_pct / 100

    for m_idx_fc in range(months_fc):
        current_month_num_fc = m_idx_fc + 1; current_year_num_fc = m_idx_fc // 12 + 1
        durations_for_this_year_fc = yearly_duration_share.get(current_year_num_fc, {})
        rejoining_users_this_month_fc = rejoin_tracker_fc.get(m_idx_fc, 0)
        newly_acquired_this_month_fc = new_users_monthly_fc[m_idx_fc] if m_idx_fc < len(new_users_monthly_fc) else 0
        total_onboarding_this_month_fc = newly_acquired_this_month_fc + rejoining_users_this_month_fc

        for dur_val_fc, dur_share_pct_fc in durations_for_this_year_fc.items():
            if dur_val_fc not in slab_map: continue
            users_for_this_duration_fc = int(total_onboarding_this_month_fc * (dur_share_pct_fc / 100))
            for installment_val_fc, slab_share_pct_fc in slab_map[dur_val_fc].items():
                users_for_this_slab_fc = int(users_for_this_duration_fc * (slab_share_pct_fc / 100))
                if dur_val_fc not in slot_fees or dur_val_fc not in slot_distribution: continue
                for slot_num_fc, slot_config_meta_fc in slot_fees[dur_val_fc].items():
                    if slot_config_meta_fc['blocked']: continue
                    fee_on_commitment_frac_fc = slot_config_meta_fc['fee'] / 100
                    total_commitment_per_user_fc = installment_val_fc * dur_val_fc
                    fee_amount_per_user_fc = total_commitment_per_user_fc * fee_on_commitment_frac_fc
                    slot_users_share_pct_fc = slot_distribution[dur_val_fc].get(slot_num_fc, 0)
                    users_in_this_specific_cohort_fc = int(users_for_this_slab_fc * (slot_users_share_pct_fc / 100))
                    if users_in_this_specific_cohort_fc == 0: continue
                    from_rejoin_pool_fc = min(users_in_this_specific_cohort_fc, rejoining_users_this_month_fc)
                    from_newly_acquired_fc = users_in_this_specific_cohort_fc - from_rejoin_pool_fc
                    rejoining_users_this_month_fc -= from_rejoin_pool_fc
                    total_nii_for_cohort_lifetime_per_user = 0
                    payout_due_month_idx_for_cohort_fc = m_idx_fc + slot_num_fc - 1
                    for j_installment_num in range(dur_val_fc):
                        collection_month_of_this_installment_idx = m_idx_fc + j_installment_num
                        days_this_installment_held = days_between_specific_dates(
                            collection_month_of_this_installment_idx, global_collection_day,
                            payout_due_month_idx_for_cohort_fc, global_payout_day)
                        nii_from_this_installment = installment_val_fc * daily_interest_rate_fc * days_this_installment_held
                        total_nii_for_cohort_lifetime_per_user += nii_from_this_installment
                    total_nii_for_cohort_duration_fc = total_nii_for_cohort_lifetime_per_user * users_in_this_specific_cohort_fc
                    avg_monthly_nii_for_cohort = total_nii_for_cohort_duration_fc / dur_val_fc if dur_val_fc > 0 else 0
                    nii_to_log_for_joining_month = avg_monthly_nii_for_cohort
                    num_defaulters_total_fc = int(users_in_this_specific_cohort_fc * current_default_frac_fc)
                    num_pre_payout_defaulters_fc = int(num_defaulters_total_fc * global_default_pre_frac_fc)
                    num_post_payout_defaulters_fc = num_defaulters_total_fc - num_pre_payout_defaulters_fc
                    loss_per_pre_defaulter_fc = total_commitment_per_user_fc * (1 - current_pre_payout_recovery_frac_fc)
                    loss_per_pre_defaulter_fc = max(0, loss_per_pre_defaulter_fc)
                    total_pre_payout_loss_fc = num_pre_payout_defaulters_fc * loss_per_pre_defaulter_fc
                    loss_per_post_defaulter_fc = total_commitment_per_user_fc 
                    total_post_payout_loss_fc = num_post_payout_defaulters_fc * loss_per_post_defaulter_fc
                    total_loss_for_cohort_fc = total_pre_payout_loss_fc + total_post_payout_loss_fc
                    total_fees_for_cohort_fc = fee_amount_per_user_fc * users_in_this_specific_cohort_fc
                    expected_lifetime_profit_for_cohort_fc = (total_fees_for_cohort_fc + total_nii_for_cohort_duration_fc) - total_loss_for_cohort_fc
                    cash_in_installments_this_month_cohort_fc = users_in_this_specific_cohort_fc * installment_val_fc
                    payout_due_calendar_month_for_cohort_fc = payout_due_month_idx_for_cohort_fc + 1 
                    payout_amount_scheduled_for_cohort_fc = users_in_this_specific_cohort_fc * total_commitment_per_user_fc
                    pools_formed_by_this_cohort_fc = users_in_this_specific_cohort_fc / dur_val_fc if dur_val_fc > 0 else 0
                    external_capital_needed_for_cohort_lifetime_fc = max(0, total_loss_for_cohort_fc - (total_fees_for_cohort_fc + total_nii_for_cohort_duration_fc))
                    forecast_data_fc.append({
                        "Month Joined": current_month_num_fc, "Year Joined": current_year_num_fc, "Duration": dur_val_fc, 
                        "Slab Installment": installment_val_fc, "Assigned Slot": slot_num_fc, "Users": users_in_this_specific_cohort_fc, 
                        "Pools Formed": pools_formed_by_this_cohort_fc, "Total Commitment/User": total_commitment_per_user_fc,
                        "Fee % (on Total Commitment)": fee_on_commitment_frac_fc * 100, 
                        "Total Fee Collected (Lifetime)": total_fees_for_cohort_fc, 
                        "NII Earned This Month (Avg)": nii_to_log_for_joining_month, 
                        "Total NII (Lifetime)": total_nii_for_cohort_duration_fc, 
                        "Expected Lifetime Profit": expected_lifetime_profit_for_cohort_fc, 
                        "Cash In (Installments This Month)": cash_in_installments_this_month_cohort_fc, 
                        "Payout Due Month": payout_due_calendar_month_for_cohort_fc, 
                        "Payout Amount Scheduled": payout_amount_scheduled_for_cohort_fc, 
                        "Total Default Loss (Lifetime)": total_loss_for_cohort_fc, 
                        "External Capital For Loss (Lifetime)": external_capital_needed_for_cohort_lifetime_fc})
                    deposit_log_data_fc.append({"Month": current_month_num_fc, "Users Joining": users_in_this_specific_cohort_fc, 
                                              "Installments Collected": cash_in_installments_this_month_cohort_fc, 
                                              "NII This Month (Avg)": nii_to_log_for_joining_month})
                    default_log_data_fc.append({"Month": current_month_num_fc, "Year": current_year_num_fc, 
                                              "Pre-Payout Defaulters (Cohort)": num_pre_payout_defaulters_fc, 
                                              "Post-Payout Defaulters (Cohort)": num_post_payout_defaulters_fc, 
                                              "Default Loss (Cohort Lifetime)": total_loss_for_cohort_fc})
                    lifecycle_data_fc.append({"Month": current_month_num_fc, 
                                            "New Users Acquired for Cohort": from_newly_acquired_fc, 
                                            "Rejoining Users for Cohort": from_rejoin_pool_fc, 
                                            "Total Onboarding to Cohort": users_in_this_specific_cohort_fc})
                    users_completing_cycle_non_default = users_in_this_specific_cohort_fc - num_defaulters_total_fc
                    users_completing_cycle_non_default = max(0, users_completing_cycle_non_default)
                    rejoin_at_month_idx_fc = m_idx_fc + dur_val_fc + int(current_rest_period_months_fc)
                    if rejoin_at_month_idx_fc < months_fc:
                        rejoin_tracker_fc[rejoin_at_month_idx_fc] = rejoin_tracker_fc.get(rejoin_at_month_idx_fc, 0) + users_completing_cycle_non_default
        if m_idx_fc + 1 < months_fc:
            growth_base_for_next_month_fc = total_onboarding_this_month_fc
            next_month_new_users_fc = int(growth_base_for_next_month_fc * (config_param_fc['monthly_growth'] / 100))
            if enforce_cap_growth_fc and (TAM_used_cumulative_fc + next_month_new_users_fc) > TAM_current_year_fc:
                next_month_new_users_fc = max(0, TAM_current_year_fc - TAM_used_cumulative_fc)
            TAM_used_cumulative_fc += next_month_new_users_fc
            if (m_idx_fc + 1) % 12 == 0: TAM_current_year_fc = int(TAM_current_year_fc * (1 + config_param_fc['annual_growth'] / 100))
            new_users_monthly_fc.append(next_month_new_users_fc)
    return (pd.DataFrame(forecast_data_fc).fillna(0), pd.DataFrame(deposit_log_data_fc).fillna(0),
            pd.DataFrame(default_log_data_fc).fillna(0), pd.DataFrame(lifecycle_data_fc).fillna(0))

# === EXPORT AND DISPLAY LOOP ===
# ... (This section remains the same as your last full code version) ...
output_excel_main = io.BytesIO()
with pd.ExcelWriter(output_excel_main, engine="xlsxwriter") as excel_writer_main:
    for scenario_idx_main, scenario_data_main in enumerate(scenarios):
        current_config_main = scenario_data_main.copy()
        current_config_main.update({
            "kibor": kibor, "spread": spread, "rest_period": rest_period,
            "default_rate": default_rate, 
            "pre_payout_recovery_pct": global_pre_payout_recovery_pct 
        })
        df_forecast_main, df_deposit_log_main, df_default_log_main, df_lifecycle_main = run_forecast(current_config_main)
        st.header(f"Scenario: {scenario_data_main['name']}")
        st.subheader(f"📘 Raw Forecast Data (Cohorts by Joining Month)")
        if not df_forecast_main.empty:
            st.dataframe(df_forecast_main.style.format(precision=0, thousands=","))
            df_monthly_direct_main = df_forecast_main.groupby("Month Joined")[
                ["Cash In (Installments This Month)", "NII Earned This Month (Avg)", "Pools Formed", "Users"]
            ].sum().reset_index().rename(columns={"Month Joined": "Month", 
                                                  "Users": "Users Joining This Month",
                                                  "NII Earned This Month (Avg)": "NII This Month (Sum of Avg from New Cohorts)"})
            df_payouts_actual_main = df_forecast_main.groupby("Payout Due Month")[
                ["Payout Amount Scheduled", "Users"]
            ].sum().reset_index().rename(columns={"Payout Due Month": "Month", 
                                                  "Payout Amount Scheduled": "Actual Cash Out This Month",
                                                  "Users": "Payout Recipient Users"})
            df_lifetime_values_main = df_forecast_main.groupby("Month Joined")[
                ["Total Fee Collected (Lifetime)", "Total NII (Lifetime)", "Total Default Loss (Lifetime)", 
                 "Expected Lifetime Profit", "External Capital For Loss (Lifetime)"]
            ].sum().reset_index().rename(columns={"Month Joined": "Month"})
            df_monthly_summary_main = pd.DataFrame({"Month": range(1, 61)})
            df_monthly_summary_main = df_monthly_summary_main.merge(df_monthly_direct_main, on="Month", how="left")
            df_monthly_summary_main = df_monthly_summary_main.merge(df_payouts_actual_main, on="Month", how="left")
            df_monthly_summary_main = df_monthly_summary_main.merge(df_lifetime_values_main, on="Month", how="left")
            df_monthly_summary_main = df_monthly_summary_main.fillna(0)
            df_monthly_summary_main["Net Cash Flow This Month"] = df_monthly_summary_main["Cash In (Installments This Month)"] - df_monthly_summary_main["Actual Cash Out This Month"]
            df_monthly_summary_main["Gross Profit This Month (Accrued from New Cohorts)"] = df_monthly_summary_main["Total Fee Collected (Lifetime)"] + \
                                                                    df_monthly_summary_main["Total NII (Lifetime)"] - \
                                                                    df_monthly_summary_main["Total Default Loss (Lifetime)"]
            st.subheader(f"📊 Monthly Summary for {scenario_data_main['name']}")
            cols_to_display_monthly_main = ["Month", "Users Joining This Month", "Pools Formed", "Cash In (Installments This Month)", 
                                            "Actual Cash Out This Month", "Net Cash Flow This Month", "NII This Month (Sum of Avg from New Cohorts)", 
                                            "Total NII (Lifetime)", "Payout Recipient Users", "Total Fee Collected (Lifetime)", 
                                            "Total Default Loss (Lifetime)", "Gross Profit This Month (Accrued from New Cohorts)", 
                                            "External Capital For Loss (Lifetime)"]
            st.dataframe(df_monthly_summary_main[cols_to_display_monthly_main].style.format(precision=0, thousands=","))
            df_monthly_summary_main["Year"] = ((df_monthly_summary_main["Month"] - 1) // 12) + 1
            df_yearly_summary_main = df_monthly_summary_main.groupby("Year")[
                ["Users Joining This Month", "Pools Formed", "Cash In (Installments This Month)", "Actual Cash Out This Month", 
                 "Net Cash Flow This Month", "NII This Month (Sum of Avg from New Cohorts)", "Total NII (Lifetime)", 
                 "Payout Recipient Users", "Total Fee Collected (Lifetime)", "Total Default Loss (Lifetime)", 
                 "Gross Profit This Month (Accrued from New Cohorts)", "External Capital For Loss (Lifetime)"]
            ].sum().reset_index()
            df_yearly_summary_main.rename(columns={
                "Gross Profit This Month (Accrued from New Cohorts)": "Annual Gross Profit (Accrued from New Cohorts)",
                "NII This Month (Sum of Avg from New Cohorts)": "Annual NII (Sum of Avg from New Cohorts)",
                "Total NII (Lifetime)": "Annual Total NII (Lifetime from New Cohorts)"}, inplace=True)
            df_profit_share_main = pd.DataFrame({
                "Year": df_yearly_summary_main["Year"],
                "External Capital Needed (Annual Accrual)": df_yearly_summary_main["External Capital For Loss (Lifetime)"],
                "Annual Cash In (Installments)": df_yearly_summary_main["Cash In (Installments This Month)"],
                "Annual NII (Accrued Lifetime)": df_yearly_summary_main["Annual Total NII (Lifetime from New Cohorts)"],
                "Annual Default Loss (Accrued)": df_yearly_summary_main["Total Default Loss (Lifetime)"],
                "Annual Fee Collected (Accrued)": df_yearly_summary_main["Total Fee Collected (Lifetime)"],
                "Annual Gross Profit (Accrued)": df_yearly_summary_main["Annual Gross Profit (Accrued from New Cohorts)"],
                "Part-A Profit Share": df_yearly_summary_main["Annual Gross Profit (Accrued from New Cohorts)"] * party_a_pct,
                "Part-B Profit Share": df_yearly_summary_main["Annual Gross Profit (Accrued from New Cohorts)"] * party_b_pct})
            df_profit_share_main["% Loss Covered by External Capital"] = 0
            mask_main = df_yearly_summary_main["Total Default Loss (Lifetime)"] > 0
            if mask_main.any():
                df_profit_share_main.loc[mask_main, "% Loss Covered by External Capital"] = \
                    (df_yearly_summary_main.loc[mask_main, "External Capital For Loss (Lifetime)"] / df_yearly_summary_main.loc[mask_main, "Total Default Loss (Lifetime)"]) * 100
            df_profit_share_main.fillna(0, inplace=True)
            st.subheader(f"💰 Profit Share Summary for {scenario_data_main['name']}")
            st.dataframe(df_profit_share_main.style.format(precision=0, thousands=","))
            st.subheader(f"📆 Yearly Summary for {scenario_data_main['name']}")
            st.dataframe(df_yearly_summary_main.style.format(precision=0, thousands=","))
        else:
            st.warning(f"No forecast data generated for {scenario_data_main['name']}. Summary tables will be empty.")
            df_monthly_summary_main = pd.DataFrame(columns=["Month"]); df_yearly_summary_main = pd.DataFrame(columns=["Year"]); df_profit_share_main = pd.DataFrame(columns=["Year"])
        
        # === 📊 VISUAL CHARTS ===
        # ... (Charting section remains the same) ...
        st.subheader(f"Visual Charts for {scenario_data_main['name']}")
        df_monthly_chart_data_main = df_monthly_summary_main.copy()
        df_yearly_chart_data_main = df_yearly_summary_main.copy()
        if "Year" in df_yearly_chart_data_main.columns and not df_yearly_chart_data_main.empty: df_yearly_chart_data_main["Year"] = df_yearly_chart_data_main["Year"].astype(str)
        df_profit_share_chart_data_main = df_profit_share_main.copy()
        if "Year" in df_profit_share_chart_data_main.columns and not df_profit_share_chart_data_main.empty: df_profit_share_chart_data_main["Year"] = df_profit_share_chart_data_main["Year"].astype(str)
        FIG_SIZE_MAIN = (10, 4.5)
        st.markdown("##### Chart 1: Monthly Pools Formed vs. Cash In (Installments)")
        chart_cols_m1_main = ["Month", "Pools Formed", "Cash In (Installments This Month)"]
        if not df_monthly_chart_data_main.empty and all(col in df_monthly_chart_data_main.columns for col in chart_cols_m1_main):
            fig1_main, ax1_main = plt.subplots(figsize=FIG_SIZE_MAIN); ax2_main = ax1_main.twinx()
            bars1_main = ax1_main.bar(df_monthly_chart_data_main["Month"], df_monthly_chart_data_main["Pools Formed"], color=COLOR_PRIMARY_BAR, label="Pools Formed This Month", width=0.7)
            line1_main, = ax2_main.plot(df_monthly_chart_data_main["Month"], df_monthly_chart_data_main["Cash In (Installments This Month)"], color=COLOR_SECONDARY_LINE, label="Cash In (Installments)", marker='o', linewidth=2, markersize=4)
            ax1_main.set_xlabel("Month"); ax1_main.set_ylabel("Pools Formed", color=COLOR_PRIMARY_BAR); ax2_main.set_ylabel("Cash In (Installments)", color=COLOR_SECONDARY_LINE)
            ax1_main.tick_params(axis='y', labelcolor=COLOR_PRIMARY_BAR); ax2_main.tick_params(axis='y', labelcolor=COLOR_SECONDARY_LINE)
            ax2_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}")); ax1_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))
            handles_main = [bars1_main, line1_main]; labels_main = [h.get_label() for h in handles_main]
            fig1_main.legend(handles_main, labels_main, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2); fig1_main.tight_layout(rect=[0, 0.05, 1, 1]); st.pyplot(fig1_main)
        else: st.caption("Not enough data for Chart 1.")
        st.markdown("##### Chart 2: Monthly Users Joining vs. Accrued Gross Profit (from New Cohorts)")
        chart_cols_m2_main = ["Month", "Users Joining This Month", "Gross Profit This Month (Accrued from New Cohorts)"]
        if not df_monthly_chart_data_main.empty and all(col in df_monthly_chart_data_main.columns for col in chart_cols_m2_main):
            fig2_main, ax3_main = plt.subplots(figsize=FIG_SIZE_MAIN); ax4_main = ax3_main.twinx()
            bars2_main = ax3_main.bar(df_monthly_chart_data_main["Month"], df_monthly_chart_data_main["Users Joining This Month"], color=COLOR_ACCENT_BAR, label="Users Joining This Month", width=0.7)
            line2_main, = ax4_main.plot(df_monthly_chart_data_main["Month"], df_monthly_chart_data_main["Gross Profit This Month (Accrued from New Cohorts)"], color=COLOR_ACCENT_LINE, label="Accrued Gross Profit (New Cohorts)", marker='o', linewidth=2, markersize=4)
            ax3_main.set_xlabel("Month"); ax3_main.set_ylabel("Users Joining", color=COLOR_ACCENT_BAR); ax4_main.set_ylabel("Accrued Gross Profit", color=COLOR_ACCENT_LINE)
            ax3_main.tick_params(axis='y', labelcolor=COLOR_ACCENT_BAR); ax4_main.tick_params(axis='y', labelcolor=COLOR_ACCENT_LINE)
            ax3_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}")); ax4_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))
            handles_main = [bars2_main, line2_main]; labels_main = [h.get_label() for h in handles_main]
            fig2_main.legend(handles_main, labels_main, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2); fig2_main.tight_layout(rect=[0, 0.05, 1, 1]); st.pyplot(fig2_main)
        else: st.caption("Not enough data for Chart 2.")
        st.markdown("##### Chart 3: Annual Pools Formed vs. Annual Cash In (Installments)")
        chart_cols_y1_main = ["Year", "Pools Formed", "Cash In (Installments This Month)"]
        if not df_yearly_chart_data_main.empty and all(col in df_yearly_chart_data_main.columns for col in chart_cols_y1_main):
            fig3_main, ax5_main = plt.subplots(figsize=FIG_SIZE_MAIN); ax6_main = ax5_main.twinx()
            bars3_main = ax5_main.bar(df_yearly_chart_data_main["Year"], df_yearly_chart_data_main["Pools Formed"], color=COLOR_PRIMARY_BAR, label="Annual Pools Formed", width=0.6) 
            line3_main, = ax6_main.plot(df_yearly_chart_data_main["Year"], df_yearly_chart_data_main["Cash In (Installments This Month)"], color=COLOR_SECONDARY_LINE, label="Annual Cash In (Installments)", marker='o', linewidth=2, markersize=4)
            ax5_main.set_xlabel("Year"); ax5_main.set_ylabel("Annual Pools Formed", color=COLOR_PRIMARY_BAR); ax6_main.set_ylabel("Annual Cash In", color=COLOR_SECONDARY_LINE)
            ax5_main.tick_params(axis='y', labelcolor=COLOR_PRIMARY_BAR); ax6_main.tick_params(axis='y', labelcolor=COLOR_SECONDARY_LINE)
            ax5_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}")); ax6_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))
            handles_main = [bars3_main, line3_main]; labels_main = [h.get_label() for h in handles_main]
            fig3_main.legend(handles_main, labels_main, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2); fig3_main.tight_layout(rect=[0, 0.05, 1, 1]); st.pyplot(fig3_main)
        else: st.caption("Not enough data for Chart 3.")
        st.markdown("##### Chart 4: Annual Users Joining vs. Annual Accrued Gross Profit (from New Cohorts)")
        chart_cols_y2_main = ["Year", "Users Joining This Month", "Annual Gross Profit (Accrued from New Cohorts)"]
        if not df_yearly_chart_data_main.empty and all(col in df_yearly_chart_data_main.columns for col in chart_cols_y2_main):
            fig4_main, ax7_main = plt.subplots(figsize=FIG_SIZE_MAIN); ax8_main = ax7_main.twinx()
            bars4_main = ax7_main.bar(df_yearly_chart_data_main["Year"], df_yearly_chart_data_main["Users Joining This Month"], color=COLOR_ACCENT_BAR, label="Annual Users Joining", width=0.6)
            line4_main, = ax8_main.plot(df_yearly_chart_data_main["Year"], df_yearly_chart_data_main["Annual Gross Profit (Accrued from New Cohorts)"], color=COLOR_ACCENT_LINE, label="Annual Accrued Gross Profit (New Cohorts)", marker='o', linewidth=2, markersize=4)
            ax7_main.set_xlabel("Year"); ax7_main.set_ylabel("Annual Users Joining", color=COLOR_ACCENT_BAR); ax8_main.set_ylabel("Annual Accrued Profit", color=COLOR_ACCENT_LINE)
            ax7_main.tick_params(axis='y', labelcolor=COLOR_ACCENT_BAR); ax8_main.tick_params(axis='y', labelcolor=COLOR_ACCENT_LINE)
            ax7_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}")); ax8_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))
            handles_main = [bars4_main, line4_main]; labels_main = [h.get_label() for h in handles_main]
            fig4_main.legend(handles_main, labels_main, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2); fig4_main.tight_layout(rect=[0, 0.05, 1, 1]); st.pyplot(fig4_main)
        else: st.caption("Not enough data for Chart 4.")
        st.markdown("##### Chart 5: Annual External Capital vs. Fee & Accrued Profit")
        chart_cols_y3_main = ["Year", "External Capital Needed (Annual Accrual)", "Annual Fee Collected (Accrued)", "Annual Gross Profit (Accrued)"]
        if not df_profit_share_chart_data_main.empty and all(col in df_profit_share_chart_data_main.columns for col in chart_cols_y3_main):
            fig5_main, ax9_main = plt.subplots(figsize=FIG_SIZE_MAIN); ax10_main = ax9_main.twinx()
            bars5_main = ax9_main.bar(df_profit_share_chart_data_main["Year"], df_profit_share_chart_data_main["External Capital Needed (Annual Accrual)"], color=COLOR_HIGHLIGHT_BAR, label="External Capital (Accrual)", width=0.6)
            line5_fee_main, = ax10_main.plot(df_profit_share_chart_data_main["Year"], df_profit_share_chart_data_main["Annual Fee Collected (Accrued)"], color=COLOR_PRIMARY_BAR, marker='o', label="Annual Fee (Accrual)", linewidth=2, markersize=4)
            line5_profit_main, = ax10_main.plot(df_profit_share_chart_data_main["Year"], df_profit_share_chart_data_main["Annual Gross Profit (Accrued)"], color=COLOR_SECONDARY_LINE, marker='s', label="Annual Gross Profit (Accrual)", linestyle='--', linewidth=2, markersize=4)
            ax9_main.set_xlabel("Year"); ax9_main.set_ylabel("External Capital", color=COLOR_HIGHLIGHT_BAR); ax10_main.set_ylabel("Fee & Profit (Accrued)", color=TEXT_COLOR)
            ax9_main.tick_params(axis='y', labelcolor=COLOR_HIGHLIGHT_BAR); ax10_main.tick_params(axis='y', labelcolor=TEXT_COLOR)
            ax9_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}")); ax10_main.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))
            handles_main = [bars5_main, line5_fee_main, line5_profit_main]; labels_main = [h.get_label() for h in handles_main]
            fig5_main.legend(handles_main, labels_main, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=3); fig5_main.tight_layout(rect=[0, 0.05, 1, 1]); st.pyplot(fig5_main)
        else: st.caption("Not enough data for Chart 5.")

        # Export to Excel
        sheet_name_prefix_main = scenario_data_main['name'][:25].replace(" ", "_").replace("/", "_")
        if not df_forecast_main.empty: df_forecast_main.to_excel(excel_writer_main, index=False, sheet_name=f"{sheet_name_prefix_main}_ForecastCohorts")
        if not df_monthly_summary_main.empty: df_monthly_summary_main[cols_to_display_monthly_main].to_excel(excel_writer_main, index=False, sheet_name=f"{sheet_name_prefix_main}_MonthlySummary")
        if not df_yearly_summary_main.empty: df_yearly_summary_main.to_excel(excel_writer_main, index=False, sheet_name=f"{sheet_name_prefix_main}_YearlySummary")
        if not df_profit_share_main.empty: df_profit_share_main.to_excel(excel_writer_main, index=False, sheet_name=f"{sheet_name_prefix_main}_ProfitShare")
        if not df_deposit_log_main.empty: df_deposit_log_main.to_excel(excel_writer_main, index=False, sheet_name=f"{sheet_name_prefix_main}_DepositLog")
        if not df_default_log_main.empty: df_default_log_main.to_excel(excel_writer_main, index=False, sheet_name=f"{sheet_name_prefix_main}_DefaultLog")
        if not df_lifecycle_main.empty: df_lifecycle_main.to_excel(excel_writer_main, index=False, sheet_name=f"{sheet_name_prefix_main}_LifecycleLog")

output_excel_main.seek(0)
st.sidebar.download_button("📥 Download All Scenarios Excel", data=output_excel_main, file_name="all_scenarios_rosca_forecast.xlsx")
