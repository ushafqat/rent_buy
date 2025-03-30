import streamlit as st
import numpy_financial as npf
import numpy as np
import pandas as pd

# --- Configuration ---
st.set_page_config(layout="wide", page_title="Rent vs. Buy Calculator")

st.title("Rent vs. Buy Financial Comparison (NYC Condo/Co-op)")
st.markdown("""
This app compares the estimated financial outcome of buying a property versus renting a similar property
and investing the difference over a specified time horizon. Adjust the inputs in the sidebar to see
how different assumptions affect the outcome. Select Property Type for appropriate defaults/guidance.
***Disclaimer:** This is a simplified financial model. It does not account for all factors
(e.g., specific co-op/condo rules, unexpected repairs, detailed tax nuances, lifestyle preferences).
Consult with financial and real estate professionals before making any decisions.*
""")

# --- Helper Functions ---
# (Helper functions remain the same as before: calculate_average_monthly_value,
# calculate_fv_annuity, calculate_fv_lump_sum, calculate_loan_balance,
# calculate_interest_paid_over_period)

def calculate_average_monthly_value(initial_value, annual_growth_rate, years):
    """Calculates the average monthly value over a period with annual growth."""
    if annual_growth_rate == 0:
        return initial_value
    # More accurate average calculation using geometric series sum idea
    if years <= 0: return initial_value
    total_periods = int(years * 12)
    monthly_growth_rate = (1 + annual_growth_rate)**(1/12) - 1
    if monthly_growth_rate == 0: # Handle no growth case
        return initial_value

    # Sum of geometric series: initial * (1 - r^n) / (1 - r)
    # We need average, so divide by n (total_periods)
    total_sum = initial_value * (1 - (1 + monthly_growth_rate)**total_periods) / (1 - (1 + monthly_growth_rate))
    average = total_sum / total_periods
    return average

def calculate_fv_annuity(monthly_payment, annual_rate, years):
    """Calculates the future value of a series of monthly payments."""
    if years <= 0 or annual_rate < -1 : return 0 # Avoid calculation errors
    monthly_rate = annual_rate / 12
    periods = int(years * 12)
    # Handle zero rate case
    if monthly_rate == 0:
        return monthly_payment * periods
    return npf.fv(monthly_rate, periods, -monthly_payment, 0)

def calculate_fv_lump_sum(present_value, annual_rate, years):
    """Calculates the future value of a lump sum investment."""
    if years <= 0 : return present_value
    return npf.fv(annual_rate, years, 0, -present_value)

def calculate_loan_balance(loan_amount, annual_rate, term_years, years_passed):
    """Calculates the remaining loan balance after a certain number of years."""
    if loan_amount <= 0: return 0
    if years_passed <= 0: return loan_amount
    if years_passed >= term_years: return 0
    monthly_rate = annual_rate / 12
    periods_total = int(term_years * 12)
    periods_passed = int(years_passed * 12)
    # Calculate the present value of the remaining payments
    pmt = npf.pmt(monthly_rate, periods_total, -loan_amount)
    # Use FV function to find remaining balance (which is the PV of remaining payments)
    # Or calculate FV of initial loan and FV of payments made
    remaining_balance = npf.fv(monthly_rate, periods_passed, pmt, -loan_amount)
    # Alternative using PV: remaining_balance = npf.pv(monthly_rate, periods_total - periods_passed, -pmt)
    return remaining_balance if remaining_balance > 0 else 0


def calculate_interest_paid_over_period(loan_amount, annual_rate, term_years, start_year, end_year):
    """Calculates total interest paid between start_year (exclusive) and end_year (inclusive)."""
    if loan_amount <= 0 or start_year >= end_year: return 0
    monthly_rate = annual_rate / 12
    periods_total = int(term_years * 12)
    pmt = npf.pmt(monthly_rate, periods_total, -loan_amount)

    total_interest = 0
    # numpy_financial ipmt is 1-based for periods
    start_period = int(start_year * 12) + 1
    end_period = int(end_year * 12) + 1

    # Ensure periods are within the loan term
    start_period = max(1, start_period)
    end_period = min(periods_total + 1, end_period)
    if start_period >= end_period: return 0

    # Calculate interest for each month in the range
    try:
        # Need pv (present value) which is the loan amount
        interest_payments = npf.ipmt(monthly_rate, np.arange(start_period, end_period), periods_total, pv=-loan_amount)
        total_interest = np.sum(interest_payments)
    except Exception as e:
         st.error(f"Error calculating interest: {e}") # Catch potential errors
         total_interest = 0 # Avoid breaking the app

    return abs(total_interest) # Interest is negative, return positive value


# --- Sidebar Inputs ---
st.sidebar.header("Scenario Inputs & Assumptions")

# Property Type Selector
property_type = st.sidebar.selectbox("Property Type", ["Co-op", "Condo"], index=0)

# Adjust defaults based on property type
default_closing_costs = 2.5 if property_type == "Co-op" else 4.5
closing_costs_help = "Typical Buyer Closing Costs in NYC: ~1-3% + Mansion Tax for Co-ops, ~3-6% for Condos (incl. Mortgage Recording Tax)."
prop_tax_portion_help = "For Co-ops: Enter % of monthly fees allocated to property tax (from co-op statement). Set to 0 if using 'Separate Annual Tax' field."
separate_prop_tax_help = "For Condos: Enter total annual property tax bill. For Co-ops: Use this to override % calculation if known."
dp_help = "Enter your planned down payment. Note: Co-ops often require minimums of 20-50%+, while condos may allow less based on lender."

# Property & Loan Inputs
st.sidebar.subheader("Property & Loan (Buy Scenario)")
home_price = st.sidebar.number_input("Home Price ($)", min_value=100000, value=1595000, step=5000, format="%d")
down_payment_percent = st.sidebar.slider("Down Payment (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5, format="%.1f%%", help=dp_help)
interest_rate_percent = st.sidebar.slider("Mortgage Interest Rate (%)", min_value=1.0, max_value=15.0, value=7.188, step=0.001, format="%.3f%%")
loan_term_years = st.sidebar.selectbox("Loan Term (Years)", options=[15, 20, 30], index=2)
monthly_fees = st.sidebar.number_input(f"Monthly Fees ({'Maint.' if property_type == 'Co-op' else 'Common Charges'})", min_value=0, value=3398, step=10, format="%d")
closing_costs_percent = st.sidebar.slider("Estimated Buyer Closing Costs (% of Price)", min_value=0.0, max_value=10.0, value=default_closing_costs, step=0.1, format="%.1f%%", help=closing_costs_help)

# Rent Inputs
st.sidebar.subheader("Rental Scenario")
rent_monthly = st.sidebar.number_input("Equivalent Monthly Rent (Year 1)", min_value=100, value=10000, step=100, format="%d")

# Shared Assumptions
st.sidebar.subheader("Market & Time Assumptions")
time_horizon_years = st.sidebar.slider("Time Horizon (Years)", min_value=1, max_value=30, value=10, step=1)
property_appreciation_rate_percent = st.sidebar.slider("Avg. Annual Property Appreciation (%)", min_value=-5.0, max_value=15.0, value=3.0, step=0.1, format="%.1f%%")
investment_return_rate_percent = st.sidebar.slider("Avg. Annual Investment Return (%)", min_value=0.0, max_value=15.0, value=7.0, step=0.1, format="%.1f%%")
rent_growth_rate_percent = st.sidebar.slider("Avg. Annual Rent Growth (%)", min_value=0.0, max_value=10.0, value=3.0, step=0.1, format="%.1f%%")
maintenance_growth_rate_percent = st.sidebar.slider(f"Avg. Annual {'Maint.' if property_type == 'Co-op' else 'Common Charge'} Growth (%)", min_value=0.0, max_value=10.0, value=3.0, step=0.1, format="%.1f%%")
selling_costs_percent = st.sidebar.slider("Estimated Selling Costs (% of Future Value)", min_value=0.0, max_value=10.0, value=7.0, step=0.1, format="%.1f%%")

# Tax Inputs
st.sidebar.subheader("Tax Assumptions (Approximate)")
prop_tax_portion_percent = st.sidebar.slider("Property Tax Portion of Monthly Fees (%)", min_value=0.0, max_value=100.0, value=40.0 if property_type == 'Co-op' else 0.0, step=1.0, format="%.0f%%", help=prop_tax_portion_help)
separate_prop_tax_annual = st.sidebar.number_input("Separate Annual Property Tax ($)", min_value=0, value=0, step=100, format="%d", help=separate_prop_tax_help)
marginal_tax_rate_percent = st.sidebar.slider("Combined Marginal Tax Rate (%)", min_value=0.0, max_value=60.0, value=40.0, step=0.5, format="%.1f%%", help="Your combined Federal + State + Local marginal tax rate.")
standard_deduction = st.sidebar.number_input("Standard Deduction ($)", min_value=0, value=30000, step=100, format="%d", help="Your estimated standard deduction (e.g., ~30k for MFJ in 2025).")
mortgage_interest_limit = st.sidebar.number_input("Mortgage Interest Deduction Limit ($)", min_value=0, value=750000, step=1000, format="%d", help="Typically $750,000 for loans after 12/15/2017.")
salt_cap = st.sidebar.number_input("SALT Deduction Cap ($)", min_value=0, value=10000, step=500, format="%d", help="Typically $10,000 per household.")

# --- Convert percentages to decimals ---
down_payment_rate = down_payment_percent / 100.0
interest_rate = interest_rate_percent / 100.0
closing_costs_rate = closing_costs_percent / 100.0
property_appreciation_rate = property_appreciation_rate_percent / 100.0
investment_return_rate = investment_return_rate_percent / 100.0
rent_growth_rate = rent_growth_rate_percent / 100.0
maintenance_growth_rate = maintenance_growth_rate_percent / 100.0
selling_costs_rate = selling_costs_percent / 100.0
prop_tax_portion_rate = prop_tax_portion_percent / 100.0
marginal_tax_rate = marginal_tax_rate_percent / 100.0

# --- Calculations ---

# Buy Scenario - Upfront Costs
down_payment_amount = home_price * down_payment_rate
loan_amount = home_price - down_payment_amount
closing_costs_amount = home_price * closing_costs_rate
initial_cash_outlay = down_payment_amount + closing_costs_amount

# Buy Scenario - Monthly Costs (Year 1)
p_and_i = 0
if loan_amount > 0 and interest_rate >= 0 and loan_term_years > 0:
    p_and_i = npf.pmt(interest_rate / 12, loan_term_years * 12, -loan_amount)
buy_monthly_cost_gross_y1 = p_and_i + monthly_fees

# Buy Scenario - Property Tax Calculation (Year 1 Basis)
total_prop_tax_y1 = 0
if property_type == "Co-op":
    # Primarily use % of maintenance, unless separate tax is entered as override
    prop_tax_from_maint_y1 = (monthly_fees * 12) * prop_tax_portion_rate
    total_prop_tax_y1 = prop_tax_from_maint_y1 if separate_prop_tax_annual == 0 else separate_prop_tax_annual
    if separate_prop_tax_annual > 0 and prop_tax_portion_rate > 0:
         st.sidebar.info("Using 'Separate Annual Tax' for Co-op tax calculation.")
elif property_type == "Condo":
    # Primarily use separate annual tax. Ignore % portion.
    total_prop_tax_y1 = separate_prop_tax_annual
    if prop_tax_portion_percent > 0:
        st.sidebar.warning("For Condos, property tax is typically paid separately. The '% Property Tax Portion' slider is ignored.")


# Buy Scenario - Tax Savings (Average over Horizon)
total_tax_savings_over_horizon = 0
average_annual_tax_saving = 0
average_monthly_tax_saving = 0

if marginal_tax_rate > 0 and time_horizon_years > 0 and loan_amount > 0: # Ensure loan exists for interest deduction
    for year in range(1, int(time_horizon_years) + 1):
        # Interest paid during this year
        interest_paid_this_year = calculate_interest_paid_over_period(loan_amount, interest_rate, loan_term_years, year - 1, year)

        # Calculate deductible interest based on limit
        deductible_interest_ratio = 1.0
        if loan_amount > mortgage_interest_limit > 0:
             # Use initial ratio as approximation for average over the year
             deductible_interest_ratio = min(1.0, mortgage_interest_limit / loan_amount)
        deductible_interest_this_year = interest_paid_this_year * deductible_interest_ratio

        # Estimate property tax for this year
        # Simplified: Assume prop tax grows at maintenance growth rate if derived from it,
        # or maybe a separate growth rate if entered separately? Let's stick to maint growth rate for simplicity.
        prop_tax_this_year = total_prop_tax_y1 * ((1 + maintenance_growth_rate)**(year - 1)) # Approx growth

        # Calculate SALT deduction (capped)
        # Assuming state income tax likely exceeds $10k, SALT is capped at $10k including prop tax
        # A more precise calc would check if state income + prop tax > 10k
        salt_deduction_this_year = min(prop_tax_this_year, salt_cap) # Simplification: Assumes prop tax is the binding constraint or income tax fills rest up to cap

        # Total Itemized Deductions for this year (related to housing)
        itemized_deductions_this_year = deductible_interest_this_year + salt_deduction_this_year # Add other potential deductions if needed (e.g., charity)

        # Tax saving for the year vs standard deduction
        tax_saving_this_year = max(0, itemized_deductions_this_year - standard_deduction) * marginal_tax_rate
        total_tax_savings_over_horizon += tax_saving_this_year

    average_annual_tax_saving = total_tax_savings_over_horizon / time_horizon_years if time_horizon_years > 0 else 0
    average_monthly_tax_saving = average_annual_tax_saving / 12

# Buy Scenario - Average Monthly Costs
avg_monthly_fees = calculate_average_monthly_value(monthly_fees, maintenance_growth_rate, time_horizon_years)
# Note: For Condo, the 'avg_monthly_fees' represents Common Charges. Need to add avg prop tax.
avg_monthly_prop_tax = calculate_average_monthly_value(total_prop_tax_y1 / 12, maintenance_growth_rate, time_horizon_years) # Assume tax grows at same rate

avg_monthly_buy_cost_gross = p_and_i + avg_monthly_fees
if property_type == "Condo":
    avg_monthly_buy_cost_gross += avg_monthly_prop_tax # Add separate avg tax for condo gross cost

avg_monthly_buy_cost_net = avg_monthly_buy_cost_gross - average_monthly_tax_saving

# Buy Scenario - Future Outcomes
future_property_value = home_price * ((1 + property_appreciation_rate) ** time_horizon_years)
loan_balance_future = calculate_loan_balance(loan_amount, interest_rate, loan_term_years, time_horizon_years)
selling_costs_amount = future_property_value * selling_costs_rate
net_equity_after_sale = future_property_value - loan_balance_future - selling_costs_amount
buy_net_financial_gain = net_equity_after_sale - initial_cash_outlay

# Rent Scenario - Calculations
initial_investment = initial_cash_outlay # Amount not spent on buying
avg_monthly_rent = calculate_average_monthly_value(rent_monthly, rent_growth_rate, time_horizon_years)

# Calculate average monthly amount available to invest
avg_monthly_investment = max(0, avg_monthly_buy_cost_net - avg_monthly_rent) # Invest if buying is effectively more expensive

# Future value of investments
fv_initial_investment = calculate_fv_lump_sum(initial_investment, investment_return_rate, time_horizon_years)
fv_monthly_investments = calculate_fv_annuity(avg_monthly_investment, investment_return_rate, time_horizon_years)
total_fv_investments = fv_initial_investment + fv_monthly_investments
rent_net_financial_gain = total_fv_investments - initial_investment

# --- Display Results ---

st.header("Comparison Summary")
st.markdown(f"*(Based on a **{time_horizon_years:.0f}-year** time horizon for a **{property_type}**)*")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Buying Scenario")
    st.metric(label="Est. Net Financial Gain", value=f"${buy_net_financial_gain:,.0f}")
    st.markdown("*(Future Net Equity - Initial Cash Outlay)*")


with col2:
    st.subheader("Renting & Investing Scenario")
    st.metric(label="Est. Net Financial Gain", value=f"${rent_net_financial_gain:,.0f}")
    st.markdown("*(Future Investment Value - Initial Investment Amount)*")


st.header(" ") # Spacer

# Conclusion
st.subheader("Conclusion")
difference = buy_net_financial_gain - rent_net_financial_gain
if difference > 0:
    st.success(f"Buying appears **more financially beneficial** by approximately **${difference:,.0f}** over {time_horizon_years:.0f} years, based on these assumptions.")
elif difference < 0:
    st.error(f"Renting & Investing appears **more financially beneficial** by approximately **${abs(difference):,.0f}** over {time_horizon_years:.0f} years, based on these assumptions.")
else:
    st.info("Buying and Renting & Investing appear to have a similar financial outcome based on these assumptions.")

st.markdown("---")


# --- Detailed Breakdown ---
st.header("Detailed Breakdown & Assumptions")

# Assumptions Display
with st.expander("Key Assumptions Used", expanded=False):
    assumptions_data = {
        "Parameter": [
            "Property Type", "Time Horizon", "Avg. Property Appreciation", "Avg. Investment Return",
            "Avg. Rent Growth", f"Avg. {'Maint.' if property_type=='Co-op' else 'Comm. Charge'} Growth", "Property Selling Costs",
            "Marginal Tax Rate", "Standard Deduction", "Mortgage Interest Limit", "SALT Cap"
        ],
        "Value": [
            property_type, f"{time_horizon_years:.0f} Years", f"{property_appreciation_rate:.1%}", f"{investment_return_rate:.1%}",
            f"{rent_growth_rate:.1%}", f"{maintenance_growth_rate:.1%}", f"{selling_costs_rate:.1%}",
            f"{marginal_tax_rate:.1%}", f"${standard_deduction:,.0f}", f"${mortgage_interest_limit:,.0f}", f"${salt_cap:,.0f}"
        ]
    }
    st.table(pd.DataFrame(assumptions_data))

# Buy Scenario Details
with st.expander("Buy Scenario Details", expanded=False):
    st.markdown("##### Upfront Costs")
    st.metric(label="Total Initial Cash Outlay", value=f"${initial_cash_outlay:,.0f}")
    st.markdown(f"* Down Payment: ${down_payment_amount:,.0f} ({down_payment_percent:.1f}%)")
    st.markdown(f"* Est. Closing Costs: ${closing_costs_amount:,.0f} ({closing_costs_percent:.1f}%)")

    st.markdown("##### Monthly Costs")
    st.metric(label="Year 1 Gross Monthly Cost", value=f"${buy_monthly_cost_gross_y1:,.0f}")
    st.markdown(f"* P&I: ${p_and_i:,.0f}")
    st.markdown(f"* {'Maintenance' if property_type == 'Co-op' else 'Common Charges'}: ${monthly_fees:,.0f}")
    if property_type == "Condo":
         st.markdown(f"* Separate Property Tax (Year 1): ${total_prop_tax_y1/12:,.0f}")

    st.metric(label="Est. Average Monthly Tax Saving", value=f"${average_monthly_tax_saving:,.0f}")
    st.metric(label="Est. Average Net Monthly Cost (After Tax Saving)", value=f"${avg_monthly_buy_cost_net:,.0f}")


    st.markdown(f"##### Outcome after {time_horizon_years:.0f} Years")
    st.metric(label="Est. Future Property Value", value=f"${future_property_value:,.0f}")
    st.metric(label="Est. Remaining Loan Balance", value=f"${loan_balance_future:,.0f}")
    st.metric(label="Est. Selling Costs", value=f"${selling_costs_amount:,.0f}")
    st.metric(label="Est. Net Equity After Sale", value=f"${net_equity_after_sale:,.0f}")

# Rent Scenario Details
with st.expander("Rent & Invest Scenario Details", expanded=False):
    st.markdown("##### Investment Basis")
    st.metric(label="Initial Investment (Funds not used for buying)", value=f"${initial_investment:,.0f}")
    st.metric(label="Est. Average Monthly Investment (Based on cost difference)", value=f"${avg_monthly_investment:,.0f}")
    st.markdown(f"* (Compares Avg. Effective Buy Cost ${avg_monthly_buy_cost_net:,.0f} vs. Avg. Rent Cost ${avg_monthly_rent:,.0f})*")

    st.markdown(f"##### Investment Outcome after {time_horizon_years:.0f} Years (at {investment_return_rate:.1%} avg. return)")
    st.metric(label="Future Value of Initial Investment", value=f"${fv_initial_investment:,.0f}")
    st.metric(label="Future Value of Monthly Investments", value=f"${fv_monthly_investments:,.0f}")
    st.metric(label="Total Future Value of Investments", value=f"${total_fv_investments:,.0f}")

