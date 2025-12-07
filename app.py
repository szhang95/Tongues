from shiny import App, render, ui
import pandas as pd
import refinitiv.data as rd


# Task for today:
# Add inputs to this app so that the user can select where they want to hunt
#   for arb opportunities in the options chain
# they need to be able to select:
# 1) Underlying
# 2) strike price range
# 3) Expiry date range

# You probably also want to add a button called "fetch chain" or something
# because you don't want the app to try to fetch the options chain for an
# asset before the user is finished typing out the RIC.

# Also add some funcionality that lets the user see where the underlying is
# trading so that they have a better idea of what strike price range to look at

# one SIMPLE way to do that would be to get the most recent stock price,
# for example:

# Get underlying spot
# underlying_ric = "TSLA.O"
# spot_df = rd.get_data(underlying_ric, ['TR.PriceClose'])
# spot = spot_df['Price Close'].iloc[0]
# print(f"TSLA spot: {spot:.2f}")

# ...but a graph of recent prices -- mayube a nice candlestick plot -- would
# be great :)
# mplfinance or plotly both will do that for you if you fetch OPEN HIGH LOW
# CLOSE data

# also maybe start thinking about your UI color scheme
# you can make it cute and pink, you can make it sci-fi, you can make it
# black and professional finance, whatever you think is best, but you can
# choose a color scheme with packages like these: https://shiny.posit.co/py/docs/ui-customize.html


app_ui = ui.page_fillable(
    ui.input_text("underlying", "Enter an underlying RIC", value = "MSFT.O"),
    ui.output_data_frame("strikes_and_expiries")
)

def server(input, output, session):
    rd.open_session()
    session.on_ended(rd.close_session)

    @render.data_frame
    def strikes_and_expiries():
        # Create a sample dataframe
        strikes_and_expiries_df = rd.discovery.search(
            view=rd.discovery.Views.EQUITY_QUOTES,
            top=10,
            filter="( SearchAllCategoryv2 eq 'Options' and "
                   "(ExpiryDate gt 2025-12-06 and ExpiryDate lt 2026-01-31 and "
                   "(StrikePrice ge 300 and StrikePrice le 500) and "
                   "ExchangeName xeq 'OPRA' and "
                   f"(UnderlyingQuoteRIC eq '{input.underlying()}')))",
            select="DTSubjectName,AssetState,BusinessEntity,PI,ExchangeName,CallPutOption,StrikePrice,ExpiryDate,RIC,UnderlyingQuoteRIC,UnderlyingIssuerName,ExchangeCode,UnderlyingRCSAssetCategoryLeaf"
        )
        return strikes_and_expiries_df


app = App(app_ui, server)
app.run()