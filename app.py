from shiny import App, render, ui, reactive
import refinitiv.data as rd
import pandas as pd
from datetime import datetime

app_ui = ui.page_fillable(
    ui.tags.head(
        ui.tags.link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/"
                 "css2?family=Inter:wght@400;500;600;700&display=swap"
        )
    ),

    ui.div(
        {
            "class": "container-fluid",
            "style": "max-width: 1800px; margin: 0 auto;"
        },

        # 顶部导航栏
        ui.div(
            {"class": "row",
             "style": "background: #0a0e27; border-bottom: 1px solid #1e2640; "
                      "padding: 20px 30px; margin-bottom: 0;"
             },
            ui.div(
                {"class": "col-6"},
                ui.div(
                    ui.h4(
                        "Devil Tongues",
                        style="color: #fff; margin: 0; "
                              "font-weight: 700; letter-spacing: 2px;"
                    ),
                    ui.p(
                        "Options Chain Analysis with Refinitiv",
                        style="color: #64748b; margin: 5px 0 0 0; "
                              "font-size: 0.85rem;"
                    )
                )
            ),
            ui.div(
                {"class": "col-6 text-end"},
                ui.div(
                    ui.span(
                        "Local Time:",
                        style="color: #10b981; font-weight: 600; "
                              "margin-right: 8px;"
                    ),
                    ui.span(
                        id="timestamp",
                        style="color: #94a3b8; font-size: 0.9rem;"
                    )
                )
            )
        ),

        ui.div(
            {"class": "row", "style": "margin-top: 30px;"},

            # 左侧控制面板
            ui.div(
                {"class": "col-md-3"},

                # 参数配置
                ui.div(
                    {
                        "class": "panel",
                        "style": "background: #0f172a; "
                                 "border: 1px solid #1e293b; "
                                 "border-radius: 8px; padding: 24px; "
                                 "margin-bottom: 20px;"
                    },
                    ui.h6(
                        "Data Selection",
                        style="color: #64748b; font-weight: 600; "
                              "letter-spacing: 1px; margin-bottom: 20px; "
                              "font-size: 0.75rem;"
                    ),
                    ui.div(
                        {"style": "margin-bottom: 20px;"},
                        ui.tags.label(
                            "Underlying Asset RIC",
                            style="color: #94a3b8; font-size: 0.85rem; "
                                  "font-weight: 500;"
                        ),
                        ui.input_selectize(
                            "underlying_ric",
                            None,
                            choices=[
                                "AAPL.O", "MSFT.O", "TSLA.O", "NVDA.O",
                                "AMZN.O", "META.O", "GOOGL.O", "NFLX.O",
                                "AMD.O", "INTC.O", "JPM.N", "GS.N"
                            ],
                            selected="MSFT.O",
                            options={"maxItems": 1}
                        )
                    ),

                    ui.div(
                        {
                            "style": "background: #1e293b; padding: 16px; "
                                     "border-radius: 6px; margin-bottom: 20px;"
                        },
                        ui.div(
                            ui.tags.label(
                                "Strike Range",
                                style="color: #94a3b8; "
                                      "font-size: 0.85rem; "
                                      "font-weight: 500; "
                                      "margin-bottom: 12px; "
                                      "display: block;"
                            ),
                            ui.div(
                                {"class": "row g-2"},
                                ui.div(
                                    {"class": "col-6"},
                                    ui.input_numeric(
                                        "min_strike", "Min", value=300
                                    )
                                ),
                                ui.div(
                                    {"class": "col-6"},
                                    ui.input_numeric(
                                        "max_strike", "Max", value=500
                                    )
                                )
                            )
                        )
                    ),

                    ui.div(
                        {
                            "style": "background: #1e293b; padding: 16px; "
                                     "border-radius: 6px; margin-bottom: 24px;"
                        },
                        ui.div(
                            ui.tags.label(
                                "Expiry Range",
                                style="color: #94a3b8; "
                                      "font-size: 0.85rem; "
                                      "font-weight: 500; "
                                      "margin-bottom: 12px; "
                                      "display: block;"
                            ),
                            ui.div(
                                {"class": "row g-2"},
                                ui.div(
                                    {"class": "col-6"},
                                    ui.input_date(
                                        "min_expiry",
                                        "From",
                                        value="2025-12-06"
                                    )
                                ),
                                ui.div(
                                    {"class": "col-6"},
                                    ui.input_date(
                                        "max_expiry",
                                        "To",
                                        value="2026-01-31"
                                    )
                                )
                            )
                        )
                    ),

                    ui.input_action_button(
                        "fetch_chain",
                        "SCAN OPTIONS",
                        class_="w-100",
                        style="background: #3b82f6; "
                              "color: white; border: none; padding: 14px; "
                              "font-weight: 600; font-size: 0.9rem; "
                              "letter-spacing: 1px; border-radius: 6px; "
                              "transition: all 0.2s;"
                    )
                )
            ),

            # 右侧主要内容区
            ui.div(
                {"class": "col-md-9"},

                # 顶部指标卡片
                ui.div(
                    {"class": "row g-3 mb-4"},

                    # 现货价格
                    ui.div(
                        {"class": "col-md-4"},
                        ui.div(
                            {
                                "class": "metric-card",
                                "style": "background: linear-gradient("
                                         "135deg, #1e40af 0%, #3b82f6 100%); "
                                         "border-radius: 8px; "
                                         "padding: 24px; "
                                         "height: 100%;"
                            },
                            ui.div(
                                ui.div(
                                    "SPOT PRICE",
                                    style="color: rgba(255,255,255,0.8); "
                                          "font-size: 0.75rem; "
                                          "font-weight: 600; "
                                          "letter-spacing: 1px; "
                                          "margin-bottom: 8px;"
                                ),
                                ui.div(
                                    ui.output_text("spot_price"),
                                    style="color: white; font-size: 2rem; "
                                          "font-weight: 700; "
                                          "margin-bottom: 4px;"
                                ),
                                ui.div(
                                    "Real-time quote",
                                    style="color: rgba(255,255,255,0.7); "
                                          "font-size: 0.8rem;"
                                )
                            )
                        )
                    ),

                    # 期权数量
                    ui.div(
                        {"class": "col-md-4"},
                        ui.div(
                            {
                                "class": "metric-card",
                                "style": "background: #0f172a; "
                                         "border: 1px solid #1e293b; "
                                         "border-radius: 8px; "
                                         "padding: 24px; height: 100%;"
                            }
                        )
                    ),

                    # 到期日范围
                    ui.div(
                        {"class": "col-md-4"},
                        ui.div(
                            {
                                "class": "metric-card",
                                "style": "background: #0f172a; "
                                         "border: 1px solid #1e293b; "
                                         "border-radius: 8px; "
                                         "padding: 24px; height: 100%;"
                            },
                            ui.div(
                                ui.div(
                                    "EXPIRY RANGE",
                                    style="color: #64748b; "
                                          "font-size: 0.75rem; "
                                          "font-weight: 600; "
                                          "letter-spacing: 1px; "
                                          "margin-bottom: 8px;"
                                ),
                                ui.div(
                                    ui.output_text("expiry_info"),
                                    style="color: #10b981; font-size: 1.4rem; "
                                          "font-weight: 700; "
                                          "margin-bottom: 4px;"
                                )
                            )
                        )
                    )
                ),

                # 图表区域
                ui.div(
                    {"class": "row g-3 mb-4"},
                    ui.div(
                        {"class": "col-md-8"},
                        ui.div(
                            {"class": "panel",
                             "style": "background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 24px;"},
                            ui.h6("STRIKE DISTRIBUTION",
                                  style="color: #64748b; font-weight: 600; letter-spacing: 1px; margin-bottom: 20px; font-size: 0.75rem;"),
                            ui.output_ui("strike_chart")
                        )
                    ),
                    ui.div(
                        {"class": "col-md-4"},
                        ui.div(
                            {"class": "panel",
                             "style": "background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 24px; height: 100%;"},
                            ui.h6("INTERPRETATION GUIDE",
                                  style="color: #64748b; font-weight: 600; letter-spacing: 1px; margin-bottom: 20px; font-size: 0.75rem;"),
                            ui.output_ui("interpretation_guide")
                        )
                    )
                ),

                # Trading Strategy Analysis
                ui.div(
                    {"class": "row g-3 mb-4"},
                    ui.div(
                        {"class": "col-12"},
                        ui.div(
                            {"class": "panel",
                             "style": "background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 24px;"},
                            ui.h6("TRADING STRATEGY ANALYSIS",
                                  style="color: #64748b; font-weight: 600; letter-spacing: 1px; margin-bottom: 20px; font-size: 0.75rem;"),
                            ui.output_ui("strategy_analysis")
                        )
                    )
                ),

                # 数据表格
                ui.div(
                    {"class": "panel",
                     "style": "background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 24px;"},
                    ui.h6("OPTIONS CHAIN",
                          style="color: #64748b; font-weight: 600; letter-spacing: 1px; margin-bottom: 20px; font-size: 0.75rem;"),
                    ui.output_data_frame("strikes_and_expiries")
                )
            )
        )
    ),

    # 自定义CSS
    ui.tags.style("""
        * {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        body {
            background: #020617;
            color: #e2e8f0;
        }
        .container-fluid {
            padding: 0;
        }
        input, select, .selectize-input {
            background: #1e293b !important;
            border: 1px solid #334155 !important;
            color: #e2e8f0 !important;
            border-radius: 6px !important;
            font-size: 0.9rem !important;
        }
        input:focus, select:focus, .selectize-input.focus {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
        }
        .selectize-dropdown {
            background: #1e293b !important;
            border: 1px solid #334155 !important;
            border-radius: 6px !important;
        }
        .selectize-dropdown-content .option {
            color: #e2e8f0 !important;
            padding: 8px 12px !important;
        }
        .selectize-dropdown-content .option:hover,
        .selectize-dropdown-content .active {
            background: #334155 !important;
            color: #fff !important;
        }
        label {
            color: #94a3b8;
            font-weight: 500;
            font-size: 0.85rem;
            margin-bottom: 8px;
        }
        .btn-primary, button {
            transition: all 0.2s;
        }
        .btn-primary:hover, button:hover {
            background: #2563eb !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }
        .metric-card {
            transition: transform 0.2s;
        }
        .metric-card:hover {
            transform: translateY(-2px);
        }
        .panel {
            transition: border-color 0.2s;
        }
        .panel:hover {
            border-color: #334155 !important;
        }
        table {
            color: #e2e8f0 !important;
        }
        table thead th {
            background: #1e293b !important;
            color: #64748b !important;
            font-weight: 600 !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.5px !important;
            text-transform: uppercase !important;
            border-bottom: 2px solid #334155 !important;
        }
        table tbody td {
            border-bottom: 1px solid #1e293b !important;
            font-size: 0.9rem !important;
        }
        table tbody tr:hover {
            background: #1e293b !important;
        }
        .dataframe {
            background: transparent !important;
        }
    """),

    # JavaScript for timestamp
    ui.tags.script("""
        function updateTimestamp() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-US', { 
                hour12: false, 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
            });
            const dateStr = now.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                year: 'numeric' 
            });
            const el = document.getElementById('timestamp');
            if (el) {
                el.textContent = dateStr + ' ' + timeStr + ' EST';
            }
        }
        updateTimestamp();
        setInterval(updateTimestamp, 1000);
    """)
)


def server(input, output, session):
    rd.open_session()
    session.on_ended(rd.close_session)

    option_data = reactive.Value(None)
    spot_price_data = reactive.Value(None)

    # Main data fetch function - only this one calls the API
    @reactive.effect
    @reactive.event(input.fetch_chain)
    def fetch_all_data():
        try:
            ric = input.underlying_ric()
            print(f"Fetching data for {ric}...")

            # Fetch spot price
            spot_df = rd.get_data(ric, ['TR.PriceClose'])
            spot = spot_df['Price Close'].iloc[0]
            spot_price_data.set(spot)
            print(f"Spot price: ${spot:.2f}")

            # Fetch options chain
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

            if df is None or len(df) == 0:
                print("No options data returned")
                df = pd.DataFrame(columns=['RIC', 'CallPutOption', 'StrikePrice', 'ExpiryDate'])
            else:
                print(f"Fetched {len(df)} option contracts")

            option_data.set(df)

        except Exception as e:
            print(f"Error fetching data: {str(e)}")
            import traceback
            traceback.print_exc()
            spot_price_data.set(None)
            option_data.set(pd.DataFrame(columns=['RIC', 'CallPutOption', 'StrikePrice', 'ExpiryDate']))

    @render.text
    def spot_price():
        spot = spot_price_data.get()
        if spot is None:
            return "Click 'SCAN OPTIONS'"
        return f"${spot:.2f}"

    @render.text
    def contract_count():
        df = option_data.get()
        if df is not None and len(df) > 0:
            return f"{len(df):,}"
        return "0"

    @render.text
    def expiry_info():
        min_date = input.min_expiry()
        max_date = input.max_expiry()
        try:
            from datetime import datetime
            min_dt = datetime.strptime(str(min_date), '%Y-%m-%d')
            max_dt = datetime.strptime(str(max_date), '%Y-%m-%d')
            days = (max_dt - min_dt).days
            return f"{days} days"
        except:
            return "N/A"

    @render.ui
    def strike_chart():
        df = option_data.get()
        if df is None or len(df) == 0:
            return ui.div("Click 'SCAN OPTIONS' to load data",
                          style="color: #64748b; text-align: center; padding: 60px; font-size: 1.1rem;")

        try:
            # 检查必要的列是否存在
            if 'StrikePrice' not in df.columns or 'CallPutOption' not in df.columns:
                return ui.div("Invalid data format", style="color: #ef4444; text-align: center; padding: 40px;")

            # 统计每个行权价的Call和Put数量
            strike_counts = df.groupby(['StrikePrice', 'CallPutOption']).size().unstack(fill_value=0)

            # 确保数据不为空
            if len(strike_counts) == 0:
                return ui.div("No strike data available", style="color: #64748b; text-align: center; padding: 40px;")

            # 创建HTML柱状图
            max_count = max(strike_counts.get('Call', [0]).max(), strike_counts.get('Put', [0]).max())
            if max_count == 0:
                max_count = 1

            html_parts = ["""
            <div style="padding: 20px;">
                <div style="display: flex; justify-content: flex-end; margin-bottom: 20px; gap: 20px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="width: 16px; height: 16px; background: #10b981; border-radius: 3px;"></div>
                        <span style="color: #94a3b8; font-size: 0.9rem;">Calls</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="width: 16px; height: 16px; background: #ef4444; border-radius: 3px;"></div>
                        <span style="color: #94a3b8; font-size: 0.9rem;">Puts</span>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(80px, 1fr)); gap: 12px; max-height: 300px; overflow-y: auto;">
            """]

            for strike in sorted(strike_counts.index):
                calls = strike_counts.loc[strike, 'Call'] if 'Call' in strike_counts.columns else 0
                puts = strike_counts.loc[strike, 'Put'] if 'Put' in strike_counts.columns else 0

                call_height = int((calls / max_count) * 150) if calls > 0 else 0
                put_height = int((puts / max_count) * 150) if puts > 0 else 0

                html_parts.append(f"""
                <div style="text-align: center;">
                    <div style="display: flex; justify-content: center; align-items: flex-end; gap: 4px; height: 160px; margin-bottom: 8px;">
                        <div style="width: 30px; height: {call_height}px; background: #10b981; border-radius: 4px 4px 0 0; position: relative; transition: all 0.3s;" title="Calls: {calls}">
                            {f'<span style="position: absolute; top: -20px; left: 50%; transform: translateX(-50%); color: #10b981; font-size: 0.75rem; font-weight: 600;">{calls}</span>' if calls > 0 else ''}
                        </div>
                        <div style="width: 30px; height: {put_height}px; background: #ef4444; border-radius: 4px 4px 0 0; position: relative; transition: all 0.3s;" title="Puts: {puts}">
                            {f'<span style="position: absolute; top: -20px; left: 50%; transform: translateX(-50%); color: #ef4444; font-size: 0.75rem; font-weight: 600;">{puts}</span>' if puts > 0 else ''}
                        </div>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 500;">${strike:.0f}</div>
                </div>
                """)

            html_parts.append("""
                </div>
                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #1e293b; color: #64748b; font-size: 0.85rem; text-align: center;">
                    Strike Price Distribution: Calls (Green) vs Puts (Red)
                </div>
            </div>
            """)

            return ui.HTML("".join(html_parts))

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return ui.div(
                ui.div(f"Chart Error: {str(e)}", style="color: #ef4444; font-weight: 600; margin-bottom: 10px;"),
                ui.div(error_details,
                       style="color: #94a3b8; font-size: 0.8rem; font-family: monospace; white-space: pre-wrap;"),
                style="text-align: left; padding: 20px; background: #1e293b; border-radius: 6px;"
            )

    @render.ui
    @reactive.event(input.fetch_chain)
    def interpretation_guide():
        return ui.HTML("""
        <div style="color: #94a3b8; font-size: 0.85rem; line-height: 1.6;">
            <div style="margin-bottom: 16px;">
                <div style="color: #e2e8f0; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                    <span style="color: #3b82f6;">●</span> Bar Height
                </div>
                <div style="color: #94a3b8; padding-left: 20px;">
                    Taller bars = Higher liquidity. Trade these strikes for tighter bid-ask spreads.
                </div>
            </div>

            <div style="margin-bottom: 16px;">
                <div style="color: #e2e8f0; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                    <span style="color: #10b981;">●</span> Green vs Red
                </div>
                <div style="color: #94a3b8; padding-left: 20px;">
                    More green (calls) = Bullish sentiment<br>
                    More red (puts) = Bearish sentiment<br>
                    Balanced = Neutral market
                </div>
            </div>

            <div style="margin-bottom: 16px;">
                <div style="color: #e2e8f0; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                    <span style="color: #f59e0b;">●</span> Clustering
                </div>
                <div style="color: #94a3b8; padding-left: 20px;">
                    Heavy activity at certain strikes indicates key support/resistance levels.
                </div>
            </div>

            <div style="background: #1e293b; padding: 12px; border-radius: 6px; border-left: 3px solid #3b82f6;">
                <div style="color: #3b82f6; font-weight: 600; font-size: 0.75rem; margin-bottom: 6px;">ARBITRAGE TIP</div>
                <div style="color: #94a3b8; font-size: 0.8rem;">
                    Look for strikes where call-put pricing violates put-call parity for potential arbitrage opportunities.
                </div>
            </div>
        </div>
        """)

    @render.ui
    def strategy_analysis():
        df = option_data.get()
        spot = spot_price_data.get()

        if df is None or len(df) == 0 or spot is None:
            return ui.div("Click 'SCAN OPTIONS' to generate analysis",
                          style="color: #64748b; text-align: center; padding: 40px;")

        try:
            ric = input.underlying_ric()
            spot_price = spot

            # Calculate metrics
            strike_counts = df.groupby(['StrikePrice', 'CallPutOption']).size().unstack(fill_value=0)
            total_calls = strike_counts.get('Call', pd.Series([0])).sum()
            total_puts = strike_counts.get('Put', pd.Series([0])).sum()
            put_call_ratio = total_puts / total_calls if total_calls > 0 else 0

            # Find most active strike
            total_by_strike = strike_counts.sum(axis=1)
            most_active_strike = total_by_strike.idxmax()

            # Determine market sentiment
            if put_call_ratio > 1.2:
                sentiment = "BEARISH"
                sentiment_color = "#ef4444"
                sentiment_desc = "High put volume suggests defensive positioning"
            elif put_call_ratio < 0.8:
                sentiment = "BULLISH"
                sentiment_color = "#10b981"
                sentiment_desc = "High call volume indicates bullish expectations"
            else:
                sentiment = "NEUTRAL"
                sentiment_color = "#64748b"
                sentiment_desc = "Balanced call/put activity shows uncertainty"

            # Generate stock-specific strategies
            stock_name = ric.split('.')[0]

            # Calculate ATM, ITM, OTM strikes
            atm_strike = round(spot_price / 5) * 5  # Round to nearest $5
            itm_call_strike = atm_strike - 20
            otm_call_strike = atm_strike + 20
            itm_put_strike = atm_strike + 20
            otm_put_strike = atm_strike - 20

            return ui.HTML(f"""
            <div style="color: #94a3b8;">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 24px;">
                    <div style="background: #1e293b; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="color: #64748b; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px;">PUT/CALL RATIO</div>
                        <div style="color: {sentiment_color}; font-size: 1.8rem; font-weight: 700;">{put_call_ratio:.2f}</div>
                        <div style="color: #64748b; font-size: 0.75rem; margin-top: 4px;">{total_puts} puts / {total_calls} calls</div>
                    </div>

                    <div style="background: #1e293b; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="color: #64748b; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px;">MARKET SENTIMENT</div>
                        <div style="color: {sentiment_color}; font-size: 1.5rem; font-weight: 700; margin-bottom: 4px;">{sentiment}</div>
                        <div style="color: #64748b; font-size: 0.75rem;">{sentiment_desc}</div>
                    </div>

                    <div style="background: #1e293b; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="color: #64748b; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px;">HOTTEST STRIKE</div>
                        <div style="color: #3b82f6; font-size: 1.8rem; font-weight: 700;">${most_active_strike:.0f}</div>
                        <div style="color: #64748b; font-size: 0.75rem; margin-top: 4px;">Most liquid contracts</div>
                    </div>
                </div>

                <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 24px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                        <div style="width: 4px; height: 24px; background: #3b82f6; border-radius: 2px;"></div>
                        <h5 style="color: #e2e8f0; margin: 0; font-size: 1.1rem; font-weight: 600;">Strategy Recommendations for {stock_name}</h5>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 20px;">
                        Current Price: <span style="color: #3b82f6; font-weight: 600;">${spot_price:.2f}</span> | 
                        ATM Strike: <span style="color: #e2e8f0; font-weight: 600;">${atm_strike:.0f}</span>
                    </div>

                    <div style="display: grid; gap: 16px;">
                        <div style="background: rgba(16, 185, 129, 0.1); border-left: 3px solid #10b981; padding: 16px; border-radius: 6px;">
                            <div style="color: #10b981; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 1.2rem;">📈</span> BULLISH PLAY
                            </div>
                            <div style="color: #e2e8f0; font-size: 0.9rem; margin-bottom: 8px; font-weight: 500;">
                                Long Call @ ${otm_call_strike:.0f} strike
                            </div>
                            <div style="color: #94a3b8; font-size: 0.85rem; line-height: 1.5;">
                                <strong>Setup:</strong> Buy OTM calls if you expect {stock_name} to rally above ${otm_call_strike:.0f}.<br>
                                <strong>Risk:</strong> Limited to premium paid. <strong>Reward:</strong> Unlimited upside.<br>
                                <strong>Best for:</strong> High conviction bullish bets with defined risk.
                            </div>
                        </div>

                        <div style="background: rgba(239, 68, 68, 0.1); border-left: 3px solid #ef4444; padding: 16px; border-radius: 6px;">
                            <div style="color: #ef4444; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 1.2rem;">📉</span> BEARISH PLAY
                            </div>
                            <div style="color: #e2e8f0; font-size: 0.9rem; margin-bottom: 8px; font-weight: 500;">
                                Long Put @ ${atm_strike:.0f} strike
                            </div>
                            <div style="color: #94a3b8; font-size: 0.85rem; line-height: 1.5;">
                                <strong>Setup:</strong> Buy ATM puts for maximum sensitivity to price decline.<br>
                                <strong>Risk:</strong> Premium paid. <strong>Reward:</strong> Profit down to $0.<br>
                                <strong>Best for:</strong> Hedging long stock positions or directional bear bets.
                            </div>
                        </div>

                        <div style="background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3b82f6; padding: 16px; border-radius: 6px;">
                            <div style="color: #3b82f6; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 1.2rem;">⚖️</span> NEUTRAL PLAY (Volatility)
                            </div>
                            <div style="color: #e2e8f0; font-size: 0.9rem; margin-bottom: 8px; font-weight: 500;">
                                Iron Condor: Sell ${atm_strike - 10:.0f}/${atm_strike + 10:.0f}, Buy ${atm_strike - 20:.0f}/${atm_strike + 20:.0f}
                            </div>
                            <div style="color: #94a3b8; font-size: 0.85rem; line-height: 1.5;">
                                <strong>Setup:</strong> Profit from low volatility if {stock_name} stays range-bound.<br>
                                <strong>Risk:</strong> Limited to spread width. <strong>Reward:</strong> Net premium collected.<br>
                                <strong>Best for:</strong> Earning income in sideways markets with high IV.
                            </div>
                        </div>

                        <div style="background: rgba(245, 158, 11, 0.1); border-left: 3px solid #f59e0b; padding: 16px; border-radius: 6px;">
                            <div style="color: #f59e0b; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 1.2rem;">💰</span> ARBITRAGE OPPORTUNITY
                            </div>
                            <div style="color: #e2e8f0; font-size: 0.9rem; margin-bottom: 8px; font-weight: 500;">
                                Check Put-Call Parity at ${most_active_strike:.0f} strike
                            </div>
                            <div style="color: #94a3b8; font-size: 0.85rem; line-height: 1.5;">
                                <strong>Theory:</strong> Call - Put = Stock - Strike × e^(-r×T)<br>
                                <strong>Action:</strong> If calls are overpriced relative to puts (or vice versa), execute conversion/reversal arbitrage.<br>
                                <strong>Target:</strong> Look at the most liquid strike (${most_active_strike:.0f}) for best execution.
                            </div>
                        </div>
                    </div>
                </div>

                <div style="background: #1e293b; padding: 16px; border-radius: 8px; border-left: 3px solid #64748b;">
                    <div style="color: #64748b; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px;">⚠️ RISK DISCLAIMER</div>
                    <div style="color: #94a3b8; font-size: 0.8rem; line-height: 1.5;">
                        Options trading involves substantial risk. Past performance does not guarantee future results. 
                        This analysis is for educational purposes only and not financial advice. Always conduct your own research 
                        and consider consulting with a licensed financial advisor before making investment decisions.
                    </div>
                </div>
            </div>
            """)

        except Exception as e:
            return ui.div(f"Analysis error: {str(e)}", style="color: #ef4444; padding: 20px;")

    @reactive.event(input.fetch_chain)
    def strikes_and_expiries():
        ric = input.underlying_ric()
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

        option_data.set(df)

        return df


app = App(app_ui, server)
app.run()