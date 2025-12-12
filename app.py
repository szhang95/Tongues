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


def analyze_arbitrage(surface_df: pd.DataFrame, risk_free_rate: float = 0.05, threshold: float = 0.005):
    """
    Analyze options surface for arbitrage opportunities
    """
    # Pivot to get calls and puts
    calls = surface_df[surface_df["CallPutOption"] == "Call"].copy()
    puts = surface_df[surface_df["CallPutOption"] == "Put"].copy()

    # Merge on strike and expiry
    merged = calls.merge(
        puts,
        on=["K", "T", "S", "ExpiryDate"],
        suffixes=("_call", "_put")
    )

    merged["C_mid"] = merged["mid_call"]
    merged["P_mid"] = merged["mid_put"]
    merged["implied_r"] = merged.apply(compute_implied_r, axis=1)
    merged["r_diff"] = merged["implied_r"] - risk_free_rate

    # Generate signals
    merged["signal"] = None
    merged.loc[merged["r_diff"] > threshold, "signal"] = "Sell synthetic, buy stock"
    merged.loc[merged["r_diff"] < -threshold, "signal"] = "Buy synthetic, short stock"

    return merged[merged["signal"].notna()]


# ---------- UI ----------
app_ui = ui.page_fillable(
    ui.include_css("custom.css"),
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
                        ui.output_data_frame("arbitrage_table"),
                    ),
                    ui.nav_panel(
                        "Trading Blotter",
                        ui.h4("Trade Execution", style="margin-top: 20px;"),
                        ui.output_data_frame("blotter_table"),
                        ui.div(
                            {"style": "margin-top: 20px;"},
                            ui.input_action_button("clear_blotter", "Clear Blotter", class_="btn-secondary"),
                        ),
                    ),
                    ui.nav_panel(
                        "3D Surface",
                        ui.h4("Implied Rate Surface (r vs K vs T)", style="margin-top: 20px;"),
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
    blotter_data = reactive.Value([])

    # ---- spot ----
    @reactive.effect
    @reactive.event(input.fetch_spot)
    def _fetch_spot():
        ric = input.underlying_ric()
        try:
            # Try to get current price with timestamp
            df = rd.get_data(ric, fields=["TR.PriceClose", "TR.PriceCloseDate"])
            spot_price_data.set(df["Price Close"].iloc[0])

            # Check various possible column names for the date
            date_col = None
            for col in df.columns:
                if "date" in col.lower() or "time" in col.lower():
                    date_col = col
                    break

            if date_col and pd.notna(df[date_col].iloc[0]):
                exchange_time_data.set(pd.to_datetime(df[date_col].iloc[0]).strftime("%Y-%m-%d %H:%M:%S"))
            else:
                exchange_time_data.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            # Fallback: just get the price
            df = rd.get_data(ric, fields=["TR.PriceClose"])
            spot_price_data.set(df["Price Close"].iloc[0])
            exchange_time_data.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

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

        # Add to blotter
        current_blotter = blotter_data.get()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for _, row in arb_df.iterrows():
            trade = {
                "Timestamp": timestamp,
                "Underlying": input.underlying_ric(),
                "Strike": row["K"],
                "Expiry": row["ExpiryDate"].strftime("%Y-%m-%d"),
                "T": f"{row['T']:.3f}",
                "Strategy": row["signal"],
                "Implied_r": f"{row['implied_r']:.4f}",
                "r_diff": f"{row['r_diff']:.4f}",
                "Call_Mid": f"{row['C_mid']:.2f}",
                "Put_Mid": f"{row['P_mid']:.2f}",
            }
            current_blotter.append(trade)

        blotter_data.set(current_blotter)

    @render.data_frame
    def arbitrage_table():
        df = arbitrage_data.get()
        req(df is not None)

        display_df = df[["K", "T", "ExpiryDate", "signal", "implied_r", "r_diff", "C_mid", "P_mid"]].copy()
        display_df.columns = ["Strike", "T (years)", "Expiry", "Signal", "Implied r", "r - rf", "Call Mid", "Put Mid"]
        return display_df

    @render.data_frame
    def blotter_table():
        blotter = blotter_data.get()
        req(len(blotter) > 0)
        return pd.DataFrame(blotter)

    @reactive.effect
    @reactive.event(input.clear_blotter)
    def _clear_blotter():
        blotter_data.set([])

    # ---- 3D surface plot ----
    @render.ui
    def surface_plot():
        surf = surface_data.get()
        req(surf is not None)

        arb_df = arbitrage_data.get()
        if arb_df is None or arb_df.empty:
            return ui.div("No arbitrage data available. Click 'ANALYZE ARBITRAGE' first.")

        # Prepare data for 3D surface
        K_vals = arb_df["K"].values
        T_vals = arb_df["T"].values
        r_vals = arb_df["implied_r"].values

        if len(K_vals) < 3:
            return ui.div("Insufficient data points for 3D surface. Need more strike/expiry combinations.")

        # Create a grid for interpolation
        K_unique = np.sort(np.unique(K_vals))
        T_unique = np.sort(np.unique(T_vals))

        if len(K_unique) < 2 or len(T_unique) < 2:
            return ui.div("Need at least 2 different strikes and 2 different expiries for surface plot.")

        K_grid, T_grid = np.meshgrid(
            np.linspace(K_unique.min(), K_unique.max(), 30),
            np.linspace(T_unique.min(), T_unique.max(), 30)
        )

        # Interpolate r values
        try:
            r_grid = interpolate.griddata(
                (K_vals, T_vals), r_vals, (K_grid, T_grid), method='cubic', fill_value=np.nan
            )

            # Create 3D surface plot
            fig = go.Figure(data=[go.Surface(
                x=K_grid,
                y=T_grid,
                z=r_grid,
                colorscale='Viridis',
                colorbar=dict(title="Implied r")
            )])

            fig.update_layout(
                title="Implied Risk-Free Rate Surface",
                scene=dict(
                    xaxis_title="Strike (K)",
                    yaxis_title="Time to Expiry (T)",
                    zaxis_title="Implied r",
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.3))
                ),
                template="plotly_dark",
                height=600,
                margin=dict(l=0, r=0, t=40, b=0)
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", full_html=False))

        except Exception as e:
            return ui.div(f"Error creating surface plot: {str(e)}")


app = App(app_ui, server)