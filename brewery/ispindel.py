import logging
import os
import json
import plotly.graph_objects as go
from plotly.offline import plot
from plotly.subplots import make_subplots
from influxdb import InfluxDBClient
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = os.path.join(BASE_DIR, "static/config/config.json")


def save_plot(charge):
    # Get charge
    logging.debug("save_plot: saving measurements of charge: %s", charge.cid)

    # Getting credentials
    with open(CONFIG_FILE) as json_file:
        data = json.load(json_file)
        for ifdb in data["influxdb"]:
            ifdb_host = ifdb["host"]
            ifdb_port = ifdb["port"]
            ifdb_user = ifdb["user"]
            ifdb_pass = ifdb["password"]
            ifdb_db = ifdb["database"]

    logging.debug("save_plot: connecting to influx db: %s", ifdb_db)
    client = InfluxDBClient(
        host=ifdb_host, port=ifdb_port, username=ifdb_user, password=ifdb_pass, ssl=True
    )
    client.switch_database(ifdb_db)

    # Build query
    query = 'SELECT * INTO "' + charge.cid + '" FROM "measurements"'
    logging.debug("save_plot: query: %s", query)
    client.query(query)
    logging.debug("save_plot: done.")

    # Cleanup
    query = 'DELETE FROM "measurements"'
    client.query(query)
    logging.debug("save_plot: cleaning up.")


def get_plot(charge):
    # Get charge
    logging.debug("get_plot: plot for charge: %s", charge.cid)

    # Getting credentials
    with open(CONFIG_FILE) as json_file:
        data = json.load(json_file)
        for ifdb in data["influxdb"]:
            ifdb_host = ifdb["host"]
            ifdb_port = ifdb["port"]
            ifdb_user = ifdb["user"]
            ifdb_pass = ifdb["password"]
            ifdb_db = ifdb["database"]

    logging.debug("get_plot: connecting to influx db: %s", ifdb_db)
    client = InfluxDBClient(
        host=ifdb_host, port=ifdb_port, username=ifdb_user, password=ifdb_pass, ssl=True
    )
    client.switch_database(ifdb_db)

    # Build query
    if charge.finished:
        query = 'SELECT "tilt","temperature", "battery" FROM ' + '"' + charge.cid + '"'
        q = client.query(query)
    else:
        q = client.query('SELECT "tilt","temperature", "battery" FROM "measurements"')

    logging.debug("get_plot: querying data from db")
    # logging.debug("get_plot: result: %s", q)
    # ['time', 'RSSI', 'battery', 'gravity', 'interval',
    #  'source', 'temp_units', 'temperature', 'tilt']
    time = []
    tilt = []
    temperature = []
    battery = []
    points = q.get_points()
    for item in points:
        time.append(item["time"])
        print("Time: {}".format(item["time"]))
        # Polynomial: 0.000166916x^3 + -0.01470147x^2 + 0.679876283x + -10.536229152
        x = item["tilt"]
        plato = 0.000166916 * pow(x, 3)
        plato = plato - (0.01470147 * pow(x, 2))
        plato = plato + (0.679876283 * x)
        plato = plato - 10.536229152
        tilt.append(plato)

        temperature.append(item["temperature"])
        battery.append(item["battery"])

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.update_layout(
        height=550,
        xaxis_title="Zeit",
        yaxis=dict(
            title_text="Vergärungsgrad [°Plato]",
            tickmode="array",
        ),
        yaxis2=dict(
            title="Temperatur [°C]", overlaying="y", side="right", range=[2, 30]
        ),
        font=dict(family="Courier New, monospace", size=14, color="RebeccaPurple"),
        legend=dict(yanchor="top", xanchor="right", y=0.95, x=0.9),
        hovermode="x",
    )
    fig.update_yaxes(automargin=True)
    fig.update_xaxes(showline=True, linewidth=2, linecolor="black")
    fig.update_yaxes(showline=True, linewidth=2, linecolor="black")

    fig.add_trace(
        go.Scatter(
            x=time[1:], y=tilt[1:], line_shape="spline", mode="lines", name="Plato"
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=time[1:],
            y=temperature[1:],
            line_shape="spline",
            mode="lines",
            name="Temperatur",
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=time[1:],
            y=battery[1:],
            line_shape="spline",
            mode="lines",
            name="Batterie",
            visible="legendonly",
        )
    )

    plt_div = plot(fig, output_type="div")
    client.close()

    logging.debug("get_plot: process finished")
    fig.write_image("/tmp/ispindelfig.png", format="PNG")

    return plt_div
