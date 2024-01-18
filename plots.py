import circlify
import numpy as np
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go

import cleanup as cleanup


def geo_lut():
    data = [
        {'Cleanup Site': 'Cowell/Main Beach', 'Lat': 36.96314713351904, 'Lon': -122.02243758278826},
        {'Cleanup Site': 'Del Monte Beach', 'Lat': 36.60567463011781, 'Lon': -121.86921753856507},
        {'Cleanup Site': 'Sunny Cove Beach', 'Lat': 36.9608131481512, 'Lon': -121.98939936638436},
        {'Cleanup Site': 'SLR @ Felker', 'Lat': 36.98459460220125, 'Lon': -122.0270405610404},
        {'Cleanup Site': 'Capitola', 'Lat': 36.9717416923847, 'Lon': -121.94958914242098},
        {'Cleanup Site': 'SLR @ Soquel', 'Lat': 36.9734528505215, 'Lon': -122.0226709635966},
        {'Cleanup Site': 'Lompico Creek', 'Lat': 37.1114960947694, 'Lon': -122.04525603510727},
        {'Cleanup Site': 'Seabright State Beach', 'Lat': 36.963194113357105, 'Lon': -122.00719361268948},
        {'Cleanup Site': 'Corcoran Lagoon', 'Lat': 36.959697974689185, 'Lon': -121.98498873132264},
        {'Cleanup Site': 'Twin Lakes State Beach', 'Lat': 36.962252960276544, 'Lon': -121.99777127397948},
    ]
    lut = pd.DataFrame(data)
    return lut


def circle_packing_graph(df, min_items=None, color_scale=None):
    """
    Plot circle packing graph of cleanup items using the circlify package.
    Item type and number of items will be displayed on graph if there are at least
    min_items. All item types and corresponding numbers will appear as hover data.

    :param pd.DataFrame df: Cleaned SOS data
    :param int/None min_items: Minimum nbr of items to show text inside circle without hovering
        If none: use percentages of largest number.
    :param str/None color_scale: Plotly colorscale, see https://plotly.com/python/builtin-colorscales/
    :return go.Figure fig: Plotly circle packing figure
    """
    if color_scale is None:
        color_scale = 'BuPu'

    df_circ = df.copy()
    # Compute total of columns
    col_sum = cleanup.sum_items(df_circ)
    # Sort values, circlify wants values sorted in descending order
    col_sum = col_sum.sort_values(ascending=False)
    # Remove zeros
    col_sum = col_sum[col_sum > 0]
    # Set a min item if none
    if min_items is None:
        min_items = int(col_sum.iloc[0]/100)
    # Create a circle packing graph
    # compute circle positions:
    circles = circlify.circlify(
        col_sum.tolist(),
        show_enclosure=False,
        target_enclosure=circlify.Circle(x=0, y=0, r=1)
    )
    # Circlify wants input sorted in descending order, output is ascending??
    circles.reverse()
    # Create figure
    fig = go.Figure()
    fig.data = []
    # Set axes properties
    fig.update_xaxes(
        range=[-1.05, 1.05],  # making slightly wider axes than -1 to 1 so no edge of circles cut-off
        showticklabels=False,
        showgrid=False,
        zeroline=False
    )
    fig.update_yaxes(
        range=[-1.05, 1.05],
        showticklabels=False,
        showgrid=False,
        zeroline=False,
    )
    # Get some different colors
    plot_colors = plotly.colors.sample_colorscale(color_scale, samplepoints=10, low=0, high=1.0, colortype='rgb')

    # add circles
    for idx, circle in enumerate(circles):
        x, y, r = circle
        plot_color = plot_colors[int(round(r * 10))]
        fig.add_shape(type="circle",
                      xref="x",
                      yref="y",
                      x0=x - r, y0=y - r, x1=x + r, y1=y + r,
                      fillcolor=plot_color,
                      line_width=2,
                      )
        nbr_items = int(col_sum.iloc[idx])
        txt = "{} <br> {}".format(col_sum.index[idx], str(nbr_items))
        # Text gets messy if circle is too small
        if nbr_items > 7 * min_items or \
                (nbr_items > min_items and len(txt) < 30):
            fig.add_annotation(
                x=x,
                y=y,
                text=txt,
                hovertext=txt,
                showarrow=False,
                font_size=10,
            )
        else:
            fig.add_annotation(
                x=x,
                y=y,
                text='',
                hovertext=txt,
                showarrow=False,
                font_size=10,
            )
    fig.update_layout(
        autosize=False,
        width=1100,
        height=1100,
    )
    return fig


def treemap_graph(df, color_scale=None):

    if color_scale is None:
        color_scale = 'BuPu'

    df_circ = df.copy()
    # Compute total of columns
    col_sum = cleanup.sum_items(df_circ)

    df_sum = pd.DataFrame({'Item': col_sum.index, 'Quantity': col_sum.values})

    fig = px.treemap(df_sum, path=[px.Constant('Cleanup Numbers'), 'Item'],
                     values='Quantity',
                     names='Item',
                     color='Quantity',
                     color_continuous_scale=color_scale,
                     )
    fig.update_layout(
        autosize=False,
        width=1100,
        height=800,
    )
    return fig


def map_graph(df):
    fig = px.scatter_mapbox(
        data_frame=df,
        lat='Lat',
        lon='Lon',
        size='Cigarette Butts',
        hover_name='Cleanup Site',
        hover_data=['Cleanup Site', 'Cigarette Butts'],
        color_discrete_sequence=['fuchsia'],
        zoom=9,
        center={'lat': 36.5, 'lon': -122},
        height=1500,
        width=500,
    )
    fig.update_layout(mapbox_style="carto-positron")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    fig.update_layout(mapbox_bounds={"west": -124, "east": -120, "south": 35, "north": 38})
    fig.update_layout(autosize=False, width=1000, height=800)
    return fig
