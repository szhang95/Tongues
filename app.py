from __future__ import annotations

from datetime import datetime, timedelta
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
    """
    Compute implied risk-free rate from put-call parity:
    C - P = S - K * exp(-r*T)
    r = -(1/T) * ln((S - (C-P)) / K)
    """
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
    """Convert full strategy to short summary"""
    if "Sell synthetic" in signal:
        return "Sell Call+Buy Put+Buy Stock"
    elif "Buy synthetic" in signal:
        return "Buy Call+Sell Put+Short Stock"
    return signal


def get_strategy_details(row) -> dict:
    """Generate detailed strategy breakdown and recommendations"""
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
    else:  # Conversion
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
    """
    Analyze options surface for arbitrage opportunities
    """
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


# ---------- UI ----------
app_ui = ui.page_fillable(
    ui.include_css("custom.css"),
    ui.tags.style("""
        .strategy-row {
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .strategy-row:hover {
            background-color: rgba(59, 130, 246, 0.1) !important;
        }
        .strategy-detail-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid #3b82f6;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
            box-shadow: 0 8px 24px rgba(59, 130, 246, 0.3);
        }
        .strategy-section {
            margin-bottom: 15px;
        }
        .strategy-section h5 {
            color: #3b82f6;
            margin-bottom: 8px;
            font-size: 0.95rem;
        }
        .strategy-positions {
            background: rgba(15, 23, 42, 0.5);
            padding: 12px;
            border-radius: 6px;
            margin: 8px 0;
        }
        .profit-highlight {
            color: #10b981;
            font-weight: 600;
        }
        .risk-highlight {
            color: #f59e0b;
        }
        .recommendation-box {
            background: rgba(59, 130, 246, 0.1);
            border-left: 4px solid #3b82f6;
            padding: 12px;
            margin-top: 10px;
            border-radius: 4px;
        }
    """),
    ui.div(
        {"class": "container-fluid"},
        ui.div(
            {"class": "row", "style": "margin-top: 30px;"},
            # Left Panel - Controls
            ui.div(
                {"class": "col-md-3"},
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
                    "fetch_spot", "FETCH SPOT", class_="w-100", style="margin-top: 12px;"
                ),
                ui.div(
                    {"style": "margin-top: 20px;"},
                    ui.input_numeric("min_strike", "Min Strike", value=300),
                    ui.input_numeric("max_strike", "Max Strike", value=500),
                    ui.input_date("min_expiry", "Min Expiry", value=default_min_expiry),
                    ui.input_date("max_expiry", "Max Expiry", value=default_max_expiry),
                    ui.input_numeric("top_options", "Max Contracts", value=1000),
                ),
                ui.input_action_button(
                    "fetch_chain", "SCAN OPTIONS", class_="w-100", style="margin-top: 20px;"
                ),
                ui.div(
                    {"style": "margin-top: 20px;"},
                    ui.input_numeric("risk_free_rate", "Risk-Free Rate (%)", value=5.0, step=0.1),
                    ui.input_numeric("arb_threshold", "Arbitrage Threshold (%)", value=0.5, step=0.1),
                ),
                ui.input_action_button(
                    "analyze_arb", "ANALYZE ARBITRAGE", class_="w-100", style="margin-top: 12px;"
                ),
            ),
            # Right Panel - Display
            ui.div(
                {"class": "col-md-9"},
                ui.navset_tab(
                    ui.nav_panel(
                        "Market Data",
                        ui.h4("Spot Price", style="margin-top: 20px;"),
                        ui.output_text("spot_price"),
                        ui.output_text("exchange_time"),
                        ui.h4("Options Chain", style="margin-top: 20px;"),
                        ui.output_data_frame("options_table"),
                    ),
                    ui.nav_panel(
                        "Arbitrage Signals",
                        ui.h4("Detected Opportunities", style="margin-top: 20px;"),
                        ui.div(
                            ui.output_text("arb_summary"),
                            style="margin-bottom: 15px; color: #94a3b8;"
                        ),
                        ui.output_data_frame("arbitrage_table"),
                        ui.output_ui("strategy_details"),
                    ),
                    ui.nav_panel(
                        "Execution Calculator",
                        ui.h4("Calculate Real-World Execution Costs & Returns", style="margin-top: 20px;"),
                        ui.div(
                            {"style": "margin-bottom: 20px; color: #94a3b8;"},
                            ui.output_text("calc_instruction")
                        ),
                        ui.output_ui("calculator_interface"),
                    ),
                    ui.nav_panel(
                        "3D Surface",
                        ui.h4("Implied Rate Surface (r vs K vs T)", style="margin-top: 20px;"),
                        ui.div(
                            {
                                "style": "background: rgba(251, 191, 36, 0.1); border-left: 4px solid #fbbf24; padding: 12px; margin: 20px 0; border-radius: 4px;"},
                            ui.p(
                                "ℹ️ Note: If the 3D surface doesn't appear after clicking 'ANALYZE ARBITRAGE', please click the button again to refresh the visualization.",
                                style="margin: 0; color: #fcd34d; font-size: 0.9em;")
                        ),
                        ui.output_ui("surface_plot"),
                    ),
                ),
            ),
        ),
    ),
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
    calc_slippage = reactive.Value(0.5)

    # ---- spot ----
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

    # ---- chain + prices ----
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

    # ---- arbitrage analysis ----
    @reactive.effect
    @reactive.event(input.analyze_arb)
    def _analyze_arbitrage():
        surf = surface_data.get()
        req(surf is not None)

        rf_rate = input.risk_free_rate() / 100.0
        threshold = input.arb_threshold() / 100.0

        arb_df = analyze_arbitrage(surf, rf_rate, threshold)
        arbitrage_data.set(arb_df)
        selected_arb_row.set(None)  # Reset selection

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
                {"style": "margin-top: 20px; color: #64748b; text-align: center;"},
                "Click on a row above to see detailed strategy breakdown and recommendations"
            )

        row = df.iloc[row_idx]
        details = get_strategy_details(row)

        return ui.div(
            {"class": "strategy-detail-card"},
            ui.h4(details["type"], style="color: #3b82f6; margin-bottom: 15px;"),

            ui.div(
                {"class": "strategy-section"},
                ui.h5("Summary"),
                ui.p(details["summary"], style="color: #cbd5e1;")
            ),

            ui.div(
                {"class": "strategy-section"},
                ui.h5("Required Positions"),
                ui.div(
                    {"class": "strategy-positions"},
                    ui.HTML("<br>".join(details["positions"]))
                )
            ),

            ui.div(
                {"class": "strategy-section"},
                ui.h5("Rationale"),
                ui.p(details["rationale"], style="color: #cbd5e1;")
            ),

            ui.div(
                {"class": "strategy-section"},
                ui.h5("Expected Profit"),
                ui.p(details["profit"], {"class": "profit-highlight"})
            ),

            ui.div(
                {"class": "strategy-section"},
                ui.h5("⚠️ Risks"),
                ui.div(
                    {"class": "risk-highlight", "style": "white-space: pre-line;"},
                    details["risk"]
                )
            ),

            ui.div(
                {"class": "recommendation-box"},
                ui.h5("💡 Recommendation"),
                ui.p(details["recommendation"], style="margin: 0; color: #e2e8f0;")
            )
        )

    # ---- Execution Calculator ----
    @render.text
    def calc_instruction():
        df = arbitrage_data.get()
        if df is None or df.empty:
            return "No arbitrage opportunities available. Run 'ANALYZE ARBITRAGE' first."
        row_idx = selected_arb_row.get()
        if row_idx is None:
            return "Select a strategy from the 'Arbitrage Signals' tab to calculate execution costs."
        return f"Calculating real-world execution costs for selected strategy"

    @render.ui
    def calculator_interface():
        row_idx = selected_arb_row.get()
        df = arbitrage_data.get()

        if row_idx is None or df is None or df.empty:
            return ui.div(
                {"style": "margin-top: 20px; color: #64748b; text-align: center; padding: 40px;"},
                ui.h5("No Strategy Selected"),
                ui.p(
                    "Please go to the 'Arbitrage Signals' tab and click on a row to select a strategy for calculation.")
            )

        row = df.iloc[row_idx]
        strategy_type = get_strategy_summary(row['signal'])

        # Get reactive values
        contracts = calc_contracts.get()
        commission = calc_commission.get()
        slippage_pct = calc_slippage.get()

        # Calculate costs
        call_cost = row['C_mid'] * contracts * 100
        put_credit = row['P_mid'] * contracts * 100
        stock_value = row['S'] * contracts * 100
        total_commission = commission * 3  # 3 legs
        slippage_cost = (call_cost + put_credit + stock_value) * (slippage_pct / 100)

        if strategy_type == "Sell Call+Buy Put+Buy Stock":
            # Reverse Conversion
            net_credit = call_cost - put_credit
            total_cost = net_credit + total_commission + slippage_cost
            stock_position = stock_value
            net_position = total_cost + stock_position
            days_to_expiry = row['T'] * 365
            expected_profit = abs(row['r_diff']) * net_position

            profit_label = "Expected Profit"
            best_case = expected_profit * 1.3
            worst_case = expected_profit * 0.7
        else:
            # Conversion
            net_credit = stock_value - row['K'] * contracts * 100 + put_credit - call_cost
            total_cost = total_commission + slippage_cost
            net_position = abs(net_credit - total_cost)
            days_to_expiry = row['T'] * 365
            expected_profit = abs(row['r_diff']) * net_position

            profit_label = "Expected Profit"
            best_case = expected_profit * 1.3
            worst_case = expected_profit * 0.7

        # Calculate returns
        roi = (expected_profit / net_position * 100) if net_position > 0 else 0
        annualized_return = (roi * 365 / days_to_expiry) if days_to_expiry > 0 else 0
        required_margin = net_position * 0.25  # Assume 25% margin requirement

        return ui.div(
            {"class": "row"},
            # Left column - Inputs
            ui.div(
                {"class": "col-md-4"},
                ui.div(
                    {"class": "strategy-detail-card"},
                    ui.h5("Selected Strategy", style="color: #3b82f6; margin-bottom: 15px;"),
                    ui.p(f"Type: {strategy_type}", style="color: #e2e8f0; margin: 5px 0;"),
                    ui.p(f"Strike: ${row['K']:.0f}", style="color: #e2e8f0; margin: 5px 0;"),
                    ui.p(f"Expiry: {row['ExpiryDate'].strftime('%Y-%m-%d')}", style="color: #e2e8f0; margin: 5px 0;"),
                    ui.p(f"Days to Expiry: {days_to_expiry:.0f}", style="color: #e2e8f0; margin: 5px 0;"),

                    ui.hr(style="border-color: #334155; margin: 20px 0;"),

                    ui.h5("Input Parameters", style="color: #3b82f6; margin-bottom: 15px;"),
                    ui.input_numeric("contracts", "Number of Contracts", value=10, min=1, max=1000),
                    ui.input_numeric("commission_per_leg", "Commission per Leg ($)", value=5.0, min=0, step=0.5),
                    ui.input_numeric("slippage_pct", "Expected Slippage (%)", value=0.5, min=0, max=5, step=0.1),

                    ui.input_action_button("calculate_btn", "Update Calculation", class_="btn-action w-100",
                                           style="margin-top: 20px;"),
                )
            ),

            # Right column - Results
            ui.div(
                {"class": "col-md-8"},
                ui.div(
                    {"class": "strategy-detail-card"},
                    ui.h5("Cost Breakdown", style="color: #3b82f6; margin-bottom: 15px;"),
                    ui.div(
                        {"class": "strategy-positions"},
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Call Cost:"),
                            ui.span(f"${call_cost:,.2f}", style="font-weight: 600;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Put Credit:"),
                            ui.span(f"${put_credit:,.2f}", style="font-weight: 600; color: #10b981;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Stock Position:"),
                            ui.span(f"${stock_value:,.2f}", style="font-weight: 600;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Total Commission (3 legs):"),
                            ui.span(f"-${total_commission:,.2f}", style="font-weight: 600; color: #f59e0b;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span(f"Slippage ({slippage_pct}%):"),
                            ui.span(f"-${slippage_cost:,.2f}", style="font-weight: 600; color: #f59e0b;")
                        ),
                        ui.hr(style="border-color: #334155; margin: 15px 0;"),
                        ui.div(
                            {
                                "style": "display: flex; justify-content: space-between; margin: 8px 0; font-size: 1.1em;"},
                            ui.span("Net Position:"),
                            ui.span(f"${net_position:,.2f}", style="font-weight: 700; color: #3b82f6;")
                        ),
                    )
                ),

                ui.div(
                    {"class": "strategy-detail-card", "style": "margin-top: 20px;"},
                    ui.h5("Expected Returns", style="color: #10b981; margin-bottom: 15px;"),
                    ui.div(
                        {"class": "strategy-positions"},
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 12px 0;"},
                            ui.span(profit_label + ":"),
                            ui.span(f"${expected_profit:,.2f}",
                                    style="font-weight: 700; color: #10b981; font-size: 1.2em;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Return on Investment:"),
                            ui.span(f"{roi:.2f}%", style="font-weight: 600;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Annualized Return:"),
                            ui.span(f"{annualized_return:.2f}%", style="font-weight: 600; color: #10b981;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Required Margin (est.):"),
                            ui.span(f"${required_margin:,.2f}", style="font-weight: 600;")
                        ),
                    )
                ),

                ui.div(
                    {"class": "strategy-detail-card", "style": "margin-top: 20px;"},
                    ui.h5("Scenario Analysis", style="color: #3b82f6; margin-bottom: 15px;"),
                    ui.div(
                        {"class": "strategy-positions"},
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Best Case (+30%):"),
                            ui.span(f"${best_case:,.2f}", style="font-weight: 600; color: #10b981;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Expected Case:"),
                            ui.span(f"${expected_profit:,.2f}", style="font-weight: 600;")
                        ),
                        ui.div(
                            {"style": "display: flex; justify-content: space-between; margin: 8px 0;"},
                            ui.span("Worst Case (-30%):"),
                            ui.span(f"${worst_case:,.2f}", style="font-weight: 600; color: #f59e0b;")
                        ),
                        ui.hr(style="border-color: #334155; margin: 15px 0;"),
                        ui.div(
                            {"style": "color: #94a3b8; font-size: 0.9em; margin-top: 10px;"},
                            "Note: These calculations are estimates. Actual execution may vary based on market conditions, liquidity, and timing."
                        )
                    )
                ),
            )
        )

    @reactive.effect
    @reactive.event(input.calculate_btn)
    def _update_calc_params():
        calc_contracts.set(input.contracts())
        calc_commission.set(input.commission_per_leg())
        calc_slippage.set(input.slippage_pct())

    # ---- 3D surface plot ----
    @render.ui
    def surface_plot():
        surf = surface_data.get()
        arb_df = arbitrage_data.get()

        if surf is None:
            return ui.div(
                {"style": "margin-top: 20px; color: #64748b; text-align: center; padding: 40px;"},
                ui.h5("No Data Available"),
                ui.p("Please scan options first by clicking 'SCAN OPTIONS' in the left panel.")
            )

        if arb_df is None or arb_df.empty:
            return ui.div(
                {"style": "margin-top: 20px; color: #64748b; text-align: center; padding: 40px;"},
                ui.h5("No Arbitrage Data"),
                ui.p("Click 'ANALYZE ARBITRAGE' in the left panel to generate the surface.")
            )

        K_vals = arb_df["K"].values
        T_vals = arb_df["T"].values
        r_vals = arb_df["implied_r"].values

        if len(K_vals) < 3:
            return ui.div("Insufficient data points for 3D surface. Need more strike/expiry combinations.")

        K_unique = np.sort(np.unique(K_vals))
        T_unique = np.sort(np.unique(T_vals))

        if len(K_unique) < 2 or len(T_unique) < 2:
            return ui.div("Need at least 2 different strikes and 2 different expiries for surface plot.")

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

            fig.update_layout(
                title="Implied Risk-Free Rate Surface",
                scene=dict(
                    xaxis_title="Strike Price ($)",
                    yaxis_title="Time to Expiry (Days)",
                    zaxis_title="Implied r, % ann",
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.3)),
                    xaxis=dict(tickprefix="$"),
                    zaxis=dict(ticksuffix="%")
                ),
                template="plotly_dark",
                height=600,
                margin=dict(l=0, r=0, t=40, b=0)
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", full_html=False))

        except Exception as e:
            return ui.div(f"Error creating surface plot: {str(e)}")


app = App(app_ui, server)

if __name__ == "__main__":
    app.run()