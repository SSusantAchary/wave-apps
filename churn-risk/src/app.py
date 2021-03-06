from test.e2e import walkthrough

import pandas as pd
from h2o_wave import app, main, Q, ui
from plotly import graph_objects as go

from .churn_predictor import ChurnPredictor
from .config import Configuration
from .plots import (
    convert_plot_to_html,
    generate_figure_pie_of_target_percent,
    get_image_from_matplotlib,
    tall_stat_card_dollars,
    wide_stat_card_dollars,
)
from .utils import python_code_content

config = Configuration()
churn_predictor = ChurnPredictor()


df = pd.read_csv(config.testing_data_url).head(40)
df.fillna(config.def_column_values, inplace=True)
df.dropna(subset=config.mandatory_columns, inplace=True)
phone_choices = [ui.choice(name=phone, label=str(phone)) for phone in df[config.id_column]]


def show_profile(q: Q):
    del q.page["content"]
    q.page['search'] = ui.form_card(box=config.boxes['search'], items=[
        ui.text_xl("Customer Profiles from Model Predictions"),
        ui.picker(
            name="customers",
            label="Customer Phone Number",
            choices=phone_choices,
            max_choices=1,
            values=q.args.customers,
            trigger=True
       )
    ])
    if not q.args.customers:
      q.page["empty_profile_page"] = ui.form_card(box=config.boxes["empty_profile_page"], items=[
        ui.text_xl("To see the analysis results, you need to choose a phone number first.")
      ])
    else: 
        del q.page["empty_profile_page"]
        df = pd.read_csv(config.testing_data_url)
        cust_phone_no = q.args.customers[0]
        q.client.selected_customer_index = int(df[df[config.id_column] == cust_phone_no].index[0])
        populate_churn_plots(q)
        populate_customer_churn_stats(cust_phone_no,df,q)


def populate_churn_plots(q):
    shap_plot = churn_predictor.get_shap_explanation(q.client.selected_customer_index)
    q.page["shap_plot"] = ui.image_card(
        box=config.boxes["shap_plot"],
        title="",
        type="png",
        image=get_image_from_matplotlib(shap_plot),
    )

    top_negative_pd_plot = churn_predictor.get_top_negative_pd_explanation(q.client.selected_customer_index)
    q.page["top_negative_pd_plot"] = ui.image_card(
        box=config.boxes["top_negative_pd_plot"],
        title="Feature Most Contributing to Retention",
        type="png",
        image=get_image_from_matplotlib(top_negative_pd_plot),
    )

    top_positive_pd_plot = churn_predictor.get_top_positive_pd_explanation(q.client.selected_customer_index)
    q.page["top_positive_pd_plot"] = ui.image_card(
        box=config.boxes["top_positive_pd_plot"],
        title="Feature Most Contributing to Churn",
        type="png",
        image=get_image_from_matplotlib(top_positive_pd_plot),
    )


def populate_customer_churn_stats(cust_phone_no, df, q):
    df["Total Charges"] = (df.Total_Day_charge + df.Total_Eve_Charge + df.Total_Night_Charge + df.Total_Intl_Charge)

    df = df[
        [
            "Total_Day_charge",
            "Total_Eve_Charge",
            "Total_Night_Charge",
            "Total_Intl_Charge",
            config.id_column,
            "Total Charges",
        ]
    ]

    df.columns = ["Day Charges", "Evening Charges", "Night Charges", "Int'l Charges", config.id_column, "Total Charges"]

    q.page["day_stat"] = wide_stat_card_dollars(
        df, cust_phone_no, "Day Charges", config.boxes["day_stat"], config.color
    )
    q.page["eve_stat"] = wide_stat_card_dollars(
        df, cust_phone_no, "Evening Charges", config.boxes["eve_stat"], config.color
    )
    q.page["night_stat"] = wide_stat_card_dollars(
        df, cust_phone_no, "Night Charges", config.boxes["night_stat"], config.color
    )
    q.page["intl_stat"] = wide_stat_card_dollars(
        df, cust_phone_no, "Int'l Charges", config.boxes["intl_stat"], config.color
    )
    q.page["total_stat"] = tall_stat_card_dollars(
        df,
        cust_phone_no,
        "Total Charges",
        config.boxes["total_stat"],
        config.total_gauge_color,
    )
    q.page["customer"] = ui.small_stat_card(box=config.boxes["customer"], title="Customer", value=str(cust_phone_no))

    q.page["churn_rate"] = ui.small_stat_card(
        box=config.boxes["churn_rate"],
        title="Churn Rate",
        value=f"{churn_predictor.get_churn_rate_of_customer(q.client.selected_customer_index)}%",
    )

    labels = ["Day Charges", "Evening Charges", "Night Charges", "Int'l Charges"]
    values = [
        df[df[config.id_column] == cust_phone_no][labels[0]].values[0],
        df[df[config.id_column] == cust_phone_no][labels[1]].values[0],
        df[df[config.id_column] == cust_phone_no][labels[2]].values[0],
        df[df[config.id_column] == cust_phone_no][labels[3]].values[0],
    ]

    html_plot = generate_figure_pie_of_target_percent( "", labels, values, get_figure_layout())

    q.page["stat_pie"] = ui.frame_card(
        box=config.boxes["stat_pie"],
        title="Total call charges breakdown",
        content=convert_plot_to_html(config.figure_config, html_plot, "cdn", False),
    )


def get_figure_layout():
    return go.Layout(margin=go.layout.Margin(l=0, r=0, b=0, t=0, pad=0, autoexpand=True))


async def initialize(q: Q):
    # Initialize H2O-3 model and tests data set
    churn_predictor.build_model(config.training_data_url, config.default_model)
    churn_predictor.set_testing_data_frame(config.testing_data_url)
    churn_predictor.predict()

    q.app.header_png = await q.site.upload([config.image_path])
    q.app.training_file_url = await q.site.upload([config.working_data])
    q.page["title"] = ui.header_card(
        box=config.boxes["banner"],
        title=config.title,
        subtitle=config.subtitle,
        icon=config.icon,
        icon_color=config.color,
    )

    q.page["nav_bar"] = ui.tab_card(
        box=config.boxes["navbar"],
        value=f'#{q.args["#"]}',
        items=[
            ui.tab(name="#profile", label="Customer Profiles"),
            ui.tab(name="#tour", label="Application Code"),
        ],
    )
    q.page['meta'] = ui.meta_card(box='', title='Telcom Churn Analytics')
    q.client.app_initialized = True


@app("/")
async def serve(q: Q):
    if not q.client.app_initialized:
        await initialize(q)

    if q.args['#'] == 'tour':
        q.page["content"] = ui.form_card(box=config.boxes["content"], items=python_code_content("app.py"))
    else:
        show_profile(q)

    await q.page.save()
