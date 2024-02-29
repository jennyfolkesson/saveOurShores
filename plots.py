import circlify
import numpy as np
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go

import cleanup as cleanup

SOS_BLUE = '#00b5e2'

PLOT_COLORS = {
    'Mixed': 'grey',
    'Wood': 'teal',
    'Glass': SOS_BLUE,
    'Metal': 'lightgreen',
    'Plastic': 'blue',
}


def circle_packing_graph(df, col_config, min_items=None, plot_colors=None):
    """
    Plot circle packing graph of cleanup items using the circlify package.
    Item type and number of items will be displayed on graph if there are at least
    min_items. All item types and corresponding numbers will appear as hover data.
    Circles will be color coded based on their material.

    :param pd.DataFrame df: Cleaned SOS data
    :param pd.DataFrame col_config: Cleaned column config file
    :param int/None min_items: Minimum nbr of items to show text inside circle without hovering
        If none: use percentages of largest number.
    :param None/str plot_colors: Dict with colors corresponding to material or plotly colorscale name
    :return go.Figure fig: Plotly circle packing figure
    """
    if plot_colors is not None:
        assert isinstance(plot_colors, str),\
            "plot_colors must be string corresponding to plotly colormap"
        plot_colors = plotly.colors.sample_colorscale(
            plot_colors,
            samplepoints=5,
            low=0,
            high=1,
            colortype='rgb',
        )
        plot_colors = {
            'Mixed': plot_colors[0],
            'Wood': plot_colors[1],
            'Glass': plot_colors[2],
            'Metal': plot_colors[3],
            'Plastic': plot_colors[4],
        }
    else:
        plot_colors = PLOT_COLORS

    col_sum = df.copy()
    # Compute total of columns
    nonitem_cols = list(col_config.loc[col_config['material'].isnull()]['name'])
    col_sum.drop(nonitem_cols, axis=1, inplace=True)
    col_sum = col_sum.sum(axis=0, numeric_only=True)
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
    # add circles
    for idx, circle in enumerate(circles):
        item = col_sum.index[idx]
        material = col_config.loc[col_config['name'] == item, 'material'].iloc[0]
        x, y, r = circle
        fig.add_shape(type="circle",
                      xref="x",
                      yref="y",
                      x0=x - r, y0=y - r, x1=x + r, y1=y + r,
                      fillcolor=plot_colors[material],
                      opacity=0.5,
                      line_width=2,
                      )
        nbr_items = int(col_sum.iloc[idx])
        txt = ''
        hovertxt = "{} <br> {}".format(item, str(nbr_items))
        # Text gets messy if circle is too small
        # TODO: compare text length to radius
        if nbr_items > 7 * min_items or \
                (nbr_items > min_items and len(txt) < 30):
            txt = hovertxt
        fig.add_annotation(
            x=x,
            y=y,
            text=txt,
            hovertext=hovertxt,
            showarrow=False,
            font_size=10,
        )

    for material in plot_colors.keys():
        fig.add_traces(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name=material,
                marker=dict(size=16,
                            color=plot_colors[material],
                            symbol='circle',
                            opacity=0.5),
            )
        )
    fig.update_traces(showlegend=True)
    fig.update_layout(
        autosize=False,
        width=1000,
        height=1000,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title="Total Number of Items Collected By Category and Material in 2023",
    )
    return fig


def treemap_graph(annual_data, col_config, color_scale=None):

    if color_scale is None:
        color_scale = 'BuPu'

    # Stack columns for treemap plot
    col_stack = pd.DataFrame(annual_data.stack()).reset_index()
    col_stack.columns = ['Year', 'Item', 'Quantity']
    # Remove entries with zeros
    col_stack = col_stack[col_stack['Quantity'] > 0]
    # Plot treemap
    fig = px.treemap(
        col_stack,
        path=[px.Constant("All"), 'Year', 'Item'],
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


def map_graph(df, circ_color=SOS_BLUE):
    """
    Plot sites where cigarettes have been cleaned up as circles on a map.
    The size of the circle corresponds to the amount of cigarette butts.

    :param pd.DataFrame df: Dataframe containing Cleanup Site, Cigarette Buttts, and
        Latitude, Longitude
    :param str circ_color: Color of circles
    :return plotly.graph_objs fig: Map with circles corresponding to cigarette butts
    """
    fig = px.scatter_mapbox(
        data_frame=df,
        lat='Latitude',
        lon='Longitude',
        size='Cigarette Butts',
        hover_name='Cleanup Site',
        hover_data=['Cleanup Site', 'Cigarette Butts'],
        color_discrete_sequence=[circ_color],
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
