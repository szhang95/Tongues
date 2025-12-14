from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from shiny import App, ui, render, reactive, req
import refinitiv.data as rd
import plotly.graph_objects as go
from scipy import interpolate


# ---------- helpers ----------
def get_next_friday(d: datetime.date) -> datetime.date:
    return d + timedelta(days=(4 - d.weekday()) % 7)


def get_fourth_friday(d: datetime.date) -> datetime.date:
    return get_next_friday(d) + timedelta(weeks=3)


today = datetime.today().date()
default_min_expiry = get_next_friday(today)
default_max_expiry = today + timedelta(days=120)


def build_surface_df(df: pd.DataFrame, spot: float) -> pd.DataFrame:
    df = df.copy()
    df["Bid"] = pd.to_numeric(df.get("Bid"), errors="coerce")
    df["Ask"] = pd.to_numeric(df.get("Ask"), errors="coerce")
    df["Last"] = pd.to_numeric(df.get("Last"), errors="coerce")

    df["mid"] = df[["Bid", "Ask"]].mean(axis=1)
    df.loc[df["mid"].isna(), "mid"] = df["Last"]

    df["ExpiryDate"] = pd.to_datetime(df["ExpiryDate"])
    now = pd.Timestamp.now()
    df["T"] = (df["ExpiryDate"] - now).dt.days / 365.0
    df["K"] = df["StrikePrice"]
    df["S"] = spot

    return df[["RIC", "K", "T", "mid", "S", "StrikePrice", "ExpiryDate", "CallPutOption"]]


def compute_implied_r(row):
    try:
        if row["T"] <= 0 or row["K"] <= 0:
            return np.nan

        numerator = row["S"] - (row["C_mid"] - row["P_mid"])
        if numerator <= 0:
            return np.nan

        r = -(1 / row["T"]) * np.log(numerator / row["K"])
        return r
    except:
        return np.nan


def get_strategy_summary(signal: str) -> str:
    if "Sell synthetic" in signal:
        return "Sell Call+Buy Put+Buy Stock"
    elif "Buy synthetic" in signal:
        return "Buy Call+Sell Put+Short Stock"
    return signal


def get_strategy_details(row) -> dict:
    strategy_type = get_strategy_summary(row['signal'])
    r_diff_pct = row['r_diff'] * 100

    if strategy_type == "Sell Call+Buy Put+Buy Stock":
        return {
            "type": "Reverse Conversion Arbitrage",
            "summary": "The synthetic stock (long call + short put) is overpriced relative to actual stock.",
            "positions": [
                f"• SELL Call @ ${row['K']:.0f} strike for ${row['C_mid']:.2f}",
                f"• BUY Put @ ${row['K']:.0f} strike for ${row['P_mid']:.2f}",
                f"• BUY underlying stock @ ${row['S']:.2f}"
            ],
            "rationale": f"The implied rate ({row['implied_r'] * 100:.2f}%) exceeds the risk-free rate by {abs(r_diff_pct):.2f}%, indicating mispricing.",
            "profit": f"Net credit of ${row['C_mid'] - row['P_mid']:.2f} + dividend yield over {row['T'] * 365:.0f} days",
            "risk": "• Execution risk across 3 legs\n• Pin risk at expiration\n• Early assignment on short call\n• Transaction costs may erode profit",
            "recommendation": "Execute if net arbitrage exceeds 0.5% annualized after costs." if abs(
                r_diff_pct) > 0.5 else "Profit margin may be too thin after transaction costs."
        }
    else:
        return {
            "type": "Conversion Arbitrage",
            "summary": "The synthetic stock (long call + short put) is underpriced relative to actual stock.",
            "positions": [
                f"• BUY Call @ ${row['K']:.0f} strike for ${row['C_mid']:.2f}",
                f"• SELL Put @ ${row['K']:.0f} strike for ${row['P_mid']:.2f}",
                f"• SELL (short) underlying stock @ ${row['S']:.2f}"
            ],
            "rationale": f"The implied rate ({row['implied_r'] * 100:.2f}%) is below the risk-free rate by {abs(r_diff_pct):.2f}%, indicating mispricing.",
            "profit": f"Net credit of ${row['S'] - row['K']:.2f} + interest earned over {row['T'] * 365:.0f} days",
            "risk": "• Requires margin for short stock\n• Hard to borrow costs\n• Dividend risk on short stock\n• Early assignment on short put\n• Transaction costs",
            "recommendation": "Execute if net arbitrage exceeds 1% annualized after costs, and stock is easy to borrow." if abs(
                r_diff_pct) > 1 else "Consider borrowing costs and margin requirements before executing."
        }


def analyze_arbitrage(surface_df: pd.DataFrame, risk_free_rate: float = 0.05, threshold: float = 0.005):
    calls = surface_df[surface_df["CallPutOption"] == "Call"].copy()
    puts = surface_df[surface_df["CallPutOption"] == "Put"].copy()

    merged = calls.merge(
        puts,
        on=["K", "T", "S", "ExpiryDate"],
        suffixes=("_call", "_put")
    )

    merged["C_mid"] = merged["mid_call"]
    merged["P_mid"] = merged["mid_put"]
    merged["implied_r"] = merged.apply(compute_implied_r, axis=1)
    merged["r_diff"] = merged["implied_r"] - risk_free_rate

    merged["signal"] = None
    merged.loc[merged["r_diff"] > threshold, "signal"] = "Sell synthetic, buy stock"
    merged.loc[merged["r_diff"] < -threshold, "signal"] = "Buy synthetic, short stock"

    return merged[merged["signal"].notna()]


def calculate_execution_costs(row, contracts, commission, slippage_pct, risk_free_rate):
    multiplier = 100

    strike = row['K']
    spot = row['S']
    call_mid = row['C_mid']
    put_mid = row['P_mid']
    days_to_expiry = row['T'] * 365
    T = row['T']
    implied_rate = row['implied_r']
    rate_diff = row['r_diff']

    strategy_type = get_strategy_summary(row['signal'])

    call_value = call_mid * contracts * multiplier
    put_value = put_mid * contracts * multiplier
    stock_value = spot * contracts * multiplier
    strike_value = strike * contracts * multiplier

    total_commission = commission * 3
    total_notional = call_value + put_value + stock_value
    slippage_cost = total_notional * (slippage_pct / 100)
    total_costs = total_commission + slippage_cost

    if strategy_type == "Sell Call+Buy Put+Buy Stock":
        call_credit = call_value
        put_debit = put_value
        stock_debit = stock_value

        option_net = call_credit - put_debit
        initial_outflow = stock_debit - option_net + total_costs

        expiry_inflow = strike_value
        expected_outflow_with_interest = initial_outflow * np.exp(risk_free_rate * T)
        net_pnl = expiry_inflow - expected_outflow_with_interest

        theoretical_profit = rate_diff * strike_value * T
        required_margin = stock_value * 0.5
        capital_employed = initial_outflow

        initial_cash = -initial_outflow
        expiry_cash = expiry_inflow

    else:
        call_debit = call_value
        put_credit = put_value
        stock_credit = stock_value

        option_net = put_credit - call_debit
        initial_inflow = stock_credit + option_net - total_costs

        expiry_outflow = strike_value
        expected_inflow_with_interest = initial_inflow * np.exp(risk_free_rate * T)
        net_pnl = expected_inflow_with_interest - expiry_outflow

        theoretical_profit = abs(rate_diff) * strike_value * T
        required_margin = stock_value * 1.5
        capital_employed = required_margin

        initial_cash = initial_inflow
        expiry_cash = -expiry_outflow

    roi = (theoretical_profit / capital_employed * 100) if capital_employed > 0 else 0
    annualized_return = (roi * 365 / days_to_expiry) if days_to_expiry > 0 else 0

    best_case = theoretical_profit * 1.3
    worst_case = theoretical_profit * 0.7

    return {
        'strategy_type': strategy_type,
        'strike': strike,
        'spot': spot,
        'call_mid': call_mid,
        'put_mid': put_mid,
        'call_value': call_value,
        'put_value': put_value,
        'stock_value': stock_value,
        'strike_value': strike_value,
        'option_net': option_net,
        'initial_cash': initial_cash,
        'expiry_cash': expiry_cash,
        'total_commission': total_commission,
        'slippage_cost': slippage_cost,
        'total_costs': total_costs,
        'net_pnl': net_pnl,
        'theoretical_profit': theoretical_profit,
        'required_margin': required_margin,
        'capital_employed': capital_employed,
        'roi': roi,
        'annualized_return': annualized_return,
        'best_case': best_case,
        'worst_case': worst_case,
        'days_to_expiry': days_to_expiry,
        'implied_rate': implied_rate,
        'rate_diff': rate_diff,
        'risk_free_rate': risk_free_rate
    }


# ---------- UI ----------
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Home",
        ui.include_css(Path(__file__).with_name("custom.css")),
        ui.div(
            {"class": "hero-section"},
            ui.div(
                {"class": "hero-content"},
                ui.h1("DevilTongues", {"class": "hero-title"}),
                ui.p("Real-Time Synthetic Bond Arbitrage Detection Platform", {"class": "hero-subtitle"}),
                ui.div(
                    {"class": "hero-badges"},
                    ui.span("Python", {"class": "badge"}),
                    ui.span("LSEG Refinitiv", {"class": "badge"}),
                    ui.span("Options Trading", {"class": "badge"}),
                    ui.span("Quantitative Finance", {"class": "badge"}),
                )
            )
        ),
        ui.div(
            {"class": "content-container"},
            ui.div(
                {"class": "info-card"},
                ui.h2("What is DevilTongues?", {"class": "card-title"}),
                ui.p(
                    "DevilTongues identifies arbitrage opportunities in synthetic bonds through real-time put-call parity analysis. "
                    "By connecting to LSEG market data, we calculate implied risk-free rates and flag profitable conversion strategies.",
                    {"class": "card-text"}
                ),
            ),
            ui.div(
                {"class": "feature-grid"},
                ui.div(
                    {"class": "feature-card"},
                    ui.div("📊", {"class": "feature-icon"}),
                    ui.h3("Real-Time Data", {"class": "feature-title"}),
                    ui.p("Live spot prices and options chains from LSEG Refinitiv", {"class": "feature-text"}),
                ),
                ui.div(
                    {"class": "feature-card"},
                    ui.div("🔍", {"class": "feature-icon"}),
                    ui.h3("Arbitrage Detection", {"class": "feature-title"}),
                    ui.p("Automated put-call parity analysis with customizable thresholds", {"class": "feature-text"}),
                ),
                ui.div(
                    {"class": "feature-card"},
                    ui.div("💡", {"class": "feature-icon"}),
                    ui.h3("Strategy Analysis", {"class": "feature-title"}),
                    ui.p("Detailed breakdowns with risk assessments and recommendations", {"class": "feature-text"}),
                ),
                ui.div(
                    {"class": "feature-card"},
                    ui.div("📈", {"class": "feature-icon"}),
                    ui.h3("3D Visualization", {"class": "feature-title"}),
                    ui.p("Interactive surface plots of implied rate term structures", {"class": "feature-text"}),
                ),
            ),
            ui.div(
                {"class": "info-card"},
                ui.h2("How to Use", {"class": "card-title"}),
                ui.div(
                    {"class": "steps-container"},
                    ui.div(
                        {"class": "step"},
                        ui.div("1", {"class": "step-number"}),
                        ui.div(
                            ui.h4("Fetch Market Data", {"class": "step-title"}),
                            ui.p("Go to 'Market Data' tab, select an underlying (AAPL, MSFT, etc.), and fetch live spot prices", {"class": "step-text"}),
                        )
                    ),
                    ui.div(
                        {"class": "step"},
                        ui.div("2", {"class": "step-number"}),
                        ui.div(
                            ui.h4("Scan Options Chain", {"class": "step-title"}),
                            ui.p("Set strike range, expiry dates, and scan the options chain from LSEG", {"class": "step-text"}),
                        )
                    ),
                    ui.div(
                        {"class": "step"},
                        ui.div("3", {"class": "step-number"}),
                        ui.div(
                            ui.h4("Analyze Arbitrage", {"class": "step-title"}),
                            ui.p("Set risk-free rate and threshold, then analyze for arbitrage opportunities", {"class": "step-text"}),
                        )
                    ),
                    ui.div(
                        {"class": "step"},
                        ui.div("4", {"class": "step-number"}),
                        ui.div(
                            ui.h4("Review Results", {"class": "step-title"}),
                            ui.p("View detected opportunities in 'Analysis' tab, calculate execution costs, and visualize 3D surfaces", {"class": "step-text"}),
                        )
                    ),
                )
            ),
            ui.div(
                {"class": "authors-card"},
                ui.h2("Authors", {"class": "card-title"}),
                ui.div(
                    {"class": "authors-grid"},
                    ui.div(
                        {"class": "author"},
                        ui.div("🍍", {"class": "author-icon"}),
                        ui.h4("Sunny Zhang", {"class": "author-name"}),
                        ui.p("Duke University", {"class": "author-affiliation"}),
                    ),
                    ui.div(
                        {"class": "author"},
                        ui.div("🧄", {"class": "author-icon"}),
                        ui.h4("Victoria Li", {"class": "author-name"}),
                        ui.p("Duke University", {"class": "author-affiliation"}),
                    ),
                )
            ),
        ),
    ),
    ui.nav_panel(
        "Market Data",
        ui.div(
            {"class": "page-container"},
            ui.h1("Market Data Fetching", {"class": "page-title"}),
            ui.div(
                {"class": "control-grid"},
                ui.div(
                    {"class": "control-section"},
                    ui.h3("1. Select Underlying", {"class": "section-title"}),
                    ui.input_selectize(
                        "underlying_ric",
                        "Underlying Asset RIC",
                        choices=[
                            "AAPL.O", "MSFT.O", "TSLA.O", "NVDA.O",
                            "AMZN.O", "META.O", "GOOGL.O", "NFLX.O",
                            "AMD.O", "INTC.O", "JPM.N", "GS.N",
                        ],
                        selected="MSFT.O",
                        options={"maxItems": 1},
                    ),
                    ui.input_action_button(
                        "fetch_spot", "FETCH SPOT PRICE", class_="btn-primary w-100"
                    ),
                    ui.div(
                        {"class": "spot-display"},
                        ui.output_text("spot_price"),
                        ui.output_text("exchange_time"),
                    )
                ),
                ui.div(
                    {"class": "control-section"},
                    ui.h3("2. Configure Options Chain", {"class": "section-title"}),
                    ui.div(
                        {"class": "input-row"},
                        ui.input_numeric("min_strike", "Min Strike", value=300),
                        ui.input_numeric("max_strike", "Max Strike", value=500),
                    ),
                    ui.div(
                        {"class": "input-row"},
                        ui.input_date("min_expiry", "Min Expiry", value=default_min_expiry),
                        ui.input_date("max_expiry", "Max Expiry", value=default_max_expiry),
                    ),
                    ui.input_numeric("top_options", "Max Contracts", value=1000),
                    ui.input_action_button(
                        "fetch_chain", "SCAN OPTIONS CHAIN", class_="btn-primary w-100"
                    ),
                ),
            ),
            ui.div(
                {"class": "data-section"},
                ui.h3("Options Chain Data", {"class": "section-title"}),
                ui.output_data_frame("options_table"),
            ),
        ),
    ),
    ui.nav_panel(
        "Analysis",
        ui.div(
            {"class": "page-container"},
            ui.h1("Arbitrage Analysis", {"class": "page-title"}),
            ui.div(
                {"class": "analysis-controls"},
                ui.div(
                    {"class": "control-section"},
                    ui.h3("Analysis Parameters", {"class": "section-title"}),
                    ui.input_numeric("risk_free_rate", "Risk-Free Rate (%)", value=5.0, step=0.1),
                    ui.input_numeric("arb_threshold", "Arbitrage Threshold (%)", value=0.5, step=0.1),
                    ui.input_action_button(
                        "analyze_arb", "ANALYZE ARBITRAGE", class_="btn-primary w-100"
                    ),
                ),
            ),
            ui.div(
                {"class": "data-section"},
                ui.h3("Detected Opportunities", {"class": "section-title"}),
                ui.output_text("arb_summary"),
                ui.output_data_frame("arbitrage_table"),
                ui.output_ui("strategy_details"),
            ),
        ),
    ),
    ui.nav_panel(
        "Execution Calculator",
        ui.div(
            {"class": "page-container"},
            ui.h1("Execution Cost Calculator", {"class": "page-title"}),
            ui.p("Calculate real-world execution costs using live market data", {"class": "page-subtitle"}),
            ui.output_text("calc_instruction"),
            ui.output_ui("calculator_interface"),
        ),
    ),
    ui.nav_panel(
        "3D Visualization",
        ui.div(
            {"class": "page-container"},
            ui.h1("Implied Rate Surface", {"class": "page-title"}),
            ui.p("Interactive 3D visualization of implied risk-free rates", {"class": "page-subtitle"}),
            ui.div(
                {"class": "info-banner"},
                ui.p(
                    "ℹ️ Note: If the 3D surface doesn't appear after clicking 'ANALYZE ARBITRAGE', please click the button again to refresh the visualization.",
                ),
            ),
            ui.output_ui("surface_plot"),
        ),
    ),
    title="DevilTongues",
    id="navbar",
)


# ---------- server ----------
def server(input, output, session):
    rd.open_session()
    session.on_ended(rd.close_session)

    spot_price_data = reactive.Value(None)
    exchange_time_data = reactive.Value(None)
    option_data = reactive.Value(None)
    surface_data = reactive.Value(None)
    arbitrage_data = reactive.Value(None)
    selected_arb_row = reactive.Value(None)

    calc_contracts = reactive.Value(10)
    calc_commission = reactive.Value(5.0)
    calc_slippage_pct = reactive.Value(0.5)
    calc_trigger = reactive.Value(0)

    @reactive.effect
    @reactive.event(input.calculate_btn)
    def _update_calc_params():
        try:
            v = input.contracts()
            calc_contracts.set(int(v) if v is not None else 10)
        except:
            calc_contracts.set(10)

        try:
            v = input.commission_per_leg()
            calc_commission.set(float(v) if v is not None else 5.0)
        except:
            calc_commission.set(5.0)

        try:
            v = input.slippage_pct()
            calc_slippage_pct.set(float(v) if v is not None else 0.5)
        except:
            calc_slippage_pct.set(0.5)

        try:
            calc_trigger.set(calc_trigger.get() + 1)
        except:
            calc_trigger.set(1)

    @reactive.effect
    @reactive.event(input.fetch_spot)
    def _fetch_spot():
        ric = input.underlying_ric()
        fetch_time = datetime.now()

        try:
            df = rd.get_data(ric, fields=["TR.PriceClose"])
            spot_price_data.set(df["Price Close"].iloc[0])
            exchange_time_data.set(fetch_time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            exchange_time_data.set(fetch_time.strftime("%Y-%m-%d %H:%M:%S"))
            print(f"Error fetching spot price: {e}")

    @render.text
    def spot_price():
        req(spot_price_data.get() is not None)
        return f"Spot Price: ${spot_price_data.get():.2f}"

    @render.text
    def exchange_time():
        req(exchange_time_data.get() is not None)
        return f"Last Update: {exchange_time_data.get()}"

    @reactive.effect
    @reactive.event(input.fetch_chain)
    def _fetch_chain():
        ric = input.underlying_ric()
        spot = spot_price_data.get()
        if spot is None:
            return

        fetch_time = datetime.now()

        filter_str = (
            "( SearchAllCategoryv2 eq 'Options' and "
            f"(ExpiryDate gt {input.min_expiry()} and ExpiryDate lt {input.max_expiry()}) and "
            f"(StrikePrice ge {input.min_strike()} and StrikePrice le {input.max_strike()}) and "
            "ExchangeName xeq 'OPRA' and "
            f"(UnderlyingQuoteRIC eq '{ric}'))"
        )

        chain = rd.discovery.search(
            view=rd.discovery.Views.EQUITY_QUOTES,
            top=input.top_options(),
            filter=filter_str,
            select="RIC,CallPutOption,StrikePrice,ExpiryDate",
        )

        if chain.empty:
            option_data.set(chain)
            surface_data.set(None)
            exchange_time_data.set(fetch_time.strftime("%Y-%m-%d %H:%M:%S"))
            return

        chain["RIC"] = chain["RIC"].astype(str)

        raw_price = rd.get_data(
            universe=chain["RIC"].tolist(),
            fields=["CF_BID", "CF_ASK", "CF_LAST"],
        ).reset_index()

        candidate_cols = ["RIC", "Instrument", "ric", "instrument", "index"]
        ric_col = None
        for c in candidate_cols:
            if c in raw_price.columns:
                ric_col = c
                break
        if ric_col is None:
            ric_col = raw_price.columns[0]

        price_df = raw_price.rename(
            columns={
                ric_col: "RIC",
                "CF_BID": "Bid",
                "CF_ASK": "Ask",
                "CF_LAST": "Last",
            }
        )[["RIC", "Bid", "Ask", "Last"]]

        price_df["RIC"] = price_df["RIC"].astype(str)

        merged = chain.merge(price_df, on="RIC", how="left")
        option_data.set(merged)

        surf = build_surface_df(merged, spot)
        surface_data.set(surf)

        exchange_time_data.set(fetch_time.strftime("%Y-%m-%d %H:%M:%S"))

    @render.text
    def arb_summary():
        df = arbitrage_data.get()
        if df is None or df.empty:
            return "No arbitrage opportunities detected."
        return f"Found {len(df)} arbitrage opportunities across {df['K'].nunique()} strikes"

    @render.data_frame
    def options_table():
        df = option_data.get()
        req(df is not None)
        return df

    @reactive.effect
    @reactive.event(input.analyze_arb)
    def _analyze_arbitrage():
        surf = surface_data.get()
        req(surf is not None)

        rf_rate = input.risk_free_rate() / 100.0
        threshold = input.arb_threshold() / 100.0

        arb_df = analyze_arbitrage(surf, rf_rate, threshold)
        arbitrage_data.set(arb_df)
        selected_arb_row.set(None)

    @render.data_frame
    def arbitrage_table():
        df = arbitrage_data.get()
        req(df is not None and not df.empty)

        display_df = df.copy()
        display_df["Strategy"] = display_df["signal"].apply(get_strategy_summary)
        display_df = display_df[["K", "T", "ExpiryDate", "Strategy", "implied_r", "r_diff", "C_mid", "P_mid"]]

        display_df["T"] = display_df["T"].apply(lambda x: f"{x:.4f}")
        display_df["implied_r"] = display_df["implied_r"].apply(lambda x: f"{x * 100:.2f}%")
        display_df["r_diff"] = display_df["r_diff"].apply(lambda x: f"{x * 100:.2f}%")
        display_df["C_mid"] = display_df["C_mid"].apply(lambda x: f"${x:.2f}")
        display_df["P_mid"] = display_df["P_mid"].apply(lambda x: f"${x:.2f}")
        display_df["ExpiryDate"] = pd.to_datetime(display_df["ExpiryDate"]).dt.strftime('%Y-%m-%d')
        display_df["K"] = display_df["K"].apply(lambda x: f"${x:.0f}")

        display_df.columns = ["Strike", "Years", "Expiry", "Strategy", "Implied r", "Rate Diff", "Call", "Put"]

        return render.DataGrid(
            display_df,
            selection_mode="row",
            height="400px"
        )

    @reactive.effect
    @reactive.event(input.arbitrage_table_selected_rows)
    def _on_row_select():
        selected_indices = input.arbitrage_table_selected_rows()
        if selected_indices:
            selected_arb_row.set(selected_indices[0])
        else:
            selected_arb_row.set(None)

    @render.ui
    def strategy_details():
        row_idx = selected_arb_row.get()
        df = arbitrage_data.get()

        if row_idx is None or df is None or df.empty:
            return ui.div(
                {"class": "empty-state"},
                "Click on a row above to see detailed strategy breakdown"
            )

        row = df.iloc[row_idx]
        details = get_strategy_details(row)

        return ui.div(
            {"class": "strategy-detail-card"},
            ui.h4(details["type"], {"class": "strategy-type"}),
            ui.div(
                {"class": "strategy-section"},
                ui.h5("Summary"),
                ui.p(details["summary"]),
            ),
            ui.div(
                {"class": "strategy-section"},
                ui.h5("Required Positions"),
                ui.div(
                    {"class": "positions-list"},
                    ui.HTML("<br>".join(details["positions"]))
                )
            ),
            ui.div(
                {"class": "strategy-section"},
                ui.h5("Rationale"),
                ui.p(details["rationale"]),
            ),
            ui.div(
                {"class": "strategy-section"},
                ui.h5("Expected Profit"),
                ui.p(details["profit"], {"class": "profit-text"}),
            ),
            ui.div(
                {"class": "strategy-section"},
                ui.h5("⚠️ Risks"),
                ui.div(
                    {"class": "risk-text"},
                    details["risk"]
                )
            ),
            ui.div(
                {"class": "recommendation-box"},
                ui.h5("💡 Recommendation"),
                ui.p(details["recommendation"]),
            )
        )

    @render.text
    def calc_instruction():
        df = arbitrage_data.get()
        if df is None or df.empty:
            return "No arbitrage opportunities available. Run 'ANALYZE ARBITRAGE' first."
        row_idx = selected_arb_row.get()
        if row_idx is None:
            return "Select a strategy from the 'Analysis' tab to calculate execution costs."
        return "Calculating real-world execution costs using live market data"

    @render.ui
    def calculator_interface():
        row_idx = selected_arb_row.get()
        df = arbitrage_data.get()

        if row_idx is None or df is None or df.empty:
            return ui.div(
                {"class": "empty-state"},
                ui.h5("No Strategy Selected"),
                ui.p("Please go to the 'Analysis' tab and click on a row to select a strategy for calculation."),
            )

        row = df.iloc[row_idx]

        _ = calc_trigger.get()

        contracts = calc_contracts.get()
        commission = calc_commission.get()
        slippage_pct = calc_slippage_pct.get()

        risk_free_rate = input.risk_free_rate() / 100.0

        results = calculate_execution_costs(row, contracts, commission, slippage_pct, risk_free_rate)

        return ui.div(
            {"class": "calculator-layout"},
            ui.div(
                {"class": "calculator-inputs"},
                ui.div(
                    {"class": "control-section"},
                    ui.h3("Selected Strategy", {"class": "section-title"}),
                    ui.div(
                        {"class": "strategy-badge"},
                        results['strategy_type']
                    ),
                    ui.div(
                        {"class": "market-data-display"},
                        ui.h4("Market Data (Live)"),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Strike (K):"),
                            ui.span(f"${results['strike']:.2f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Spot (S):"),
                            ui.span(f"${results['spot']:.2f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Call Mid:"),
                            ui.span(f"${results['call_mid']:.3f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Put Mid:"),
                            ui.span(f"${results['put_mid']:.3f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Days to Expiry:"),
                            ui.span(f"{results['days_to_expiry']:.0f} days", {"class": "data-value"}),
                        ),
                    ),
                    ui.div(
                        {"class": "rate-analysis-display"},
                        ui.h4("Rate Analysis"),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Implied Rate:"),
                            ui.span(f"{results['implied_rate'] * 100:.2f}%", {"class": "data-value highlight"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Benchmark Rate:"),
                            ui.span(f"{results['risk_free_rate'] * 100:.2f}%", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Rate Diff:"),
                            ui.span(f"{results['rate_diff'] * 100:.2f}%", {"class": "data-value profit" if results['rate_diff'] > 0 else "data-value"}),
                        ),
                    ),
                ),
                ui.div(
                    {"class": "control-section"},
                    ui.h3("Input Parameters", {"class": "section-title"}),
                    ui.input_numeric("contracts", "Number of Contracts", value=contracts, min=1, max=1000),
                    ui.input_numeric("commission_per_leg", "Commission per Leg ($)", value=commission, min=0, step=0.5),
                    ui.input_numeric("slippage_pct", "Expected Slippage (%)", value=slippage_pct, min=0, max=5, step=0.1),
                    ui.input_action_button("calculate_btn", "Update Calculation", class_="btn-primary w-100"),
                )
            ),
            ui.div(
                {"class": "calculator-results"},
                ui.div(
                    {"class": "control-section"},
                    ui.h3("Position Values", {"class": "section-title"}),
                    ui.div(
                        {"class": "positions-breakdown"},
                        ui.div(
                            {"class": "data-row"},
                            ui.span(f"Call Position ({contracts} contracts @ ${results['call_mid']:.2f}):"),
                            ui.span(f"${results['call_value']:,.2f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span(f"Put Position ({contracts} contracts @ ${results['put_mid']:.2f}):"),
                            ui.span(f"${results['put_value']:,.2f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span(f"Stock Position ({contracts * 100} shares @ ${results['spot']:.2f}):"),
                            ui.span(f"${results['stock_value']:,.2f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Total Commission (3 legs):"),
                            ui.span(f"-${results['total_commission']:,.2f}", {"class": "data-value warning"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span(f"Slippage ({slippage_pct}%):"),
                            ui.span(f"-${results['slippage_cost']:,.2f}", {"class": "data-value warning"}),
                        ),
                        ui.tags.hr({"class": "divider"}),
                        ui.div(
                            {"class": "data-row highlight-row"},
                            ui.span("Net P&L at Expiration:"),
                            ui.span(f"${results['net_pnl']:,.2f}", {"class": "data-value profit" if results['net_pnl'] > 0 else "data-value danger"}),
                        ),
                    )
                ),
                ui.div(
                    {"class": "control-section"},
                    ui.h3("Implied Rate Carry (Before Costs)", {"class": "section-title"}),
                    ui.div(
                        {"class": "positions-breakdown"},
                        ui.div(
                            {"class": "data-row highlight-row"},
                            ui.span("Theoretical Arbitrage Profit:"),
                            ui.span(f"${results['theoretical_profit']:,.2f}", {"class": "data-value profit large"}),
                        ),
                        ui.div(
                            {"class": "info-text"},
                            "This value reflects interest rate mispricing implied by put-call parity. "
                            "It assumes frictionless execution and excludes commissions, slippage, funding, and assignment risk."
                        ),
                        ui.tags.hr({"class": "divider"}),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Capital Employed:"),
                            ui.span(f"${results['capital_employed']:,.2f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Required Margin:"),
                            ui.span(f"${results['required_margin']:,.2f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Return on Capital (ROI):"),
                            ui.span(f"{results['roi']:.2f}%", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Annualized Return:"),
                            ui.span(f"{results['annualized_return']:.2f}%", {"class": "data-value profit large"}),
                        ),
                    )
                ),
                ui.div(
                    {"class": "control-section"},
                    ui.h3("Scenario Analysis", {"class": "section-title"}),
                    ui.div(
                        {"class": "positions-breakdown"},
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Best Case (+30%):"),
                            ui.span(f"${results['best_case']:,.2f}", {"class": "data-value profit"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Expected Case:"),
                            ui.span(f"${results['theoretical_profit']:,.2f}", {"class": "data-value"}),
                        ),
                        ui.div(
                            {"class": "data-row"},
                            ui.span("Worst Case (-30%):"),
                            ui.span(f"${results['worst_case']:,.2f}", {"class": "data-value warning"}),
                        ),
                        ui.tags.hr({"class": "divider"}),
                        ui.div(
                            {"class": "warning-box"},
                            "⚠️ Note: These calculations use real-time market data. Actual execution may vary due to market conditions, "
                            "liquidity, timing, and early assignment risk. A positive implied rate carry does not necessarily translate "
                            "into positive realized P&L once execution costs are considered."
                        )
                    )
                ),
            )
        )

    @render.ui
    def surface_plot():
        surf = surface_data.get()
        arb_df = arbitrage_data.get()

        if surf is None:
            return ui.div(
                {"class": "empty-state"},
                ui.h5("No Data Available"),
                ui.p("Please scan options first by clicking 'SCAN OPTIONS CHAIN' in the Market Data tab."),
            )

        if arb_df is None or arb_df.empty:
            return ui.div(
                {"class": "empty-state"},
                ui.h5("No Arbitrage Data"),
                ui.p("Click 'ANALYZE ARBITRAGE' in the Analysis tab to generate the surface."),
            )

        K_vals = arb_df["K"].values
        T_vals = arb_df["T"].values
        r_vals = arb_df["implied_r"].values

        if len(K_vals) < 3:
            return ui.div({"class": "empty-state"}, "Insufficient data points for 3D surface. Need more strike/expiry combinations.")

        K_unique = np.sort(np.unique(K_vals))
        T_unique = np.sort(np.unique(T_vals))

        if len(K_unique) < 2 or len(T_unique) < 2:
            return ui.div({"class": "empty-state"}, "Need at least 2 different strikes and 2 different expiries for surface plot.")

        K_grid, T_grid = np.meshgrid(
            np.linspace(K_unique.min(), K_unique.max(), 30),
            np.linspace(T_unique.min(), T_unique.max(), 30)
        )

        try:
            r_grid = interpolate.griddata(
                (K_vals, T_vals), r_vals, (K_grid, T_grid), method='cubic', fill_value=np.nan
            )

            r_grid_pct = r_grid * 100
            T_grid_days = T_grid * 365

            fig = go.Figure(data=[go.Surface(
                x=K_grid,
                y=T_grid_days,
                z=r_grid_pct,
                colorscale='Viridis',
                colorbar=dict(title="Implied r, % ann")
            )])

            fig.update_traces(
                hovertemplate='<b>Strike:</b> $%{x:.0f}<br>' +
                              '<b>Days to Expiry:</b> %{y:.1f}<br>' +
                              '<b>Implied r:</b> %{z:.2f}% ann<br>' +
                              '<extra></extra>'
            )

            # Deep-blue styling for Plotly
            fig.update_layout(
                title="Implied Risk-Free Rate Surface",
                scene=dict(
                    xaxis_title="Strike Price ($)",
                    yaxis_title="Time to Expiry (Days)",
                    zaxis_title="Implied r, % ann",
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.3)),
                    xaxis=dict(tickprefix="$"),
                    zaxis=dict(ticksuffix="%"),
                    bgcolor="#0f1e33",
                ),
                template="plotly_dark",
                paper_bgcolor="#0b1220",
                font=dict(color="#e8eefc"),
                height=600,
                margin=dict(l=0, r=0, t=40, b=0)
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", full_html=False))

        except Exception as e:
            return ui.div({"class": "empty-state"}, f"Error creating surface plot: {str(e)}")


app = App(app_ui, server)

if __name__ == "__main__":
    app.run()
