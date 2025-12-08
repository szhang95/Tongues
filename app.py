from shiny import App, render, ui, reactive
import refinitiv.data as rd


app_ui = ui.page_sidebar(

    ui.sidebar(
        ui.input_selectize(
            "underlying",
            "Underlying RIC",
            choices=[
                "AAPL.O", "MSFT.O", "TSLA.O", "NVDA.O", "AMZN.O",
                "META.O", "GOOGL.O", "NFLX.O", "AMD.O", "INTC.O",
                "JPM.N", "GS.N"
            ],
            selected="MSFT.O",
            options={"maxItems": 1}
        ),

        ui.input_numeric("min_strike", "Min Strike", value=300),
        ui.input_numeric("max_strike", "Max Strike", value=500),

        ui.input_date("min_expiry", "Min Expiry", value="2025-12-06"),
        ui.input_date("max_expiry", "Max Expiry", value="2026-01-31"),

        ui.input_action_button("fetch_chain", "Fetch Option Chain")
    ),

    ui.h2("Options Arbitrage Scanner"),

    ui.h4("Underlying Spot Price"),
    ui.output_text("spot_price"),

    ui.h4("Options Chain"),
    ui.output_data_frame("strikes_and_expiries")
)


def server(input, output, session):

    rd.open_session()
    session.on_ended(rd.close_session)

    @render.text
    @reactive.event(input.fetch_chain)
    def spot_price():
        ric = input.underlying()
        spot_df = rd.get_data(ric, ['TR.PriceClose'])
        spot = spot_df['Price Close'].iloc[0]
        return f"{ric} Spot: {spot:.2f}"

    @render.data_frame
    @reactive.event(input.fetch_chain)
    def strikes_and_expiries():

        ric = input.underlying()
        min_strike = input.min_strike()
        max_strike = input.max_strike()
        min_expiry = input.min_expiry()
        max_expiry = input.max_expiry()

        filter_str = (
            "( SearchAllCategoryv2 eq 'Options' and "
            f"(ExpiryDate gt {min_expiry} and ExpiryDate lt {max_expiry}) and "
            f"(StrikePrice ge {min_strike} and StrikePrice le {max_strike}) and "
            "ExchangeName xeq 'OPRA' and "
            f"(UnderlyingQuoteRIC eq '{ric}'))"
        )

        df = rd.discovery.search(
            view=rd.discovery.Views.EQUITY_QUOTES,
            top=500,
            filter=filter_str,
            select="RIC,CallPutOption,StrikePrice,ExpiryDate"
        )

        return df


app = App(app_ui, server)
app.run()
