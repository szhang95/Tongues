import refinitiv.data as rd
import pandas as pd


rd.open_session() # opens your session to refinitiv
                  # if we figure out how to connect WITHOUT the desktop app,
                  # then this is where we'll update the code.

# Get underlying spot
underlying_ric = "TSLA.O"
spot_df = rd.get_data(underlying_ric, ['TR.PriceClose'])
spot = spot_df['Price Close'].iloc[0]
print(f"underlying spot: {spot:.2f}")

# fetches options chain strikes, expiries, and RICs
strikes_and_expiries=rd.discovery.search(
    view = rd.discovery.Views.EQUITY_QUOTES,
    top = 1000, # 'top' controls the max number of rows returned, 1000 is max
    filter = "( SearchAllCategoryv2 eq 'Options' and "
             "(ExpiryDate gt 2025-12-06 and ExpiryDate lt 2026-01-31 and "
             "(StrikePrice ge 400 and StrikePrice le 480) and "
             "ExchangeName xeq 'OPRA' and "
             "(UnderlyingQuoteRIC eq 'TSLA.O')))",
    select = "RIC,CallPutOption,StrikePrice,ExpiryDate"
)
# might be usful to pivot, we'll see
# strikes_and_expiries.pivot(
#     index=['ExpiryDate', 'StrikePrice'],
#     columns='CallPutOption',
#     values='RIC'
# )
print(strikes_and_expiries)

# fetches most recent price info for each ric
price_data = rd.get_data(
    universe=strikes_and_expiries['RIC'].unique().tolist(),
    fields=[
        'CF_BID', 'CF_ASK', 'CF_LAST', 'CF_CLOSE', 'CF_HIGH','CF_LOW',
        'CF_VOLUME', 'CF_DATE', 'TR.OPENPRICE', 'DELTA', 'GAMMA', 'VEGA',
        'THETA', 'RHO', 'THEO_VALUE', 'IMP_VOLT', 'IMP_VOLTA', 'IMP_VOLTB'
    ]
)
print(price_data)

# Merge the price data with strikes_and_expiries
# now have full vol surface information!
options_surface = strikes_and_expiries.merge(
    price_data, on='RIC', how='left'
)

rd.close_session()
