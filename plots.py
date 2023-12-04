import circlify
import numpy as np
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go


def _sum_items(df):
    df.drop(['Date',
                  'Data Collection',
                  'Duration (Hrs)',
                  'County/City',
                  'Cleanup Site',
                  'Cleaned Size (Sq Miles)',
                  'Adult Volunteers',
                  'Youth Volunteers',
                  'Pounds Of Trash',
                  'Pounds Of Recycling',
                  'Type Of Cleanup'], axis=1, inplace=True)

    # Compute total of columns
    col_sum = df.sum(axis=0, numeric_only=True)
    return col_sum


def circle_packing_graph(df, color_scale=None):
    """
    Plot circle packing graph of cleanup items using the circlify package

    :param pd.DataFrame df: Cleaned SOS data
    :param str/None color_scale: Plotly colorscale, see https://plotly.com/python/builtin-colorscales/
    :return go.Figure fig: Plotly circle packing figure
    """
    if color_scale is None:
        color_scale = 'BuPu'

    df_circ = df.copy()
    # Compute total of columns
    col_sum = _sum_items(df_circ)
    # Sort values, circlify wants values sorted in descending order
    col_sum = col_sum.sort_values(ascending=False)

    # Create a circle packing graph
    # compute circle positions:
    circles = circlify.circlify(
        col_sum.tolist(),
        show_enclosure=False,
        target_enclosure=circlify.Circle(x=0, y=0, r=1)
    )
    # Circlify wants input sorted in descending order, output is ascending??
    circles.reverse()

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
        # Text gets messy if circle is too small
        if nbr_items > 100:
            txt = "{} <br> {}".format(col_sum.index[idx], str(nbr_items))
            fig.add_annotation(
                x=x,
                y=y,
                text=txt,
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
    col_sum = _sum_items(df_circ)

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
