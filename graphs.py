import circlify
import glob
import numpy as np
import os
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go

import cleanup as cleanup

SOS_BLUE = '#00b5e2'

# PLOT_COLORS = {
#     'Mixed': 'grey',
#     'Wood': 'teal',
#     'Glass': SOS_BLUE,
#     'Metal': 'lightgreen',
#     'Plastic': 'blue',
# }

PLOT_COLORS = {
    'Mixed': 'grey',
    'Wood': 'brown',
    'Glass': 'yellow',
    'Metal': 'orange',
    'Plastic': 'red',
}


def circle_packing_graph(df, col_config, min_items=None, plot_colors=None, opacity=.5):
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
                      opacity=opacity,
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
                marker=dict(size=20,
                            color=plot_colors[material],
                            symbol='circle',
                            opacity=opacity),
            )
        )
    fig.update_traces(showlegend=True)
    fig.update_layout(
        autosize=False,
        width=1000,
        height=1000,
        # paper_bgcolor="rgba(0,0,0,0)",
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


def map_graph(df, map_bounds=None, w=None, h=None, single_color=True):
    """
    Plot sites where cigarettes have been cleaned up as circles on a map.
    The size of the circle corresponds to the amount of cigarette butts.

    :param pd.DataFrame df: Dataframe containing Cleanup Site, Cigarette Buttts, and
        Latitude, Longitude
    :param dict map_bounds: Min and max latitudes and longitude for map boundary
    :param int/None w: Graph width
    :param int/None h: Graph height
    :param bool single_color: Plots either single color or colorscale
    :return plotly.graph_objs fig: Map with circles corresponding to cigarette butts
    """
    if map_bounds is None:
        map_bounds = {
            "west": df['Longitude'].min() - .1,
            "east": df['Longitude'].max() + .1,
            "south": df['Latitude'].min() - .01,
            "north": df['Latitude'].max() + .01,
        }
    if w is None:
        w = 1000
    if h is None:
        h = 1000
    if single_color:
        fig = px.scatter_mapbox(
            data_frame=df,
            lat='Latitude',
            lon='Longitude',
            size='Cigarette Butts',
            hover_name='Cleanup Site',
            hover_data=['Cleanup Site', 'Cigarette Butts'],
            color_discrete_sequence=['fuchsia'],
            zoom=8,
        )
    else:
        fig = px.scatter_mapbox(
            data_frame=df,
            lat='Latitude',
            lon='Longitude',
            size='Cigarette Butts',
            hover_name='Cleanup Site',
            hover_data=['Cleanup Site', 'Cigarette Butts'],
            color='Cigarette Butts',
            color_continuous_scale='Sunsetdark',
            zoom=8,
        )

    fig.update_layout(mapbox_style="carto-positron")
    fig.update_layout(margin={"r": 0.1, "t": 0.1, "l": 0.1, "b": 0.1})
    fig.update_layout(mapbox_bounds=map_bounds)
    fig.update_layout(autosize=False, width=w, height=h)
    return fig


def activity_graph(df, col_config):
    col_sum = df.copy()
    # Drop non-activity columns
    nonitem_cols = list(col_config.loc[col_config['activity'].isnull()]['name'])
    # Sum total items
    col_sum.drop(nonitem_cols, axis=1, inplace=True)
    col_sum = col_sum.sum(axis=0, numeric_only=True)
    col_sum = col_sum.sort_values(ascending=False)
    # Add activity to dataframe
    col_sum = col_sum.to_frame(name='count')
    col_sum.insert(0, 'name', col_sum.index)
    col_sum.reset_index(drop=True, inplace=True)
    col_sum = pd.merge(col_sum, col_config, how='left', on="name")
    # Bar plot
    fig = px.bar(col_sum, x='activity', y='count', color='name', text="name")
    fig.update_layout(
        autosize=False,
        width=1000,
        height=700,
        title="Total Number of Items Collected By Activity, 2013-23",
        yaxis_title='Total Number of Items',
        xaxis_title='Activity',
        legend_title='Item Category',
        xaxis={'categoryorder': 'total descending'},
    )
    fig.update_traces(
        textfont_size=10,
        textangle=0,
        textposition="inside",
        cliponaxis=False,
    )
    return fig


def make_and_save_graphs(sos_data, data_dir, ext='.png'):
    """
    Manipulate the data frame to extract features, plot graphs, and write
    them to an output directory, which is a subdirectory of the input data directory
    named 'Graphs'.

    :param pd.DataFrame sos_data: SOS data collected over the years.
    :param str data_dir: Data directory
    :param str ext: Graph file extention (default: '.png')
    """
    # Creates subdirectory for graphs
    image_dir = os.path.join(data_dir, "Graphs")
    os.makedirs(image_dir, exist_ok=True)
    # Read config for columns (created when running cleanup main)
    col_config = pd.read_csv(os.path.join(data_dir, 'sos_column_info.csv'))
    # find column names that do not correspond to items (material is nan)
    nonitem_cols = list(col_config.loc[col_config['material'].isnull()]['name'])

    # Get data from 2023 and make circle packing graph
    sos23 = sos_data[sos_data['Date'].dt.year == 2023]
    fig = circle_packing_graph(sos23, col_config, plot_colors=None)
    fig.write_image(os.path.join(image_dir, "Circle_packing_items_materials_2023" + ext))

    # Create bar graph for years 2013-23
    # Add Total Volunteers and Total Items to col config
    col_config.loc[len(col_config.index)] = ['Total Volunteers', ['Adult + 0.5*Youth'], 'float', False, np.NaN, np.NaN]
    col_config.loc[len(col_config.index)] = ['Total Items', ['Sum of items per event'], 'int', False, np.NaN, np.NaN]
    # ...and to dataframe
    items = sos_data.copy()
    items.drop(nonitem_cols, axis=1, inplace=True)
    sos_data['Total Items'] = items.sum(axis=1, numeric_only=True)
    sos_data['Total Volunteers'] = sos_data['Adult Volunteers'].fillna(0) + 0.5 * sos_data['Youth Volunteers'].fillna(0)
    # Group by year
    annual_data = cleanup.group_by_year(sos_data, col_config)
    # Sort items by sum in descending order so it's easier to decipher variables
    s = annual_data.sum()
    s = s.sort_values(ascending=False)
    annual_data = annual_data[s.index]
    item_cols = list(col_config.loc[col_config['material'].notnull()]['name'])
    annual_items = annual_data[annual_data.columns.intersection(item_cols)]
    annual_items = annual_items.iloc[:, :5]

    fig = px.bar(annual_items, x=annual_items.index, y=annual_items.columns)
    fig.update_layout(
        autosize=False,
        width=1000,
        height=700,
        title="Top 5 Most Common Item Categories, 2013-2023",
        yaxis_title='Number of Items By Category',
        xaxis_title='Year',
        legend_title='Item Category',
    )
    fig.write_image(os.path.join(image_dir, "Bar_graph_top_5_items_2013-23" + ext))

    # Create bar graph for number of volunteers over the years 2013-23
    fig = px.bar(annual_data, x=annual_data.index, y='Total Volunteers', title="Total Number of Volunteers By Year")
    fig.update_layout(
        autosize=False,
        width=850,
        height=400,
        yaxis_title='Total Number of Items By Category',
        xaxis_title='Year',
    )
    fig.update_traces(marker_color=SOS_BLUE)
    fig.write_image(os.path.join(image_dir, "Bar_graph_number_volunteers_2013-23" + ext))

    # Number of item per volunteer line graph 2013-23
    annual_volunteer = annual_data.copy()
    item_cols = list(col_config.loc[col_config['material'].notnull()]['name'])
    for item in list(item_cols):
        annual_volunteer[item] = annual_volunteer[item] / annual_volunteer['Total Volunteers']
    annual_volunteer = annual_volunteer[annual_volunteer.columns.intersection(item_cols)]
    fig = px.line(annual_volunteer, x=annual_volunteer.index, y=annual_volunteer.columns)
    fig.update_layout(
        autosize=False,
        width=1000,
        height=700,
        title="Number of Items Collected Per Volunteer For the Years 2013-23",
        yaxis_title='Number of Items Per Volunteer By Category',
        xaxis_title='Year',
        legend_title='Item Category',
    )
    fig.write_image(os.path.join(image_dir, "Line_graph_number_items_per_volunteers_2013-23" + ext))

    # Number of volunteers by site 2013-23
    sos_sites = sos_data.copy()
    sos_sites['Cleanup Site'].replace([0, 1], np.NaN, inplace=True)
    sos_sites.dropna(subset=['Cleanup Site', 'Date'], inplace=True)
    nonnumeric_cols = list(
        col_config.loc[~col_config['type'].isin(['int', 'float'])]['name'],
    )
    nonnumeric_cols.remove('Cleanup Site')
    sos_sites.drop(nonnumeric_cols, axis=1, inplace=True)
    sos_sites = sos_sites.groupby('Cleanup Site').sum()
    sos_sites = sos_sites.reset_index()
    sos_volunteers = sos_sites.copy()
    sos_volunteers.sort_values('Total Volunteers', ascending=False, inplace=True)
    sos_volunteers = sos_volunteers.head(25)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=sos_volunteers['Cleanup Site'],
        x=sos_volunteers['Adult Volunteers'],
        orientation='h',
        name='Total Cleanup Volunteers',
        marker=dict(color=SOS_BLUE),
    ))
    fig.update_layout(
        autosize=False,
        width=1000,
        height=800,
        title="Top 25 Cleanup Sites by Number of Volunteers 2013-23",
        yaxis_title='Cleanup site',
        xaxis_title='Total Number of Volunteers',
        yaxis={'categoryorder': 'total ascending'}
    )
    fig.write_image(os.path.join(image_dir, "Bar_graph_top25_sites_by_volunteers_2013-23" + ext))

    # Select top 25 sites with most items cleaned up
    sos_sites.sort_values('Total Items', ascending=False, inplace=True)
    sos_sites = sos_sites.head(25)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=sos_sites['Cleanup Site'],
        x=sos_sites['Total Items'],
        orientation='h',
        name='Total Number of Items Cleaned Up',
        marker=dict(color=SOS_BLUE),
    ))
    fig.update_layout(
        autosize=False,
        width=1000,
        height=800,
        title="Top 25 Cleanup Sites By Number of Items 2013-23",
        yaxis_title='Cleanup Site',
        xaxis_title='Total Number of Items',
        yaxis={'categoryorder': 'total ascending'}
    )
    fig.write_image(os.path.join(image_dir, "Bar_graph_top25_sites_by_items_2013-23" + ext))

    # Map of cigarette butt locations by number 2023
    sos23 = sos_data[sos_data['Date'].dt.year == 2023]
    sos23 = sos23[['Cleanup Site', 'County/City', 'Cigarette Butts']]
    sos23 = sos23.groupby('Cleanup Site').sum()
    sos23 = sos23.reset_index()
    sos23.sort_values(by=['Cigarette Butts'], ascending=False, inplace=True)
    # Load file containing coordinates for site names and join it with the cigarette butt data
    coords = pd.read_csv(os.path.join(data_dir, 'cleanup_site_coordinates.csv'))
    sos23 = pd.merge(sos23, coords, how='left', on="Cleanup Site")
    fig = map_graph(sos23, single_color=False)
    fig.write_image(os.path.join(image_dir, "Map_cigarette_butts_by_location_2023" + ext))
    # Santa Cruz only
    map_bounds = {
        "west": -122.35,
        "east": -121.59,
        "south": 36.92,
        "north": 37}
    fig = map_graph(sos23, map_bounds, h=600, single_color=False)
    fig.write_image(os.path.join(image_dir, "Map_cigarette_butts_Santa_Cruz_2023" + ext))

    # Debris caused by smoking 2013-23
    annual_smoking = annual_data[['Cigarette Butts', 'Cigar Tips', 'E-Waste', 'Tobacco', 'Lighters']].copy()
    for item in list(annual_smoking):
        annual_smoking[item] = annual_smoking[item] / annual_data['Total Volunteers']
    fig = px.line(annual_smoking, x=annual_smoking.index,
                  y=['Cigarette Butts', 'Cigar Tips', 'E-Waste', 'Tobacco', 'Lighters'])
    fig.update_layout(
        autosize=False,
        width=1000,
        height=600,
        yaxis_title='Number of Items Per Volunteer',
        xaxis_title='Year',
        legend_title='Item Category',
    )
    fig.write_image(os.path.join(image_dir, "Line_graph_smoking_per_volunteers_2013-23" + ext))

    # Debris by activity
    fig = activity_graph(sos_data, col_config)
    fig.write_image(os.path.join(image_dir, "Debris_by_activity_2013-23" + ext))

if __name__ == '__main__':
    args = cleanup.parse_args()
    data_dir = args.dir

    existing_file = glob.glob(os.path.join(data_dir, 'merged_sos_data.csv'))
    if len(existing_file) == 1:
        sos_data = pd.read_csv(existing_file[0])
        sos_data['Date'] = pd.to_datetime(sos_data['Date'], errors='coerce')
    else:
        sos_data = cleanup.merge_data(data_dir)
        sos_data.to_csv(os.path.join(data_dir, "merged_sos_data.csv"), index=False)

    make_and_save_graphs(sos_data, data_dir)
