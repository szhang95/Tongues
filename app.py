from shiny import App, render, ui, reactive, req
import refinitiv.data as rd
import pandas as pd
from datetime import datetime

app_ui = ui.page_fillable(
    ui.include_css("custom.css"),
    ui.include_js("custom.js"),
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
                            ),
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
                                ),
                                ui.div(
                                    {"class": "col-12"},
                                    ui.input_numeric(
                                        "top_options",
                                        "Number of Contracts in Query ("
                                        "1000 max)",
                                        value=1000
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
                                    "Last updated:",
                                    style="color: 'red'; "
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
                ),

                # 数据表格
                ui.div(
                    {
                        "class": "panel",
                        "style": "background: #0f172a; "
                                 "border: 1px solid #1e293b; "
                                 "border-radius: 8px; padding: 24px;"
                    },
                    ui.h6(
                        "OPTIONS CHAIN",
                        style="color: #64748b; font-weight: 600; "
                              "letter-spacing: 1px; "
                              "margin-bottom: 20px; "
                              "font-size: 0.75rem;"
                    ),
                    ui.output_data_frame("strikes_and_expiries")
                )
            )
        )
    )
)


def server(input, output, session):
    rd.open_session()
    session.on_ended(rd.close_session)

    option_chain = reactive.Value()
    option_data = reactive.Value()
    spot_price_data = reactive.Value()

    # Main data fetch function - only this one calls the API
    @reactive.effect
    @reactive.event(input.fetch_chain)
    def fetch_all_data():

        ric = input.underlying_ric()
        print(f"Fetching data for {ric}...")

        # Fetch spot price
        spot_df = rd.get_data(ric, ['TR.PriceClose'])
        spot = spot_df['Price Close'].iloc[0]
        spot_price_data.set(spot)

        # Fetch options chain
        min_strike = input.min_strike()
        max_strike = input.max_strike()
        min_expiry = input.min_expiry()
        max_expiry = input.max_expiry()

        filter_str = (
            "( SearchAllCategoryv2 eq 'Options' and "
            f"(ExpiryDate gt {min_expiry} and "
            f"ExpiryDate lt {max_expiry}) and "
            f"(StrikePrice ge {min_strike} and "
            f"StrikePrice le {max_strike}) and "
            "ExchangeName xeq 'OPRA' and "
            f"(UnderlyingQuoteRIC eq '{ric}'))"
        )

        df = rd.discovery.search(
            view=rd.discovery.Views.EQUITY_QUOTES,
            top=input.top_options(),
            filter=filter_str,
            select="RIC,CallPutOption,StrikePrice,ExpiryDate"
        )

        option_data.set(df)


    @render.text
    def spot_price():
        spot = spot_price_data.get()
        req(spot)
        return f"${spot:.2f}"


app = App(app_ui, server)
app.run()