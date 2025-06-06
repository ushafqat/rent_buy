import streamlit as st
import numpy_financial as npf
import numpy as np
import pandas as pd

# --- Configuration ---
st.set_page_config(layout="wide", page_title="Rent vs. Buy Calculator")

st.title("Rent vs. Buy vs. Buy & Rent Out Financial Comparison")
st.markdown("""
This app compares the estimated financial outcome of three scenarios over a specified time horizon:
1.  **Buying & Occupying:** Living in the purchased property.
2.  **Renting & Investing:** Renting a similar property and investing the down payment and cost differences (based on *gross* buying costs).
3.  **Buying & Renting Out (Condo Only):** Buying a condo, living in it for a period, then renting it out for the remainder of the horizon before selling.

Adjust the inputs in the sidebar. The "Buy & Rent Out" option appears only for Condos.
***Disclaimer:** This is a simplified financial model using numerous assumptions and approximations, especially regarding taxes (depreciation, rental income, capital gains). Passive Activity Loss rules for rentals are ignored. Consult with financial, tax, and real estate professionals before making decisions.*
""")

# --- Helper Functions ---
# (Helper functions remain the same)
def calculate_average_monthly_value(initial_value, annual_growth_rate, years):
    """Calculates the average monthly value over a period with annual growth."""
    if annual_growth_rate == 0:
        return initial_value
    if years <= 0: return initial_value
    total_periods = int(years * 12)
    monthly_growth_rate = (1 + annual_growth_rate)**(1/12) - 1
    if monthly_growth_rate == 0:
        return initial_value
    # Using formula for sum of geometric series: a * (1 - r^n) / (1 - r)
    total_sum = initial_value * (1 - (1 + monthly_growth_rate)**total_periods) / (-monthly_growth_rate)
    average = total_sum / total_periods if total_periods > 0 else initial_value
    return average

def calculate_fv_annuity(monthly_payment, annual_rate, years):
    """Calculates the future value of a series of monthly payments."""
    if years <= 0 or annual_rate < -1 : return 0
    monthly_rate = annual_rate / 12
    periods = int(years * 12)
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
    pmt = npf.pmt(monthly_rate, periods_total, -loan_amount)
    # Using FV formula: FV(rate, nper, pmt, pv)
    remaining_balance = npf.fv(monthly_rate, periods_passed, pmt, -loan_amount)
    return remaining_balance if remaining_balance > 0 else 0


def calculate_interest_paid_over_period(loan_amount, annual_rate, term_years, start_year, end_year):
    """Calculates total interest paid between start_year (exclusive) and end_year (inclusive)."""
    if loan_amount <= 0 or start_year >= end_year: return 0
    monthly_rate = annual_rate / 12
    periods_total = int(term_years * 12)

    total_interest = 0
    # ipmt periods are 1-based
    start_period = int(start_year * 12) + 1
    end_period = int(end_year * 12) + 1
    # Ensure periods are within the valid range [1, periods_total]
    start_period = max(1, start_period)
    end_period = min(periods_total + 1, end_period) # +1 because range is exclusive at end
    if start_period >= end_period: return 0

    try:
        # Calculate interest for each period in the range
        periods_array = np.arange(start_period, end_period)
        interest_payments = npf.ipmt(monthly_rate, periods_array, periods_total, pv=-loan_amount)
        total_interest = np.sum(interest_payments)
    except Exception as e:
         # Display error in the app for debugging
         st.error(f"Error calculating interest (Year {start_year+1}-{end_year}): {e}")
         st.error(f"Inputs: rate={monthly_rate}, per={periods_array}, nper={periods_total}, pv={-loan_amount}")
         total_interest = 0

    return abs(total_interest) # ipmt returns negative values


# --- Sidebar Inputs ---
st.sidebar.header("Scenario Inputs & Assumptions")

# Property Type Selector
property_type = st.sidebar.selectbox("Property Type", ["Co-op", "Condo"], index=1) # Default to Condo

# --- Define Time Horizon EARLY ---
time_horizon_years = st.sidebar.slider("Time Horizon (Years)", min_value=1, max_value=30, value=10, step=1)


# Adjust defaults based on property type
default_closing_costs = 2.5 if property_type == "Co-op" else 4.5
closing_costs_help = "Typical Buyer Closing Costs in NYC: ~1-3% + Mansion Tax for Co-ops, ~3-6% for Condos (incl. Mortgage Recording Tax)."
prop_tax_portion_help = "For Co-ops: Enter % of monthly fees allocated to property tax (from co-op statement). Set to 0 if using 'Separate Annual Tax' field."
separate_prop_tax_help = "For Condos: Enter total annual property tax bill. For Co-ops: Use this to override % calculation if known."
dp_help = "Enter your planned down payment. Note: Co-ops often require minimums of 20-50%+, while condos may allow less based on lender."

# --- Buy & Rent Out Scenario Inputs (Conditional) ---
model_rent_out = False
years_before_renting = 0 # Initialize
vacancy_rate_percent = 0.0
prop_mgmt_fee_percent = 0.0
annual_landlord_costs = 0
land_value_percent = 0.0

if property_type == "Condo":
    st.sidebar.markdown("---")
    model_rent_out = st.sidebar.checkbox("Model 'Buy & Rent Out' Scenario?")
    if model_rent_out:
        st.sidebar.subheader("Buy & Rent Out Inputs")
        max_rent_years = max(1, time_horizon_years - 1)
        default_rent_years = max(1, min(5, max_rent_years))
        years_before_renting = st.sidebar.slider(
            "Years Before Renting Out",
            min_value=1,
            max_value=max_rent_years,
            value=default_rent_years,
            step=1,
            help="How many years you live in the property before renting it out."
        )
        vacancy_rate_percent = st.sidebar.slider("Vacancy Rate (% of Year)", min_value=0.0, max_value=50.0, value=5.0, step=0.5, format="%.1f%%", help="Estimated percentage of the year the property is vacant between tenants.")
        prop_mgmt_fee_percent = st.sidebar.slider("Property Management Fee (% of Rent)", min_value=0.0, max_value=20.0, value=10.0, step=0.5, format="%.1f%%", help="Fee paid to property manager, if any.")
        annual_landlord_costs = st.sidebar.number_input("Extra Annual Landlord Costs ($)", min_value=0, value=1000, step=50, format="%d", help="Additional costs beyond normal maintenance when renting (extra repairs, specific insurance, etc.). Assumed to grow with inflation.")
        land_value_percent = st.sidebar.slider("Land Value (% of Purchase Price)", min_value=0.0, max_value=50.0, value=20.0, step=1.0, format="%.0f%%", help="Estimate for depreciation calculation basis (Building Value = Price - Land Value).")
        st.sidebar.markdown("*(Note: Uses 'Equivalent Monthly Rent' input below as basis for rental income)*")
    st.sidebar.markdown("---")


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
rent_monthly = st.sidebar.number_input("Equivalent Monthly Rent (Year 1)", min_value=100, value=10000, step=100, format="%d", help="Also used as basis for 'Buy & Rent Out' income.")

# Shared Assumptions
st.sidebar.subheader("Market & Time Assumptions")
# Time Horizon defined earlier
property_appreciation_rate_percent = st.sidebar.slider("Avg. Annual Property Appreciation (%)", min_value=-5.0, max_value=15.0, value=3.0, step=0.1, format="%.1f%%")
investment_return_rate_percent = st.sidebar.slider("Avg. Annual Investment Return (%)", min_value=0.0, max_value=15.0, value=7.0, step=0.1, format="%.1f%%")
rent_growth_rate_percent = st.sidebar.slider("Avg. Annual Rent Growth (%)", min_value=0.0, max_value=10.0, value=3.0, step=0.1, format="%.1f%%")
maintenance_growth_rate_percent = st.sidebar.slider(f"Avg. Annual {'Maint./Comm. Charge/Landlord Costs'} Growth (%)", min_value=0.0, max_value=10.0, value=3.0, step=0.1, format="%.1f%%") # Renamed for broader use
selling_costs_percent = st.sidebar.slider("Estimated Selling Costs (% of Future Value)", min_value=0.0, max_value=10.0, value=7.0, step=0.1, format="%.1f%%")

# Tax Inputs (Shared where applicable)
st.sidebar.subheader("Tax Assumptions (Approximate)")
prop_tax_portion_percent = st.sidebar.slider("Property Tax Portion of Monthly Fees (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, format="%.0f%%", help=prop_tax_portion_help, disabled=(property_type=='Condo')) # Disable for Condo
separate_prop_tax_annual = st.sidebar.number_input("Separate Annual Property Tax ($)", min_value=0, value=15000, step=100, format="%d", help=separate_prop_tax_help) # Default value added
marginal_tax_rate_percent = st.sidebar.slider("Marginal Income Tax Rate (%)", min_value=0.0, max_value=60.0, value=40.0, step=0.5, format="%.1f%%", help="Combined Federal + State + Local rate for ordinary income (used for deductions, rental income tax).")
# --- NEW TAX RATE INPUTS ---
ltcg_tax_rate_percent = st.sidebar.slider("Long-Term Capital Gains Tax Rate (%)", min_value=0.0, max_value=50.0, value=28.0, step=0.1, format="%.1f%%", help="Combined Federal + State + Local rate for LTCG (property sale & investments). E.g., 20% Fed + ~8% NY.")
recapture_tax_rate_percent = st.sidebar.slider("Depreciation Recapture Tax Rate (%)", min_value=0.0, max_value=50.0, value=25.0, step=0.1, format="%.1f%%", help="Tax rate on recaptured depreciation when selling rental property (often capped federally).")
# --- END NEW TAX RATE INPUTS ---
standard_deduction = st.sidebar.number_input("Standard Deduction ($)", min_value=0, value=30000, step=100, format="%d", help="Your estimated standard deduction (e.g., ~30k for MFJ in 2025).")
mortgage_interest_limit = st.sidebar.number_input("Mortgage Interest Deduction Limit ($)", min_value=0, value=750000, step=1000, format="%d", help="For Primary Residence interest deduction.")
salt_cap = st.sidebar.number_input("SALT Deduction Cap ($)", min_value=0, value=10000, step=500, format="%d", help="For Primary Residence State/Local/Property Tax deduction.")
# inflation_rate_percent = st.sidebar.slider("Assumed Inflation Rate (%)", min_value=0.0, max_value=10.0, value=3.0, step=0.1, format="%.1f%%", help="Used for growing landlord costs etc. (Using Maint Growth for now)") # Added for clarity, using maint growth for now

# --- Convert percentages to decimals ---
down_payment_rate = down_payment_percent / 100.0
interest_rate = interest_rate_percent / 100.0
closing_costs_rate = closing_costs_percent / 100.0
property_appreciation_rate = property_appreciation_rate_percent / 100.0
investment_return_rate = investment_return_rate_percent / 100.0
rent_growth_rate = rent_growth_rate_percent / 100.0
maintenance_growth_rate = maintenance_growth_rate_percent / 100.0 # Used for fees & landlord costs growth
selling_costs_rate = selling_costs_percent / 100.0
prop_tax_portion_rate = prop_tax_portion_percent / 100.0
marginal_tax_rate = marginal_tax_rate_percent / 100.0
# --- NEW TAX RATE DECIMALS ---
ltcg_tax_rate = ltcg_tax_rate_percent / 100.0
recapture_tax_rate = recapture_tax_rate_percent / 100.0
# --- END NEW TAX RATE DECIMALS ---
vacancy_rate = vacancy_rate_percent / 100.0
prop_mgmt_fee_rate = prop_mgmt_fee_percent / 100.0
land_value_rate = land_value_percent / 100.0
# inflation_rate = inflation_rate_percent / 100.0 # Using maintenance_growth_rate for now

# --- Shared Initial Calculations ---
down_payment_amount = home_price * down_payment_rate
loan_amount = home_price - down_payment_amount
closing_costs_amount = home_price * closing_costs_rate
initial_cash_outlay = down_payment_amount + closing_costs_amount
p_and_i = 0
if loan_amount > 0 and interest_rate >= 0 and loan_term_years > 0:
    if interest_rate / 12 >= 0:
       try:
           p_and_i = npf.pmt(interest_rate / 12, loan_term_years * 12, -loan_amount)
       except ValueError as e:
           st.error(f"Error calculating P&I: {e}. Check inputs.")
           p_and_i = 0
    else:
        p_and_i = 0


# --- Scenario 1: Buying & Occupying ---
buy_occupy_net_financial_gain = 0
buy_occupy_avg_monthly_net_cost = 0
buy_occupy_net_equity_after_tax = 0 # Initialize
avg_monthly_buy_cost_gross_occupy = 0 # Initialize
avg_monthly_tax_saving_buy_occupy = 0 # Initialize
avg_monthly_p_and_i = 0 # Initialize
avg_monthly_fees_occupy = 0 # Initialize
avg_monthly_prop_tax_occupy = 0 # Initialize
total_capital_gains_tax_buy_occupy = 0 # Initialize
# Calculate Year 1 Property Tax (used in loop)
total_prop_tax_y1_buy = 0
if property_type == "Co-op":
    prop_tax_from_maint_y1 = (monthly_fees * 12) * prop_tax_portion_rate
    total_prop_tax_y1_buy = prop_tax_from_maint_y1 if separate_prop_tax_annual == 0 else separate_prop_tax_annual
elif property_type == "Condo":
    total_prop_tax_y1_buy = separate_prop_tax_annual

# Calculate average tax saving and net cost for Buy & Occupy
total_tax_savings_buy_occupy = 0
cumulative_gross_costs_buy_occupy = 0
cumulative_fees_buy_occupy = 0
cumulative_prop_tax_buy_occupy = 0
if time_horizon_years > 0:
    current_fees = monthly_fees
    current_prop_tax = total_prop_tax_y1_buy
    for year in range(1, int(time_horizon_years) + 1):
        # Costs for the year
        annual_fees = current_fees * 12
        annual_p_and_i = p_and_i * 12 if p_and_i > 0 else 0
        annual_prop_tax = current_prop_tax # Use value that grows year over year
        gross_cost_this_year = annual_p_and_i + annual_fees
        if property_type == "Condo": # Add separate tax for condo gross cost
            gross_cost_this_year += annual_prop_tax
        cumulative_gross_costs_buy_occupy += gross_cost_this_year
        cumulative_fees_buy_occupy += annual_fees
        cumulative_prop_tax_buy_occupy += annual_prop_tax

        # Tax Savings for the year (Primary Residence Rules)
        tax_saving_this_year = 0
        if marginal_tax_rate > 0 and loan_amount > 0:
            interest_paid_this_year = calculate_interest_paid_over_period(loan_amount, interest_rate, loan_term_years, year - 1, year)
            deductible_interest_ratio = min(1.0, mortgage_interest_limit / loan_amount) if loan_amount > mortgage_interest_limit > 0 else 1.0
            deductible_interest_this_year = interest_paid_this_year * deductible_interest_ratio
            salt_deduction_this_year = min(annual_prop_tax, salt_cap)
            itemized_deductions_this_year = deductible_interest_this_year + salt_deduction_this_year
            tax_saving_this_year = max(0, itemized_deductions_this_year - standard_deduction) * marginal_tax_rate
        total_tax_savings_buy_occupy += tax_saving_this_year

        # Increment costs for next year
        current_fees *= (1 + maintenance_growth_rate)
        current_prop_tax *= (1 + maintenance_growth_rate) # Assume tax grows at same rate

    avg_annual_tax_saving_buy_occupy = total_tax_savings_buy_occupy / time_horizon_years if time_horizon_years > 0 else 0
    avg_monthly_tax_saving_buy_occupy = avg_annual_tax_saving_buy_occupy / 12
    avg_monthly_buy_cost_gross_occupy = (cumulative_gross_costs_buy_occupy / time_horizon_years) / 12 if time_horizon_years > 0 else 0
    buy_occupy_avg_monthly_net_cost = avg_monthly_buy_cost_gross_occupy - avg_monthly_tax_saving_buy_occupy

    # Calculate average components for display
    avg_monthly_p_and_i = p_and_i if time_horizon_years > 0 else 0
    avg_monthly_fees_occupy = (cumulative_fees_buy_occupy / time_horizon_years) / 12 if time_horizon_years > 0 else 0
    avg_monthly_prop_tax_occupy = (cumulative_prop_tax_buy_occupy / time_horizon_years) / 12 if time_horizon_years > 0 else 0


# Future Outcomes for Buy & Occupy
future_property_value = home_price * ((1 + property_appreciation_rate) ** time_horizon_years)
loan_balance_future = calculate_loan_balance(loan_amount, interest_rate, loan_term_years, time_horizon_years)
selling_costs_amount = future_property_value * selling_costs_rate
buy_occupy_net_equity_before_tax = future_property_value - loan_balance_future - selling_costs_amount
# Apply capital gains tax for primary residence
buy_basis = home_price + closing_costs_amount # Simplified basis
capital_gain_buy_occupy = max(0, future_property_value - selling_costs_amount - buy_basis)
primary_residence_exclusion = 500000 # Assume MFJ
# Use updated exclusion logic (always check 2 of last 5)
years_owned_last_5_buy_occupy = min(5, time_horizon_years)
exclusion_applies_buy_occupy = years_owned_last_5_buy_occupy >= 2 # Assumes occupied the whole time
applicable_exclusion_buy_occupy = primary_residence_exclusion if exclusion_applies_buy_occupy else 0
taxable_gain_buy_occupy = max(0, capital_gain_buy_occupy - applicable_exclusion_buy_occupy)
total_capital_gains_tax_buy_occupy = taxable_gain_buy_occupy * ltcg_tax_rate # Use LTCG rate
buy_occupy_net_equity_after_tax = buy_occupy_net_equity_before_tax - total_capital_gains_tax_buy_occupy
buy_occupy_net_financial_gain = buy_occupy_net_equity_after_tax - initial_cash_outlay


# --- Scenario 2: Renting & Investing ---
rent_invest_net_financial_gain = 0
initial_investment_rent = initial_cash_outlay
avg_monthly_rent = calculate_average_monthly_value(rent_monthly, rent_growth_rate, time_horizon_years)
# --- UPDATE: Use GROSS cost for comparison ---
avg_monthly_investment_rent = max(0, avg_monthly_buy_cost_gross_occupy - avg_monthly_rent)
# --- END UPDATE ---
fv_initial_investment_rent = calculate_fv_lump_sum(initial_investment_rent, investment_return_rate, time_horizon_years)
fv_monthly_investments_rent = calculate_fv_annuity(avg_monthly_investment_rent, investment_return_rate, time_horizon_years)
total_fv_investments_rent = fv_initial_investment_rent + fv_monthly_investments_rent
# Consider taxes on investment gains
total_principal_invested = initial_investment_rent + (avg_monthly_investment_rent * 12 * time_horizon_years)
investment_gain = max(0, total_fv_investments_rent - total_principal_invested)
# Use new LTCG tax rate for investment gains
investment_tax = investment_gain * ltcg_tax_rate
total_fv_investments_after_tax = total_fv_investments_rent - investment_tax
rent_invest_net_financial_gain = total_fv_investments_after_tax - initial_investment_rent


# --- Scenario 3: Buying & Renting Out (Condo Only) ---
buy_rent_out_net_financial_gain = 0
buy_rent_out_net_equity_after_sale_display = 0 # For display
buy_rent_out_cumulative_rental_cash_flow_display = 0 # For display
# --- Initialize variables for detailed breakdown ---
buy_rent_out_total_tax_savings_occupied = 0
buy_rent_out_cumulative_rental_cash_flow_pre_tax = 0
buy_rent_out_cumulative_rental_tax = 0
buy_rent_out_total_depreciation_taken = 0
buy_rent_out_depreciation_recapture_tax = 0
buy_rent_out_capital_gain_on_sale = 0
buy_rent_out_applicable_exclusion = 0
buy_rent_out_taxable_capital_gain = 0
buy_rent_out_capital_gains_tax_on_sale = 0
buy_rent_out_total_tax_on_sale = 0
# --- End Initialize ---

if property_type == "Condo" and model_rent_out:
    total_tax_savings_buy_rent_occupied_phase = 0 # Track savings only during occupied phase
    cumulative_rental_net_cash_flow_after_tax = 0
    total_depreciation_taken = 0
    building_basis = home_price * (1 - land_value_rate)
    annual_depreciation = building_basis / 27.5 if building_basis > 0 else 0

    current_fees_rent = monthly_fees
    current_prop_tax_rent = total_prop_tax_y1_buy # Start with the same tax
    current_landlord_costs = annual_landlord_costs
    current_rental_income_monthly = rent_monthly # Use the rent input as basis

    for year in range(1, int(time_horizon_years) + 1):
        # Determine phase
        is_owner_occupied_phase = year <= years_before_renting

        # Calculate costs for the year
        annual_fees = current_fees_rent * 12
        annual_p_and_i = p_and_i * 12 if p_and_i > 0 else 0
        annual_prop_tax = current_prop_tax_rent

        # Calculate interest paid this year
        interest_paid_this_year = calculate_interest_paid_over_period(loan_amount, interest_rate, loan_term_years, year - 1, year)

        if is_owner_occupied_phase:
            # --- Owner-Occupied Phase ---
            # Tax Savings (Primary Residence Rules)
            tax_saving_this_year = 0
            if marginal_tax_rate > 0 and loan_amount > 0:
                deductible_interest_ratio = min(1.0, mortgage_interest_limit / loan_amount) if loan_amount > mortgage_interest_limit > 0 else 1.0
                deductible_interest_this_year = interest_paid_this_year * deductible_interest_ratio
                salt_deduction_this_year = min(annual_prop_tax, salt_cap)
                itemized_deductions_this_year = deductible_interest_this_year + salt_deduction_this_year
                tax_saving_this_year = max(0, itemized_deductions_this_year - standard_deduction) * marginal_tax_rate
            total_tax_savings_buy_rent_occupied_phase += tax_saving_this_year # Accumulate savings during occupied phase

        else:
            # --- Rented-Out Phase ---
            # Calculate Rental Income & Expenses
            annual_gross_rent = current_rental_income_monthly * 12
            vacancy_loss = annual_gross_rent * vacancy_rate
            management_fees = (annual_gross_rent - vacancy_loss) * prop_mgmt_fee_rate
            effective_rent = annual_gross_rent - vacancy_loss
            landlord_costs_this_year = current_landlord_costs

            # Calculate Taxable Rental Income/Loss
            depreciation_this_year = annual_depreciation if (year - years_before_renting) <= 27.5 else 0
            total_depreciation_taken += depreciation_this_year # Track total depreciation

            rental_expenses_for_tax = (interest_paid_this_year +
                                       annual_prop_tax +
                                       annual_fees + # Common charges
                                       management_fees +
                                       landlord_costs_this_year +
                                       depreciation_this_year) # Include depreciation for tax calc

            taxable_net_rental_income = effective_rent - rental_expenses_for_tax

            # Tax on rental income (Simplified: taxed at marginal rate, ignore PAL rules)
            rental_tax = taxable_net_rental_income * marginal_tax_rate
            buy_rent_out_cumulative_rental_tax += rental_tax # Store for details

            # Calculate Net Cash Flow for the year (after tax on rental income)
            cash_expenses = (management_fees +
                             landlord_costs_this_year +
                             annual_fees + # Common charges
                             annual_prop_tax +
                             annual_p_and_i) # Principal and Interest are cash outflows

            net_cash_flow_this_year_pre_tax = effective_rent - cash_expenses # Store pre-tax for details
            buy_rent_out_cumulative_rental_cash_flow_pre_tax += net_cash_flow_this_year_pre_tax

            net_cash_flow_this_year = net_cash_flow_this_year_pre_tax - rental_tax
            cumulative_rental_net_cash_flow_after_tax += net_cash_flow_this_year

        # Increment costs/income for next year
        current_fees_rent *= (1 + maintenance_growth_rate)
        current_prop_tax_rent *= (1 + maintenance_growth_rate) # Assume tax grows at same rate
        current_landlord_costs *= (1 + maintenance_growth_rate) # Assume landlord costs grow
        current_rental_income_monthly *= (1 + rent_growth_rate)

    # --- Sale Calculation for Buy & Rent Out ---
    net_equity_before_tax = future_property_value - loan_balance_future - selling_costs_amount

    # Calculate Taxes on Sale (Simplified)
    # 1. Depreciation Recapture Tax
    # Use new recapture tax rate
    buy_rent_out_depreciation_recapture_tax = total_depreciation_taken * recapture_tax_rate

    # 2. Capital Gains Tax
    adjusted_basis = home_price + closing_costs_amount
    total_gain_on_sale = max(0, future_property_value - selling_costs_amount - adjusted_basis)
    buy_rent_out_capital_gain_on_sale = total_gain_on_sale # Store for details
    capital_gain_portion = max(0, total_gain_on_sale - total_depreciation_taken)

    # Use improved exclusion logic
    years_occupied = years_before_renting
    years_owned_last_5 = min(5, time_horizon_years)
    start_year_of_last_5 = time_horizon_years - years_owned_last_5
    owner_years_last_5 = max(0, min(years_occupied, time_horizon_years) - start_year_of_last_5)
    exclusion_applies = owner_years_last_5 >= 2

    buy_rent_out_applicable_exclusion = primary_residence_exclusion if exclusion_applies else 0
    buy_rent_out_taxable_capital_gain = max(0, capital_gain_portion - buy_rent_out_applicable_exclusion)
    # Use new LTCG tax rate
    buy_rent_out_capital_gains_tax_on_sale = buy_rent_out_taxable_capital_gain * ltcg_tax_rate

    # Total Tax on Sale
    buy_rent_out_total_tax_on_sale = buy_rent_out_depreciation_recapture_tax + buy_rent_out_capital_gains_tax_on_sale

    # Net Proceeds After Tax
    net_proceeds_after_tax = net_equity_before_tax - buy_rent_out_total_tax_on_sale
    buy_rent_out_net_equity_after_sale_display = net_proceeds_after_tax # For display

    # Final Net Financial Gain
    buy_rent_out_total_tax_savings_occupied = total_tax_savings_buy_rent_occupied_phase # Store for details
    buy_rent_out_net_financial_gain = (net_proceeds_after_tax +
                                       cumulative_rental_net_cash_flow_after_tax +
                                       buy_rent_out_total_tax_savings_occupied - # Add tax savings from owner occupied period
                                       initial_cash_outlay)
    buy_rent_out_cumulative_rental_cash_flow_display = cumulative_rental_net_cash_flow_after_tax # For display
    buy_rent_out_total_depreciation_taken = total_depreciation_taken # Store for display


# --- Display Results ---

st.header("Comparison Summary")
st.markdown(f"*(Based on a **{time_horizon_years:.0f}-year** time horizon for a **{property_type}**)*")

# Use 3 columns if the third scenario is active
num_cols = 3 if (property_type == "Condo" and model_rent_out) else 2
cols = st.columns(num_cols)

with cols[0]:
    st.subheader("Buying & Occupying")
    st.metric(label="Est. Net Financial Gain", value=f"${buy_occupy_net_financial_gain:,.0f}")
    st.markdown("*(Future Net Equity After Tax - Initial Cash Outlay)*")

with cols[1]:
    st.subheader("Renting & Investing")
    st.metric(label="Est. Net Financial Gain", value=f"${rent_invest_net_financial_gain:,.0f}")
    st.markdown("*(Future Investment Value After Tax - Initial Investment)*")

if property_type == "Condo" and model_rent_out:
    with cols[2]:
        st.subheader("Buying & Renting Out")
        st.metric(label="Est. Net Financial Gain", value=f"${buy_rent_out_net_financial_gain:,.0f}")
        st.markdown("*(Net Proceeds After Tax + Net Rental Cash Flow + Occupied Tax Savings - Initial Cash Outlay)*") # Updated formula description


st.header(" ") # Spacer

# Conclusion - Compare all active scenarios
st.subheader("Conclusion")

scenarios = {
    "Buying & Occupying": buy_occupy_net_financial_gain,
    "Renting & Investing": rent_invest_net_financial_gain
}
if property_type == "Condo" and model_rent_out:
    scenarios["Buying & Renting Out"] = buy_rent_out_net_financial_gain

# Filter out scenarios that weren't calculated (though all should be unless error)
active_scenarios = {k: v for k, v in scenarios.items() if v is not None} # Check for None if errors occur

if not active_scenarios:
    st.warning("No scenarios calculated successfully.")
else:
    # Find the best scenario based on the highest net financial gain
    best_scenario = max(active_scenarios, key=active_scenarios.get)
    best_value = active_scenarios[best_scenario]

    # Check if results are close (e.g., within 5% of the best value)
    is_close = False
    close_threshold = 0.05
    if len(active_scenarios) > 1:
        for name, value in active_scenarios.items():
            if name != best_scenario and best_value != 0 and abs(best_value - value) < abs(best_value * close_threshold):
                is_close = True
                break
            elif name != best_scenario and best_value == 0 and abs(value) < 1000: # Handle zero case
                 is_close = True
                 break

    if is_close:
         st.info(f"The financial outcomes are relatively close. **{best_scenario}** appears slightly better based on these assumptions, but other factors may be more important.")
    else:
        st.success(f"**{best_scenario}** appears to be the most financially beneficial scenario by a significant margin based on these assumptions.")

    # Display values for clarity
    st.write("Estimated Net Financial Gains:")
    sorted_scenarios = sorted(active_scenarios.items(), key=lambda item: item[1], reverse=True)
    for name, value in sorted_scenarios:
        st.write(f"* {name}: **${value:,.0f}**")


st.markdown("---")


# --- Detailed Breakdown ---
st.header("Detailed Breakdown & Assumptions")

# Assumptions Display
with st.expander("Key Assumptions Used", expanded=False):
    # Dynamically build assumptions list
    param_list = [
        "Property Type", "Time Horizon", "Avg. Property Appreciation", "Avg. Investment Return",
        "Avg. Rent Growth", f"Avg. {'Maint./Comm. Charge/Landlord Costs'} Growth", "Property Selling Costs",
        "Marginal Income Tax Rate", "Long-Term Capital Gains Tax Rate", "Depreciation Recapture Tax Rate", # Updated Tax Rates
        "Standard Deduction", "Mortgage Interest Limit (Primary)", "SALT Cap (Primary)"
    ]
    value_list = [
        property_type, f"{time_horizon_years:.0f} Years", f"{property_appreciation_rate:.1%}", f"{investment_return_rate:.1%}",
        f"{rent_growth_rate:.1%}", f"{maintenance_growth_rate:.1%}", f"{selling_costs_rate:.1%}",
        f"{marginal_tax_rate:.1%}", f"{ltcg_tax_rate:.1%}", f"{recapture_tax_rate:.1%}", # Updated Tax Rates
        f"${standard_deduction:,.0f}", f"${mortgage_interest_limit:,.0f}", f"${salt_cap:,.0f}"
    ]
    if property_type == "Condo" and model_rent_out:
         param_list.extend([
             "Years Before Renting Out", "Vacancy Rate", "Property Management Fee",
             "Annual Landlord Costs (Y1)", "Land Value % (for Depreciation)"
         ])
         value_list.extend([
             f"{years_before_renting:.0f}", f"{vacancy_rate:.1%}", f"{prop_mgmt_fee_rate:.1%}",
             f"${annual_landlord_costs:,.0f}", f"{land_value_rate:.0%}"
         ])

    assumptions_data = {"Parameter": param_list, "Value": value_list}
    st.table(pd.DataFrame(assumptions_data))
    st.caption("*Note: Tax calculations simplified (e.g., PAL rules ignored, combined LTCG rates used). Consult tax pro.*")


# Buy & Occupy Scenario Details
with st.expander("Buy & Occupy Scenario Details", expanded=True): # Expanded by default
    st.markdown("##### Upfront Costs")
    st.metric(label="Total Initial Cash Outlay", value=f"${initial_cash_outlay:,.0f}")
    st.caption("Down Payment + Est. Closing Costs")
    # st.markdown(f"* Down Payment: ${down_payment_amount:,.0f} ({down_payment_percent:.1f}%)")
    # st.markdown(f"* Est. Closing Costs: ${closing_costs_amount:,.0f} ({closing_costs_percent:.1f}%)")

    st.markdown("##### Average Monthly Costs (Over Horizon)")
    st.metric(label="Avg. Gross Monthly Cost", value=f"${avg_monthly_buy_cost_gross_occupy:,.0f}")
    st.caption(f"Avg(P&I ${avg_monthly_p_and_i:,.0f} + Fees ${avg_monthly_fees_occupy:,.0f} + Prop Tax ${avg_monthly_prop_tax_occupy:,.0f})")
    st.metric(label="Avg. Monthly Tax Saving", value=f"${avg_monthly_tax_saving_buy_occupy:,.0f}")
    st.caption("Avg annual saving from itemizing (Interest + SALT deductions vs Standard Deduction) / 12")
    st.metric(label="Avg. Net Monthly Cost", value=f"${buy_occupy_avg_monthly_net_cost:,.0f}")
    st.caption(f"Avg Gross Monthly Cost - Avg Monthly Tax Saving")


    st.markdown(f"##### Outcome at End of {time_horizon_years:.0f} Years")
    st.metric(label="Est. Future Property Value", value=f"${future_property_value:,.0f}")
    st.caption(f"Initial Price * (1 + Avg. Appreciation Rate) ^ Years")
    st.metric(label="Est. Remaining Loan Balance", value=f"${loan_balance_future:,.0f}")
    st.caption(f"Calculated based on amortization schedule")
    st.metric(label="Est. Selling Costs", value=f"${selling_costs_amount:,.0f}")
    st.caption(f"Future Property Value * Selling Cost %")
    st.metric(label="Net Equity Before Tax", value=f"${buy_occupy_net_equity_before_tax:,.0f}")
    st.caption(f"Future Value - Loan Balance - Selling Costs")
    st.metric(label="Est. Capital Gains Tax on Sale", value=f"${total_capital_gains_tax_buy_occupy:,.0f}")
    st.caption(f"Taxable Gain (Gain ${capital_gain_buy_occupy:,.0f} - Exclusion ${applicable_exclusion_buy_occupy:,.0f}) * LTCG Rate")
    st.metric(label="Est. Net Equity After Sale & Tax", value=f"${buy_occupy_net_equity_after_tax:,.0f}")
    st.caption(f"Net Equity Before Tax - Est. Capital Gains Tax on Sale")

# Rent & Invest Scenario Details
with st.expander("Rent & Invest Scenario Details", expanded=True): # Expanded by default
    st.markdown("##### Investment Basis")
    st.metric(label="Initial Investment (Funds not used for buying)", value=f"${initial_investment_rent:,.0f}")
    st.caption(f"Equal to Buyer's Initial Cash Outlay")
    st.metric(label="Est. Average Monthly Investment (Based on cost difference)", value=f"${avg_monthly_investment_rent:,.0f}")
    st.caption(f"Max(0, Avg. GROSS Buy Cost ${avg_monthly_buy_cost_gross_occupy:,.0f} - Avg. Rent Cost ${avg_monthly_rent:,.0f})")


    st.markdown(f"##### Investment Outcome after {time_horizon_years:.0f} Years (at {investment_return_rate:.1%} avg. return)")
    st.metric(label="Future Value of Investments (Pre-Tax)", value=f"${total_fv_investments_rent:,.0f}")
    st.caption(f"FV(Initial Investment ${fv_initial_investment_rent:,.0f}) + FV(Monthly Investments ${fv_monthly_investments_rent:,.0f})")
    st.metric(label="Est. Tax on Investment Gains", value=f"${investment_tax:,.0f}")
    st.caption(f"Investment Gain (FV ${total_fv_investments_rent:,.0f} - Principal Invested ${total_principal_invested:,.0f}) * LTCG Rate")
    st.metric(label="Total Future Value of Investments (After Approx. LTCG Tax)", value=f"${total_fv_investments_after_tax:,.0f}")
    st.caption(f"Future Value Pre-Tax - Est. Tax on Investment Gains")



# Buy & Rent Out Scenario Details (Conditional)
if property_type == "Condo" and model_rent_out:
    with st.expander("Buy & Rent Out Scenario Details", expanded=True): # Expanded by default
        st.markdown("##### Upfront Costs")
        st.metric(label="Total Initial Cash Outlay", value=f"${initial_cash_outlay:,.0f}")
        st.caption("Down Payment + Est. Closing Costs")
        # st.markdown(f"* Down Payment: ${down_payment_amount:,.0f} ({down_payment_percent:.1f}%)")
        # st.markdown(f"* Est. Closing Costs: ${closing_costs_amount:,.0f} ({closing_costs_percent:.1f}%)")

        st.markdown(f"##### Owner Occupied Period ({years_before_renting:.0f} Years)")
        st.metric(label="Total Tax Savings During Occupancy", value=f"${buy_rent_out_total_tax_savings_occupied:,.0f}")
        st.caption("Sum of annual tax savings from itemizing deductions (Interest + SALT vs Standard Deduction)")


        st.markdown(f"##### Rental Period ({max(0, time_horizon_years - years_before_renting):.0f} Years)") # Ensure non-negative years
        st.metric(label="Cumulative Net Rental Cash Flow (Pre-Tax)", value=f"${buy_rent_out_cumulative_rental_cash_flow_pre_tax:,.0f}")
        st.caption("Sum over rental years of: (Effective Rent - All Cash Expenses [P&I, Fees, Prop Tax, Mgmt, Landlord Costs])")
        st.metric(label="Cumulative Tax on Rental Income/Loss", value=f"${buy_rent_out_cumulative_rental_tax:,.0f}")
        st.caption("Sum over rental years of: (Taxable Rental Income/Loss * Marginal Income Tax Rate)")
        st.metric(label="Cumulative Net Rental Cash Flow (After Tax)", value=f"${buy_rent_out_cumulative_rental_cash_flow_display:,.0f}")
        st.caption("Cumulative Pre-Tax Cash Flow - Cumulative Tax on Rental Income/Loss")
        st.metric(label="Total Estimated Depreciation Taken", value=f"${buy_rent_out_total_depreciation_taken:,.0f}")
        st.caption("Sum of annual depreciation claimed during rental years")


        st.markdown(f"##### Outcome at End of {time_horizon_years:.0f} Years")
        st.metric(label="Est. Future Property Value", value=f"${future_property_value:,.0f}")
        # st.caption(f"Initial Price * (1 + Avg. Appreciation Rate) ^ Years") # Redundant
        st.metric(label="Est. Remaining Loan Balance", value=f"${loan_balance_future:,.0f}")
        # st.caption(f"Calculated based on amortization schedule") # Redundant
        st.metric(label="Est. Selling Costs", value=f"${selling_costs_amount:,.0f}")
        # st.caption(f"Future Property Value * Selling Cost %") # Redundant
        st.metric(label="Net Equity Before Tax", value=f"${net_equity_before_tax:,.0f}")
        st.caption(f"Future Value - Loan Balance - Selling Costs")
        st.metric(label="Est. Total Tax on Sale", value=f"${buy_rent_out_total_tax_on_sale:,.0f}")
        st.caption(f"Depreciation Recapture Tax (${buy_rent_out_depreciation_recapture_tax:,.0f}) + Capital Gains Tax (${buy_rent_out_capital_gains_tax_on_sale:,.0f})")
        st.metric(label="Est. Net Equity After Sale & Tax", value=f"${buy_rent_out_net_equity_after_sale_display:,.0f}")
        st.caption("(Net Equity Before Tax - Total Tax on Sale)")