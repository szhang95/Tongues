# # # ----------------------------------
# # # This is a 'helper' py file for the "Equity Derivatives Intraday Analytics: using Python to gather intraday insights on live and expired derivatives" LSEG Developer Article
# # # ----------------------------------

# # ----------------------------------
# # Imports to start with
# # ----------------------------------

import datetime as dt
from datetime import datetime, \
    timedelta  # We use these to manipulate time values
import pandas as pd
import plotly
import \
    matplotlib  # We use `matplotlib` to just in case users do not have an environment suited to `plotly`.
import \
    IPython  # We use `clear_output` for users who wish to loop graph production on a regular basis. We'll use this to `display` data (e.g.: pandas data-frames).
from plotly import subplots
import plotly
import time  # This is to pause our code when it needs to slow down
import numpy as np
import refinitiv.data as rd

try:
    rd.open_session(
        # For more info on the session, use `rd.get_config().as_dict()`
        name="desktop.workspace",
        config_name="C:/Example.DataLibrary.Python-main/Configuration/refinitiv-data.config.json")
    print("We're on 'desktop.workspace' Session")
except:
    rd.open_session()

# # ----------------------------------
# # I'd like to 1st create a workflow that enables us to output clean errors:
# # ----------------------------------
from dataclasses import dataclass


@dataclass(frozen=True)
class ExceptionData:
    data: str


class MyException(Exception):
    def __init__(self, exception_details: ExceptionData):
        self.details = exception_details

    def __str__(self):
        return self.details.data


# # ----------------------------------
# # Now let's create helper functions in the `get_options_RIC` CLass
# # ----------------------------------

class get_options_RIC():

    def __init__(self):  # Constroctor
        return None

    def _get_exchange_code(
            self,
            asset):
        """
        This function retrieves the exchange code for a given equity option.
        The exchange code is determined by the specific characteristics of the asset, which
        may include its market type, geographical location, or other defining attributes.
        These attributes are gathered via LSEG Data.

        Parameters
        -----------------------------------------------
        Inputs:
            - asset (str): The identifier for the asset for which the exchange code is required.

        Output/Returns:
            - list[str]: The exchange codes associated with the asset.
        """

        response = rd.discovery.search(
            query=asset,
            filter="SearchAllCategory eq 'Options' and Periodicity eq 'Monthly' ",
            select='ExchangeCode',
            group_by="ExchangeCode")

        if len(response) == 0:
            raise (MyException(ExceptionData(
                f"It's looking like there might not have been any trades for this option, {asset} on that date. You may want to check with: `rd.discovery.search(query = '{asset}', filter = \"SearchAllCategory eq 'Options'  and Periodicity eq 'Monthly' \", select = 'ExchangeCode', group_by = 'ExchangeCode')`")))

        exchanges = response.drop_duplicates()["ExchangeCode"].to_list()
        exchange_codes = []
        for exchange in exchanges:
            exchange_codes.append(exchange)
        return exchange_codes

    def _get_exp_month(
            self,
            maturity,
            opt_type,
            strike=None,
            opra=False):

        maturity = pd.to_datetime(maturity)
        # define option expiration identifiers
        ident = {
            '1': {'exp': 'A', 'C': 'A', 'P': 'M'},
            '2': {'exp': 'B', 'C': 'B', 'P': 'N'},
            '3': {'exp': 'C', 'C': 'C', 'P': 'O'},
            '4': {'exp': 'D', 'C': 'D', 'P': 'P'},
            '5': {'exp': 'E', 'C': 'E', 'P': 'Q'},
            '6': {'exp': 'F', 'C': 'F', 'P': 'R'},
            '7': {'exp': 'G', 'C': 'G', 'P': 'S'},
            '8': {'exp': 'H', 'C': 'H', 'P': 'T'},
            '9': {'exp': 'I', 'C': 'I', 'P': 'U'},
            '10': {'exp': 'J', 'C': 'J', 'P': 'V'},
            '11': {'exp': 'K', 'C': 'K', 'P': 'W'},
            '12': {'exp': 'L', 'C': 'L', 'P': 'X'}}

        # get expiration month code for a month
        if opt_type.upper() == 'C':
            exp_month = ident[str(maturity.month)]['C']

        elif opt_type.upper() == 'P':
            exp_month = ident[str(maturity.month)]['P']

        if opra and strike > 999.999:
            exp_month = exp_month.lower()

        return ident, exp_month

    def _check_expiry(self, ric, maturity, ident):
        maturity = pd.to_datetime(maturity)
        if maturity < datetime.now():
            ric = ric + '^' + ident[str(maturity.month)]['exp'] + str(
                maturity.year)[-2:]
        return ric

    def _request_prices(self, ric, debug):
        prices = []
        try:
            prices = rd.get_history(ric,
                                    fields=['BID', 'ASK', 'TRDPRC_1', 'SETTLE'])
        except rd.errors.RDError as err:
            if debug:
                print(f'Constructed ric {ric} -  {err}')

            # if self.debug:
            #     print("\n")
            #     print(f"rd.get_history({ric}, fields = ['BID','ASK','TRDPRC_1','SETTLE'])")
            #     print("\n")

        return prices

    def get_ric_opra(self, asset, maturity, strike, opt_type, debug):

        maturity = pd.to_datetime(maturity)

        # trim underlying asset's RIC to get the required part for option RIC
        if asset[0] == '.':  # check if the asset is an index or an equity
            asset_name = asset[
                1:]  # get the asset name - we remove "." symbol for index options
        else:
            asset_name = asset.split('.')[
                0]  # we need only the first part of the RICs for equities

        ident, exp_month = self._get_exp_month(
            maturity=maturity, opt_type=opt_type, strike=strike, opra=True)

        # get strike prrice
        if type(strike) == float:
            int_part = int(strike)
            dec_part = str(str(strike).split('.')[1])
        else:
            int_part = int(strike)
            dec_part = '00'
        if len(dec_part) == 1:
            dec_part = dec_part + '0'

        if int(strike) < 10:
            strike_ric = '00' + str(int_part) + dec_part
        elif int_part >= 10 and int_part < 100:
            strike_ric = '0' + str(int_part) + dec_part
        elif int_part >= 100 and int_part < 1000:
            strike_ric = str(int_part) + dec_part
        elif int_part >= 1000 and int_part < 10000:
            strike_ric = str(int_part) + '0'
        elif int_part >= 10000 and int_part < 20000:
            strike_ric = 'A' + str(int_part)[-4:]
        elif int_part >= 20000 and int_part < 30000:
            strike_ric = 'B' + str(int_part)[-4:]
        elif int_part >= 30000 and int_part < 40000:
            strike_ric = 'C' + str(int_part)[-4:]
        elif int_part >= 40000 and int_part < 50000:
            strike_ric = 'D' + str(int_part)[-4:]

        # build ric
        ric = asset_name + exp_month + str(maturity.day) + str(maturity.year)[
            -2:] + strike_ric + '.U'
        ric = self._check_expiry(ric, maturity, ident)

        prices = self._request_prices(ric, debug=debug)

        # return valid ric(s)
        if len(prices) == 0:
            if debug:
                print('RIC with specified parameters is not found')

        return ric, prices

    def get_ric_hk(self, asset, maturity, strike, opt_type, debug):
        maturity = pd.to_datetime(maturity)

        # get asset name and strike price for the asset
        if asset[0] == '.':
            asset_name = asset[1:]
            strike_ric = str(int(strike))
        else:
            asset_name = asset.split('.')[0]
            strike_ric = str(int(strike * 100))

        # get expiration month codes
        ident, exp_month = self._get_exp_month(maturity, opt_type)

        # get rics for options on indexes. Return if valid add to the possible_rics list if no price is found
        if asset[0] == '.':
            ric = asset_name + strike_ric + exp_month + str(maturity.year)[
                -1:] + '.HF'
            ric = self._check_expiry(ric, maturity, ident)
            prices = self._request_prices(ric, debug=debug)
            if len(prices) == 0:
                if debug:
                    print('RIC with specified parameters is not found')
            else:
                return ric, prices
        else:
            # get rics for options on equities. Return if valid add to the possible_rics list if no price is found
            # there could be several generations of options depending on the number of price adjustments due to a corporate event
            # here we use 4 adjustment opportunities.
            for i in range(4):
                ric = asset_name + strike_ric + str(i) + exp_month + str(
                    maturity.year)[-1:] + '.HK'
                ric = self._check_expiry(ric, maturity, ident)
                prices = self._request_prices(ric, debug=debug)
                if len(prices) == 0:
                    if debug:
                        print('RIC with specified parameters is not found')
                else:
                    return ric, prices
        return ric, prices

    def get_ric_ose(self, asset, maturity, strike, opt_type, debug):

        maturity = pd.to_datetime(maturity)
        strike_ric = str(strike)[:3]
        ident, exp_month = self._get_exp_month(maturity, opt_type)

        j_nets = ['', 'L', 'R']
        generations = ['Y', 'Z', 'A', 'B', 'C']

        if asset[0] == '.':
            index_dict = {'N225': 'JNI', 'TOPX': 'JTI'}
            # Option Root codes for indexes are different from the RIC, so we rename where necessery
            asset_name = index_dict[asset.split('.')[1]]

            # we consider also J-NET (Off-Auction(with "L")) and High  frequency (with 'R') option structures
            for jnet in j_nets:
                ric = asset_name + jnet + strike_ric + exp_month + str(
                    maturity.year)[-1:] + '.OS'
                ric = self._check_expiry(ric, maturity, ident)
                prices = self._request_prices(ric, debug=debug)
                if len(prices) == 0:
                    if debug:
                        print('RIC with specified parameters is not found')
                else:
                    return ric, prices
        else:
            asset_name = asset.split('.')[0]
            # these are generation codes similar to one from HK
            for jnet in j_nets:
                for gen in generations:
                    ric = asset_name + jnet + gen + strike_ric + exp_month + str(
                        maturity.year)[-1:] + '.OS'
                    ric = self._check_expiry(ric, maturity, ident)
                    prices = self._request_prices(ric, debug=debug)
                    if len(prices) == 0:
                        if debug:
                            print('RIC with specified parameters is not found')
                    else:
                        return ric, prices
        return ric, prices

    def get_ric_eurex(self, asset, maturity, strike, opt_type, debug):
        maturity = pd.to_datetime(maturity)

        if asset[0] == '.':
            index_dict = {
                'FTSE': 'OTUK',
                'SSMI': 'OSMI',
                'GDAXI': 'GDAX',
                'ATX': 'FATXA',
                'STOXX50E': 'STXE'}
            asset_name = index_dict[asset.split('.')[1]]
        else:
            asset_name = asset.split('.')[0]

        ident, exp_month = self._get_exp_month(maturity, opt_type)

        if type(strike) == float:
            int_part = int(strike)
            dec_part = str(str(strike).split('.')[1])[0]
        else:
            int_part = int(strike)
            dec_part = '0'
        if len(str(int(strike))) == 1:
            strike_ric = '0' + str(int_part) + dec_part
        else:
            strike_ric = str(int_part) + dec_part

        generations = ['', 'a', 'b', 'c', 'd']
        for gen in generations:
            ric = asset_name + strike_ric + gen + exp_month + str(
                maturity.year)[-1:] + '.EX'
            ric = self._check_expiry(ric, maturity, ident)
            prices = self._request_prices(ric, debug=debug)
            if len(prices) == 0:
                if debug:
                    print('RIC with specified parameters is not found')
            else:
                return ric, prices
        return ric, prices

    def get_ric_ieu(self, asset, maturity, strike, opt_type, debug):
        maturity = pd.to_datetime(maturity)

        if asset[0] == '.':
            index_dict = {'FTSE': 'LFE'}
            asset_name = index_dict[asset.split('.')[1]]
        else:
            asset_name = asset.split('.')[0]

        ident, exp_month = self._get_exp_month(maturity, opt_type)

        if len(str(int(strike))) == 2:
            strike_ric = '0' + str(int(strike))
        else:
            strike_ric = str(int(strike))

        if type(strike) == float and len(str(int(strike))) == 1:
            int_part = int(strike)
            dec_part = str(str(strike).split('.')[1])[0]
            strike_ric = '0' + str(int_part) + dec_part

        generations = ['', 'a', 'b', 'c', 'd']
        for gen in generations:
            ric = asset_name + strike_ric + gen + exp_month + str(
                maturity.year)[-1:] + '.L'
            ric = self._check_expiry(ric, maturity, ident)
            prices = self._request_prices(ric, debug=debug)
            if len(prices) == 0:
                if debug:
                    print(
                        f'Constructed {ric} RIC with specified parameters is not found')
            else:
                return ric, prices
        return ric, prices

    def get_option_ric(self, asset, maturity, strike, opt_type, debug,
                       exchange_not_supported_message_count=0):

        # define covered exchanges along with functions to get RICs from
        exchanges = {
            'OPQ': self.get_ric_opra,
            'IEU': self.get_ric_ieu,
            'EUX': self.get_ric_eurex,
            'HKG': self.get_ric_hk,
            'HFE': self.get_ric_hk,
            'OSA': self.get_ric_ose}

        # get exchanges codes where the option on the given asset is traded
        exchnage_codes = self._get_exchange_code(asset)
        # get the list of (from all available and covered exchanges) valid rics and their prices
        options_data = {}
        for exch in exchnage_codes:
            if exch in exchanges.keys():
                ric, prices = exchanges[exch](asset, maturity, strike, opt_type,
                                              debug)
                if len(prices) != 0:
                    options_data[ric] = prices
                    if debug:
                        print(
                            f'Option RIC for {exch} exchange is successfully constructed')
            else:
                if exchange_not_supported_message_count < 1:
                    print(f'The {exch} exchange is not supported yet')
        return options_data

    def get_option_ric_through_strike_range(
            self,
            asset,
            maturity,
            strike,
            opt_type,
            rnge,
            rnge_interval,
            round_to_nearest,
            debug,
            direction=None):
        """
        direction: None | str
            `direction` can beeither `None`, `"+"` or `"-"`.
            If `direction=None`, then this code will itterate through prices from `strike` up and down in intervals of `interval` until `rnge` an option is found for that 'new strike'.
            If `direction="+"`, then this code will itterate through prices from `strike` up (and NOT down) in intervals of `interval` until `rnge` an option is found for that 'new strike'. This is usually to concentrate only on In The Money Options.
            If `direction="-"`, then this code will itterate through prices from `strike` down (and NOT up) in intervals of `interval` until `rnge` an option is found for that 'new strike'. This is usually to concentrate only on Out Of The Money Options.
            Note that if an Option at the `stike` given exist, then that will be picked, be it with `direction=None` direction="+"` or `direction="-"`.
        """

        if direction == "+":
            if debug:
                print("strike lookthough direction: +")
            new_strike = strike + rnge_interval
        if direction == "-":
            if debug:
                print("strike lookthough direction: -")
            new_strike = strike - rnge_interval
        if direction == None:
            if debug:
                print("strike lookthough direction: o")
            new_strike = strike

        if debug:
            print(f"1st new_strike: {new_strike}")

        optn_ric = self.get_option_ric(
            asset=asset,
            maturity=maturity,
            strike=new_strike,
            opt_type=opt_type,
            debug=debug)

        range_rounded = round(
            (rnge + rnge_interval) / round_to_nearest) * round_to_nearest

        if len(optn_ric) == 0:
            # We are going to loop though exchanges to check is the option is traded there.
            # We are coding defensively, meaning that we may make several calls for the same exchange.
            # To limit the number of 'exchange not supported' messages, if it is not supported, we will use the `exchng_not_sprted_msg_cnt` object.
            exchng_not_sprted_msg_cnt = 0

            for i in range(0, range_rounded, rnge_interval):
                if i < rnge:
                    if len(optn_ric) == 0 and (
                            direction == None or direction == "+"):  # Try and find an Option RIC for a Strike `interval` above the given `strike`:
                        new_strike = (round(
                            strike / round_to_nearest) * round_to_nearest) + i
                        optn_ric = get_options_RIC().get_option_ric(
                            asset=asset, maturity=maturity, opt_type=opt_type,
                            debug=debug,
                            strike=new_strike,
                            exchange_not_supported_message_count=exchng_not_sprted_msg_cnt)
                        exchng_not_sprted_msg_cnt = + 1
                        if debug:
                            print(f"{i} new_strike: {new_strike}")
                    if len(optn_ric) == 0 and (
                            direction == None or direction == "-"):  # Try and find an Option RIC for a Strike `interval` below the given `strike`:
                        new_strike = (round(
                            strike / round_to_nearest) * round_to_nearest) - i
                        optn_ric = get_options_RIC().get_option_ric(
                            asset=asset, maturity=maturity, opt_type=opt_type,
                            debug=debug,
                            strike=new_strike,
                            exchange_not_supported_message_count=exchng_not_sprted_msg_cnt)
                        if debug:
                            print(f"{i} new_strike: {new_strike}")

        return optn_ric, new_strike


# # ----------------------------------
# # Now let's create main `IPA_Equity_Vola_n_Greeeks` CLass
# # ----------------------------------

class IPA_Equity_Vola_n_Greeeks():

    def __init__(
            self,
            debug=False,
            underlying="LSEG.L",  # ".SPX"
            strike=None,
            atm_range=200,
            atm_intervals=50,
            atm_round_to_nearest=100,
            atm_direction=None,
            maturity='2024-01-19',
            maturity_format='%Y-%m-%d',
            # e.g.: '%Y-%m-%d', '%Y-%m-%d %H:%M:%S' or '%Y-%m-%dT%H:%M:%SZ'
            option_type='Call',  # 'Put'
            buy_sell='Buy',  # 'Sell'
            data_retrieval_interval=rd.content.historical_pricing.Intervals.HOURLY,
            curr='USD',
            exercise_style='EURO',
            option_price_side=None,  # `None`, `'Bid'` or `'Ask'`.
            underlying_time_stamp='Close',
            resample='10min',
            # You can consider this the 'bucket' or 'candles' from which calculations will be made.
            rsk_free_rate_prct='USDCFCFCTSA3M=',
            # for `".SPX"`, I go with `'USDCFCFCTSA3M='`; for `".STOXX50E"`, I go with `'EURIBOR3MD='`
            rsk_free_rate_prct_field='TR.FIXINGVALUE',
            # for `".SPX"`, I go with `'TR.FIXINGVALUE'`; for `".STOXX50E"`, I go with `'TR.FIXINGVALUE'` too.
            request_fields=['ErrorMessage', 'AverageSoFar', 'AverageType',
                            'BarrierLevel', 'BarrierType',
                            'BreakEvenDeltaAmountInDealCcy',
                            'BreakEvenDeltaAmountInReportCcy',
                            'BreakEvenPriceInDealCcy',
                            'BreakEvenPriceInReportCcy', 'CallPut',
                            'CbbcOptionType', 'CbbcType',
                            'CharmAmountInDealCcy', 'CharmAmountInReportCcy',
                            'ColorAmountInDealCcy', 'ColorAmountInReportCcy',
                            'ConversionRatio', 'DailyVolatility',
                            'DailyVolatilityPercent', 'DaysToExpiry', 'DealCcy',
                            'DeltaAmountInDealCcy', 'DeltaAmountInReportCcy',
                            'DeltaExposureInDealCcy',
                            'DeltaExposureInReportCcy',
                            'DeltaHedgePositionInDealCcy',
                            'DeltaHedgePositionInReportCcy', 'DeltaPercent',
                            'DividendType', 'DividendYieldPercent',
                            'DvegaDtimeAmountInDealCcy',
                            'DvegaDtimeAmountInReportCcy', 'EndDate',
                            'ExerciseStyle', 'FixingCalendar',
                            'FixingDateArray', 'FixingEndDate',
                            'FixingFrequency', 'FixingNumbers',
                            'FixingStartDate', 'ForecastDividendYieldPercent',
                            'GammaAmountInDealCcy', 'GammaAmountInReportCcy',
                            'GammaPercent', 'Gearing', 'HedgeRatio',
                            'InstrumentCode', 'InstrumentDescription',
                            'InstrumentTag', 'Leverage', 'LotSize', 'LotsUnits',
                            'MarketDataDate', 'MarketValueInDealCcy',
                            'MoneynessAmountInDealCcy',
                            'MoneynessAmountInReportCcy', 'OptionPrice',
                            'OptionPriceSide', 'OptionTimeStamp', 'OptionType',
                            'PremiumOverCashInDealCcy',
                            'PremiumOverCashInReportCcy',
                            'PremiumOverCashPercent',
                            'PremiumPerAnnumInDealCcy',
                            'PremiumPerAnnumInReportCcy',
                            'PremiumPerAnnumPercent', 'PremiumPercent',
                            'PricingModelType', 'PricingModelTypeList',
                            'ResidualAmountInDealCcy',
                            'ResidualAmountInReportCcy', 'RhoAmountInDealCcy',
                            'RhoAmountInReportCcy', 'RhoPercent',
                            'RiskFreeRatePercent',
                            'SevenDaysThetaAmountInDealCcy',
                            'SevenDaysThetaAmountInReportCcy',
                            'SevenDaysThetaPercent', 'SpeedAmountInDealCcy',
                            'SpeedAmountInReportCcy', 'Strike',
                            'ThetaAmountInDealCcy', 'ThetaAmountInReportCcy',
                            'ThetaPercent', 'TimeValueInDealCcy',
                            'TimeValueInReportCcy', 'TimeValuePercent',
                            'TimeValuePerDay', 'TotalMarketValueInDealCcy',
                            'TotalMarketValueInDealCcy',
                            'TotalMarketValueInReportCcy',
                            'TotalMarketValueInReportCcy',
                            'UltimaAmountInDealCcy', 'UltimaAmountInReportCcy',
                            'UnderlyingCcy', 'UnderlyingPrice',
                            'UnderlyingPriceSide', 'UnderlyingRIC',
                            'UnderlyingTimeStamp', 'ValuationDate',
                            'VannaAmountInDealCcy', 'VannaAmountInReportCcy',
                            'VegaAmountInDealCcy', 'VegaAmountInReportCcy',
                            'VegaPercent', 'Volatility', 'VolatilityPercent',
                            'VolatilityType', 'VolgaAmountInDealCcy',
                            'VolgaAmountInReportCcy', 'YearsToExpiry',
                            'ZommaAmountInDealCcy', 'ZommaAmountInReportCcy'],
            search_batch_max=90,
            slep=0.6,
            corr=True,
            hist_vol=True):  # Constroctor
        '''
        IPA_Equity_Vola_n_Greeeks() Python Class Version 1.0:
            This Class was built and tested in Python 3.11.3.

        Dependencies
        ----------------------------------------------
        refinitiv.data version 1.5.1 with an open session (more on https://developers.refinitiv.com/en/api-catalog/refinitiv-data-platform/refinitiv-data-library-for-python/quick-start#getting-started-with-python)
        pandas version 1.5.3
        refinitiv.data version 1.5.1
        plotly version 5.18.0
        matplotlib version 3.8.2
        IPython version 8.17.2
        datetime (native to Python)
        time (native to Python)
        get_options_RIC() Python Class
        '''

        if option_price_side == None:
            self.option_price_side_for_IPA = 'Bid'
        else:
            self.option_price_side_for_IPA = 'Bid'

        self.option_price_side = option_price_side
        self.debug = debug
        self.underlying = underlying
        self.strike = strike
        self._strike = strike  # Let _strike be an 'original press' that we will not change, but keep going back to instead.
        self.atm_range = atm_range
        self.atm_intervals = atm_intervals
        self.atm_round_to_nearest = atm_round_to_nearest
        self.atm_direction = atm_direction
        self.maturity = maturity
        self.maturity_format = maturity_format
        self.option_type = option_type
        self.buy_sell = buy_sell
        self.data_retrieval_interval = data_retrieval_interval
        self.curr = curr
        self.exercise_style = exercise_style
        self.underlying_time_stamp = underlying_time_stamp
        self.resample = resample
        self.rsk_free_rate_prct = rsk_free_rate_prct
        self.rsk_free_rate_prct_field = rsk_free_rate_prct_field
        self.request_fields = request_fields
        self.search_batch_max = search_batch_max
        self.slep = slep
        self.corr = corr
        self.hist_vol = hist_vol

    def initiate(
            self,
            direction='default'):

        if direction == 'default':
            direction = self.atm_direction

        if self.strike == None:
            try_no = 0
            while try_no < 3:
                try:
                    if datetime.strptime(self.maturity,
                                         '%Y-%m-%d') >= datetime.now():
                        strike_maturity_pr_call = datetime.now().strftime(
                            '%Y-%m-%d')
                    else:
                        strike_maturity_pr_call = self.maturity

                    self.strike = \
                    rd.get_history(self.underlying, "TR.ClosePrice",
                                   start=strike_maturity_pr_call).values[0][0]
                    self.strike = round(self.strike, -1)
                    try_no += 1
                except:
                    try_no += 1
            self._strike = self.strike  # Let _strike be an 'original press' that we will not change, but keep going back to instead.

        if self.debug:
            if self.strike == None:
                print(f"strike_maturity_pr_call: {strike_maturity_pr_call}")
            print(f"maturity : {self.maturity}")
            print(f"original strike: {self.strike}")

        _undrlying_optn_ric, new_strike = get_options_RIC().get_option_ric_through_strike_range(
            asset=self.underlying,
            maturity=self.maturity,
            strike=self.strike,
            opt_type=self.option_type[0],
            rnge=self.atm_range,
            rnge_interval=self.atm_intervals,
            round_to_nearest=self.atm_round_to_nearest,
            debug=self.debug,
            direction=direction)

        if self.debug:
            print("1st _undrlying_optn_ric:")
            display(_undrlying_optn_ric)

        if len(_undrlying_optn_ric) == 0:  # having tried up to `atm_range+atm_intervals`, it looks like it's not working
            raise (MyException(ExceptionData(
                f"No Options could be found for strikes starting at {self.strike + (self.atm_range) + self.atm_intervals} and ending at {self.strike - (self.atm_range) - self.atm_intervals}, which were chosen from the midpoint {self.strike} with intervals of {self.atm_intervals} and rounded to the nearest {self.atm_round_to_nearest}. Please try again with a different strike. It may be that the exchange for your equity is not supported yet.")))

        if self.strike != new_strike:
            if self.debug:
                print(
                    f"Note that no Option for Strike {self.strike} was found. Instead, we use Strike {new_strike} going forward")
            self.strike = new_strike

        undrlying_optn_ric = [str(i) for i in _undrlying_optn_ric.keys()][0]
        # pd.DataFrame(_undrlying_optn_ric[undrlying_optn_ric])

        if self.debug:
            print("\n")
            print("_undrlying_optn_ric")
            print(f"2nd {_undrlying_optn_ric}")
            print("\n")
            print("undrlying_optn_ric")
            print(f"{undrlying_optn_ric}")
            print("\n")

        maturity_dtime = pd.Timestamp(self.maturity)
        sdate = (maturity_dtime - timedelta(900)).strftime('%Y-%m-%d')
        edate = maturity_dtime.strftime('%Y-%m-%d')

        # Now things are getting tricky.
        # Certain Expiered Options do not have 'TRDPRC_1' data historically. Some don't have 'SETTLE'. Some have both...
        # The below should capture 'SETTLE' when it is available, but 'TRDPRC_1' might still be present in these instances.
        # So we will need to build a logic to focus on the series with the most datapoints.
        # If there's twice as few 'TRDPRC_1' data points as there are days, I consider
        # that to be too little data, and we then ask for 'SETTLE', then MID (calculated with 'ASK' and 'BID').
        if self.option_price_side is None:
            # If `option_price_side is None`, the user is letting the program choose the field to choose.
            # Below, we will pick the field (if it has data) in this order:
            fields_lst = ['TRDPRC_1', 'SETTLE', 'BID', 'ASK']
        else:
            if self.debug:
                print("self.option_price_side")
                print(self.option_price_side)
                print("self.option_price_side.upper())]:")
                print(self.option_price_side.upper())
            fields_lst = [str(self.option_price_side.upper())]
        if self.debug:
            print(
                f"optn_mrkt_pr_gmt = rd.content.historical_pricing.summaries.Definition(universe='{undrlying_optn_ric}',start='{sdate}',end='{edate}',interval='{self.data_retrieval_interval}',fields={fields_lst}).get_data().data.df")
        optn_mrkt_pr_gmt = rd.content.historical_pricing.summaries.Definition(
            universe=undrlying_optn_ric,
            start=sdate,
            end=edate,
            interval=self.data_retrieval_interval,
            fields=fields_lst
        ).get_data().data.df
        if 'TRDPRC_1' in optn_mrkt_pr_gmt.columns:
            if len(optn_mrkt_pr_gmt.TRDPRC_1.dropna()) > 0:
                optn_mrkt_pr_gmt = pd.DataFrame(
                    data={'TRDPRC_1': optn_mrkt_pr_gmt.TRDPRC_1}).dropna()
        elif 'SETTLE' in optn_mrkt_pr_gmt.columns:
            if len(optn_mrkt_pr_gmt.SETTLE.dropna()) > 0:
                optn_mrkt_pr_gmt = pd.DataFrame(
                    data={'SETTLE': optn_mrkt_pr_gmt.SETTLE}).dropna()
        elif 'BID' in optn_mrkt_pr_gmt.columns:
            if len(optn_mrkt_pr_gmt.BID.dropna()) > 0:
                optn_mrkt_pr_gmt = pd.DataFrame(
                    data={'BID': optn_mrkt_pr_gmt.BID}).dropna()
        else:
            display(optn_mrkt_pr_gmt)
            raise ValueError(
                "Issue with `optn_mrkt_pr_gmt`, as displayed above.")
        optn_mrkt_pr_gmt.columns.name = undrlying_optn_ric

        column_with_fewest_nas = optn_mrkt_pr_gmt.isna().sum().idxmin()
        if self.debug:
            print("column_with_fewest_nas:")
            print(column_with_fewest_nas)

        optn_mrkt_pr_field = column_with_fewest_nas
        df_strt_dt = optn_mrkt_pr_gmt.index[0]
        df_strt_dt_str = df_strt_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
        df_end_dt = optn_mrkt_pr_gmt.index[-1]
        df_end_dt_str = df_end_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')

        if self.debug:
            print(
                f"undrlying_mrkt_pr_gmt = rd.content.historical_pricing.summaries.Definition(universe='{self.underlying}', start='{df_strt_dt_str}', end='{df_end_dt_str}', interval='{self.data_retrieval_interval}', fields='{optn_mrkt_pr_gmt.columns.array[0]}').get_data().data.df")
            print(
                f"optn_mrkt_pr_gmt.columns.array: {optn_mrkt_pr_gmt.columns.array}")
            print("optn_mrkt_pr_gmt 1st")
            display(optn_mrkt_pr_gmt)

        undrlying_mrkt_pr_gmt = rd.content.historical_pricing.summaries.Definition(
            universe=self.underlying,
            start=df_strt_dt_str,
            end=df_end_dt_str,
            interval=self.data_retrieval_interval,
            fields=optn_mrkt_pr_gmt.columns.array[0]
        ).get_data().data.df
        undrlying_mrkt_pr_gmt_cnt = undrlying_mrkt_pr_gmt.count()
        if self.debug:
            print("undrlying_mrkt_pr_gmt 1st")
            print(
                f"rd.content.historical_pricing.summaries.Definition(universe='{self.underlying}', start='{df_strt_dt_str}', end='{df_end_dt_str}', interval='{self.data_retrieval_interval}', fields='{optn_mrkt_pr_gmt.columns.array[0]}').get_data().data.df")
            display(undrlying_mrkt_pr_gmt)
        try:
            undrlying_mrkt_pr_gmt = pd.DataFrame(
                data={'TRDPRC_1': undrlying_mrkt_pr_gmt.TRDPRC_1}).dropna()
        except:
            try:
                undrlying_mrkt_pr_gmt = pd.DataFrame(
                    data={'SETTLE': undrlying_mrkt_pr_gmt.SETTLE}).dropna()
            except:
                try:
                    undrlying_mrkt_pr_gmt = pd.DataFrame(
                        data={'BID': undrlying_mrkt_pr_gmt.BID}).dropna()
                except:
                    raise ValueError(
                        f"There seem to be no data for the field {optn_mrkt_pr_gmt.columns.array[0]}. You may want to choose the option 'Let Program Choose' as opposed to {optn_mrkt_pr_gmt.columns.array[0]}. This came from the function of `as per the function `rd.content.historical_pricing.summaries.Definition(universe='{self.underlying}', start='{df_strt_dt_str}', end='{df_end_dt_str}', interval='{self.data_retrieval_interval}', fields='{optn_mrkt_pr_gmt.columns.array[0]}').get_data().data.df`")

        undrlying_mrkt_pr_gmt.columns.name = f"{self.underlying}"

        if optn_mrkt_pr_gmt.index[-1] >= undrlying_mrkt_pr_gmt.index[-1]:
            df_gmt = optn_mrkt_pr_gmt.copy()
            underlying_pr_field = f"underlying {self.underlying} {optn_mrkt_pr_gmt.columns.array[0]}"
            df_gmt[underlying_pr_field] = undrlying_mrkt_pr_gmt
        else:
            df_gmt = undrlying_mrkt_pr_gmt.copy()
            underlying_pr_field = f"underlying {self.underlying} {optn_mrkt_pr_gmt.columns.array[0]}"
            df_gmt.rename(
                columns={
                    optn_mrkt_pr_gmt.columns.array[0]: underlying_pr_field},
                inplace=True)
            df_gmt[optn_mrkt_pr_gmt.columns.array[0]] = optn_mrkt_pr_gmt
            df_gmt.columns.name = optn_mrkt_pr_gmt.columns.name
        df_gmt.fillna(method='ffill', inplace=True)

        self.df_end_dt = df_end_dt
        self.df_end_dt_str = df_end_dt_str
        self.optn_mrkt_pr_field = optn_mrkt_pr_field
        self.df_strt_dt = df_strt_dt
        self.df_strt_dt_str = df_strt_dt_str
        self.df_end_dt = df_end_dt
        self.df_end_dt_str = df_end_dt_str
        self.underlying_pr_field = underlying_pr_field
        self.df_gmt = df_gmt
        self.optn_mrkt_pr_gmt = optn_mrkt_pr_gmt
        self.undrlying_optn_ric = undrlying_optn_ric

        return self

    def get_history_mult_times(
            self,
            univ,
            flds,
            strt,
            nd,
            trs=6):

        if self.debug:
            print(
                f"rd.get_history(universe={univ}, fields={flds},start='{strt}', end='{nd}')")

        while trs:
            try:
                trs -= 1
                _df = rd.get_history(
                    universe=univ,
                    fields=flds,
                    start=strt, end=nd)
                trs = 0  # break, because no error
            except Exception:  # catch all exceptions
                time.sleep(self.slep)
                _df = None

        if self.debug:
            print(f"_df")
            display(_df)

        if _df is None:  # If `_df` doesn't exist
            print("\n")
            print("Please note that the following failed:")
            print(_df)
            print(
                f"rd.get_history(universe={univ}, fields={flds},start='{strt}', end='{nd}')")
            display(
                rd.get_history(universe=univ, fields=flds, start=strt, end=nd))
            print(f"Please consider another instrument other than {univ}")
            raise ValueError(
                f"Issue with `_df`, itself taken from `rd.get_history(universe={univ}, fields={flds},start='{strt}', end='{nd}')`")

        return _df

    def get_data(self):

        rf_rate_prct = self.get_history_mult_times(
            [self.rsk_free_rate_prct],
            [self.rsk_free_rate_prct_field],
            (self.df_strt_dt - timedelta(days=1)).strftime('%Y-%m-%d'),
            # https://teamtreehouse.com/community/local-variable-datetime-referenced-before-assignment
            (datetime.strptime(self.maturity, self.maturity_format) + timedelta(
                days=1)).strftime('%Y-%m-%d'))

        # rf_rate_prct = rf_rate_prct.resample(
        #     self.resample).mean().fillna(method='ffill')

        if self.debug:
            print("\n")
            print("rf_rate_prct")
            display(rf_rate_prct)
            print("self.df_gmt 1st")
            display(self.df_gmt)
            print("\n")
            print(f"self.optn_mrkt_pr_gmt 2nd")
            display(self.optn_mrkt_pr_gmt)
            print(
                "self.optn_mrkt_pr_gmt.groupby(self.optn_mrkt_pr_gmt.index.date).count().values")
            display(self.optn_mrkt_pr_gmt.groupby(
                self.optn_mrkt_pr_gmt.index.date).count().values)

        if np.amax(self.optn_mrkt_pr_gmt.groupby(
                self.optn_mrkt_pr_gmt.index.date).count().values) == 1:
            raise (MyException(ExceptionData(
                "This function only allows intraday data for now. Only interday data was returned. This may be due to illiquid Options Trading. You may want to ask only for 'Bid' or 'Ask' data as opposed to 'Let Program Choose', if you have not made that choice already, as the latter will prioritise executed trades, of which there may be few.")))

        _df_gmt = self.df_gmt.copy()
        # Convert the index of df_gmt to datetime
        _df_gmt.index = pd.to_datetime(_df_gmt.index)

        # Convert the index of rf_rate_prct to datetime
        rf_rate_prct.index = pd.to_datetime(rf_rate_prct.index)

        # Resample rf_rate_prct to match the frequency of df_gmt, forward filling the missing values
        rf_rate_prct_resampled = rf_rate_prct.resample('T').ffill()

        # Merge the dataframes
        merged_df = _df_gmt.merge(rf_rate_prct_resampled, left_index=True,
                                  right_index=True, how='left')
        merged_df.columns.name = self.df_gmt.columns.name

        if self.debug:
            # Print the merged dataframe
            print("merged_df")
            display(merged_df)
            print("list(merged_df.columns)")
            print(list(merged_df.columns))

        self.df_gmt = merged_df
        self.df_gmt.rename(
            columns={list(merged_df.columns)[-1]: 'RfRatePrct'},
            inplace=True)

        # self.df_gmt['RfRatePrct'] = rf_rate_prct

        if self.debug:
            print("self.df_gmt 2nd")
            display(self.df_gmt)

        self.df_gmt = self.df_gmt.fillna(method='ffill').fillna(method='bfill')

        if self.debug:
            print("self.df_gmt")
            display(self.df_gmt)

        self.df_gmt_no_na = self.df_gmt.dropna(subset=['RfRatePrct'])

        if self.debug:
            print("\n")
            print(
                "self.df_gmt['RfRatePrct'][self.df_gmt.isna().any(axis=1)] : ")
            print("\n")
            display(self.df_gmt['RfRatePrct'][self.df_gmt.isna().any(axis=1)])
            print("\n")
            print("self.df_gmt")
            display(self.df_gmt)
            print("self.df_gmt_no_na")
            display(self.df_gmt_no_na)

        ipa_univ_requ = [
            rd.content.ipa.financial_contracts.option.Definition(
                strike=float(self.strike),
                buy_sell=self.buy_sell,
                underlying_type=rd.content.ipa.financial_contracts.option.UnderlyingType.ETI,
                call_put=self.option_type,
                exercise_style=self.exercise_style,
                end_date=datetime.strptime(self.maturity,
                                           self.maturity_format).strftime(
                    '%Y-%m-%dT%H:%M:%SZ'),
                # '%Y-%m-%dT%H:%M:%SZ' for RD version 1.2.0 # self.maturity.strftime('%Y-%m-%dt%H:%M:%Sz') # datetime.strptime(self.maturity, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%dt%H:%M:%Sz')
                lot_size=1,
                deal_contract=1,
                time_zone_offset=0,
                underlying_definition=rd.content.ipa.financial_contracts.option.EtiUnderlyingDefinition(
                    instrument_code=self.underlying),
                pricing_parameters=rd.content.ipa.financial_contracts.option.PricingParameters(
                    valuation_date=self.df_gmt_no_na.index[i_int].strftime(
                        '%Y-%m-%dT%H:%M:%SZ'),
                    # '%Y-%m-%dT%H:%M:%SZ' for RD version 1.2.0 # '%Y-%m-%dt%H:%M:%Sz' # One version of rd wanted capitals, the other small. Here they are if you want to copy paste.
                    report_ccy=self.curr,
                    market_value_in_deal_ccy=float(
                        self.df_gmt_no_na[self.optn_mrkt_pr_field][i_int]),
                    pricing_model_type='BlackScholes',
                    risk_free_rate_percent=float(
                        self.df_gmt_no_na['RfRatePrct'][i_int]),
                    underlying_price=float(
                        self.df_gmt_no_na[self.underlying_pr_field][i_int]),
                    volatility_type='Implied',
                    option_price_side=self.option_price_side_for_IPA,
                    underlying_time_stamp=self.underlying_time_stamp))
            for i_int in range(len(self.df_gmt_no_na))]

        ipa_univ_requ_debug = [  # For debugging.
            {"strike": float(self.strike),
             "buy_sell": self.buy_sell,
             "underlying_type": rd.content.ipa.financial_contracts.option.UnderlyingType.ETI,
             "call_put": self.option_type,
             "exercise_style": self.exercise_style,
             "end_date": datetime.strptime(self.maturity,
                                           self.maturity_format).strftime(
                 '%Y-%m-%dT%H:%M:%SZ'),
             # '%Y-%m-%dT%H:%M:%SZ' for RD version 1.2.0 # self.maturity.strftime('%Y-%m-%dt%H:%M:%Sz') # datetime.strptime(self.maturity, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%dt%H:%M:%Sz')
             "lot_size": 1,
             "deal_contract": 1,
             "time_zone_offset": 0,
             "underlying_definition": {"instrument_code": self.underlying},
             "pricing_parameters": {
                 "valuation_date": self.df_gmt_no_na.index[i_int].strftime(
                     '%Y-%m-%dT%H:%M:%SZ'),
                 # '%Y-%m-%dT%H:%M:%SZ' for RD version 1.2.0 # '%Y-%m-%dt%H:%M:%Sz' # One version of rd wanted capitals, the other small. Here they are if you want to copy paste.
                 "report_ccy": self.curr,
                 "market_value_in_deal_ccy": float(
                     self.df_gmt_no_na[self.optn_mrkt_pr_field][i_int]),  #
                 "pricing_model_type": 'BlackScholes',
                 "risk_free_rate_percent": float(
                     self.df_gmt_no_na['RfRatePrct'][i_int]),
                 "underlying_price": float(
                     self.df_gmt_no_na[self.underlying_pr_field][i_int]),
                 "volatility_type": 'Implied',
                 "option_price_side": self.option_price_side_for_IPA,
                 "underlying_time_stamp": self.underlying_time_stamp}}
            for i_int in range(len(self.df_gmt_no_na))]
        ipa_univ_requ_debug_buckets = [i_rdf_bd_dbg for i_rdf_bd_dbg in [
            ipa_univ_requ_debug[j_int:j_int + self.search_batch_max] for j_int
            in range(0, len(ipa_univ_requ_debug),
                     self.search_batch_max)]]  # For debugging.

        for i_str in ["ErrorMessage", "MarketValueInDealCcy",
                      "RiskFreeRatePercent", "UnderlyingPrice", "Volatility"][
            ::-1]:  # We would like to keep a minimum of these fields in the Search Responce in order to construct following graphs.
            request_fields = [i_str] + self.request_fields
        i_int = 0
        _request_fields = request_fields.copy()

        # if self.debug:
        #     print("\n")
        #     print("ipa_univ_requ")
        #     print("\n")
        #     print(ipa_univ_requ)
        #     print("\n")

        no_of_ipa_calls = len(
            [ipa_univ_requ[j_int:j_int + self.search_batch_max] for j_int in
             range(0, len(ipa_univ_requ), self.search_batch_max)])
        if no_of_ipa_calls > 100 or self.debug:
            print(
                f"There are {no_of_ipa_calls} to make. This may take a long while. If this is too long, please consider changing the `IPA_Equity_Vola_n_Greeeks` argument from {self.data_retrieval_interval} to a longer interval")

        for enum, i_rdf_bd in enumerate(
                [ipa_univ_requ[j_int:j_int + self.search_batch_max] for j_int in
                 range(0, len(ipa_univ_requ),
                       self.search_batch_max)]):  # This list chunks our `ipa_univ_requ` in batches of `search_batch_max`

            # IPA may sometimes come back to us saying that Implied VOlatilities cannot be computed. This can happen sometimes due to extreme Moneyness and closeness to expiration. To investigate these issues, we create this 1st try loop:
            try:
                try:  # One issue we may encounter here is that the field 'ErrorMessage' in `request_fields` may break the `get_data()` call and therefore the for loop. we may therefore have to remove 'ErrorMessage' in the call; ironically when it is most useful.
                    ipa_df_get_data_return = rd.content.ipa.financial_contracts.Definitions(
                        universe=i_rdf_bd, fields=request_fields).get_data()
                except:  # https://stackoverflow.com/questions/11520492/difference-between-del-remove-and-pop-on-lists
                    _request_fields.remove('ErrorMessage')
                    ipa_df_get_data_return = rd.content.ipa.financial_contracts.Definitions(
                        universe=i_rdf_bd, fields=request_fields).get_data()
            except:
                if self.debug:
                    print("request_fields")
                    print(request_fields)
                    print(f"ipa_univ_requ_debug_buckets[{enum}]")
                    display(ipa_univ_requ_debug_buckets[enum])
                _request_fields.remove('ErrorMessage')
                ipa_df_get_data_return = rd.content.ipa.financial_contracts.Definitions(
                    universe=i_rdf_bd, fields=request_fields).get_data()

            _ipa_df_gmt_no_na = ipa_df_get_data_return.data.df
            if i_int == 0:
                ipa_df_gmt_no_na = _ipa_df_gmt_no_na.drop("ErrorMessage",
                                                          axis=1)  # We only keep "ErrorMessage" for debugging in self._IPA_df.
            else:
                ipa_df_gmt_no_na = pd.concat(
                    [ipa_df_gmt_no_na,
                     _ipa_df_gmt_no_na.drop(labels=["ErrorMessage"], axis=1)],
                    ignore_index=True)
            i_int += 1
            time.sleep(1)
            if self.debug:
                print(i_int)
            if not self.debug and no_of_ipa_calls > 100:
                print(i_int)

        if self.debug and len(ipa_df_gmt_no_na) > 0:
            print("ipa_df_gmt_no_na 1st:")
            display(ipa_df_gmt_no_na)

        ipa_df_gmt_no_na.index = self.df_gmt_no_na.index
        ipa_df_gmt_no_na.columns.name = self.df_gmt_no_na.columns.name

        self.df = ipa_df_gmt_no_na.copy()
        if self.corr:
            # silense a PerformanceWarinng
            import warnings
            warnings.simplefilter(action='ignore',
                                  category=pd.errors.PerformanceWarning)
            # Now add the new column for correnation
            corr_df = self.df['OptionPrice'].ffill().rolling(window=63).corr(
                self.df['Volatility'].ffill())
            # corr_df = pd.to_numeric(self.df['OptionPrice'].ffill().rolling(window=63).corr(self.df['Volatility'].ffill()))
            self.df['3M(63WorkDay)MovCorr(StkprImpvola)'] = corr_df
        if self.hist_vol:
            # Resample data to daily frequency by taking the mean of intraday data
            self.df_daily = self.df.select_dtypes(
                include=[np.number]).resample(rule='B').mean()
            for i in ["OptionPrice", "UnderlyingPrice"]:
                # Forward fill it to get rid on NAs that represent a lack of movement in price
                self.df_daily[i] = self.df_daily[i].ffill()
                # Calculate the Historical Volatility on a 30 day moving window and implement it in main dataframe
                self.df_daily[f'30DHist{i}DailyVolatility'] = self.df_daily[
                    i].rolling(window=30).std()
                self.df_daily[f'30DHist{i}DailyVolatilityAnnualized'] = \
                self.df_daily[f'30DHist{i}DailyVolatility'] * np.sqrt(252)
                self.df = pd.merge_asof(
                    self.df,
                    self.df_daily[[f'30DHist{i}DailyVolatility',
                                   f'30DHist{i}DailyVolatilityAnnualized']],
                    left_index=True, right_index=True, direction='backward')

        self._request_fields = _request_fields
        self.rf_rate_prct = rf_rate_prct
        self.ipa_univ_requ = ipa_univ_requ
        self.ipa_df_gmt_no_na = ipa_df_gmt_no_na
        return self

    def graph(
            self,
            title=None,
            corr=True,
            hist_vol=True,
            df=None,
            graph_template='plotly_dark',
            req_flds=["OptionPrice", "MarketValueInDealCcy",
                      "RiskFreeRatePercent", "UnderlyingPrice", "Volatility",
                      "VolatilityPercent", "DeltaPercent", "GammaPercent",
                      "RhoPercent", "ThetaPercent", "VegaPercent", "Leverage",
                      "Gearing", "HedgeRatio", "DailyVolatility",
                      "DailyVolatilityPercent", "Strike", "YearsToExpiry"]
    ):

        # `plotly` is a library used to render interactive graphs:
        import plotly.graph_objects as go
        import \
            plotly.express as px  # This is just to see the implied vol graph when that field is available
        import \
            matplotlib.pyplot as plt  # We use `matplotlib` to just in case users do not have an environment suited to `plotly`.

        if df == None:
            df = self.df
        if corr and self.corr:
            req_flds.append("3M(63WorkDay)MovCorr(StkprImpvola)")
        if hist_vol and self.hist_vol:
            for i in ["OptionPrice", "UnderlyingPrice"]:
                req_flds.append(f"30DHist{i}DailyVolatility")
                req_flds.append(f"30DHist{i}DailyVolatilityAnnualized")
        req_flds = list(dict.fromkeys(
            req_flds))  # remove potential duplicates in the list and keep only unique and different str elements while keepint the original order.

        if title == None:
            title = self.ipa_df_gmt_no_na.columns.name

        df_graph = df[req_flds].fillna(np.nan).astype(float)
        fig = px.line(df_graph)

        fig.update_layout(
            title=title,
            template=graph_template)
        fig.for_each_trace(
            lambda t: t.update(
                visible=True if t.name in df.columns[:1] else "legendonly"))

        self.df_graph = df_graph
        self.fig = fig
        return self

    def cross_moneyness(
            self,
            smile_range=4
    ):

        # We're going to append to our 3 lists:
        undrlying_optn_ric_lst = []
        strikes_lst = []
        df_gmt_lst = []
        df_lst = []
        fig_lst = []
        first_strike = self.strike
        first_undrlying_optn_ric = self.undrlying_optn_ric
        first_df_gmt = self.df_gmt
        first_df = self.df
        first_fig = self.fig

        # Let's itterate down strikes up to the lower limit `smile_range`
        for i in range(smile_range):
            # try:
            self.initiate(direction="-").get_data().graph()
            if self.debug:
                print("self.strike")
                print(self.strike)
                print("self._strike")
                print(self._strike)
            undrlying_optn_ric_lst.append(self.undrlying_optn_ric)
            strikes_lst.append(self.strike)
            df_gmt_lst.append(self.df_gmt)
            df_lst.append(self.df)
            fig_lst.append(self.fig)
            # except:
            #     print(f"failed at strike {self.strike}")

        # Up to now, we collected data per strike, going down, but we want a list from the lowest strike going up:
        strikes_lst = strikes_lst[
            ::-1]  # `[::-1]` reverses the order of our list
        undrlying_optn_ric_lst = undrlying_optn_ric_lst[::-1]
        df_gmt_lst = df_gmt_lst[::-1]
        df_lst = df_lst[::-1]
        fig_lst = fig_lst[::-1]

        # We skipped the strike we already collected data for before calling on `single_date_smile`
        strikes_lst.append(first_strike)
        undrlying_optn_ric_lst.append(first_undrlying_optn_ric)
        df_gmt_lst.append(first_df_gmt)
        df_lst.append(first_df)
        fig_lst.append(first_fig)

        # Now let's itterate up strikes up to the upper limit `smile_range`
        self.strike = self._strike + self.atm_intervals
        for i in range(smile_range):
            # try:
            self.initiate(direction="+").get_data().graph()
            undrlying_optn_ric_lst.append(self.undrlying_optn_ric)
            strikes_lst.append(self.strike)
            df_gmt_lst.append(self.df_gmt)
            df_lst.append(self.df)
            fig_lst.append(self.fig)
            # except:
            #     print(f"failed at strike {self.strike}")

        return strikes_lst, undrlying_optn_ric_lst, df_gmt_lst, df_lst, fig_lst
