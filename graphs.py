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

PLOT_COLORS = {
    'Mixed': 'grey',
    'Wood': 'brown',
    'Glass': 'yellow',
    'Metal': 'orange',
    'Plastic': 'red',
}

def treemap_graph(annual_data, color_scale=None):

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


class GraphMaker:
    """
    Class for making graphs and saving them
    """
    def __init__(self,
                 data_dir,
                 sos_data,
                 col_config,
                 ext='.png'):

        self.sos_blue = '#00b5e2'
        self.data_dir=data_dir
        self.sos_data = sos_data
        self.sos23 = sos_data[sos_data['Date'].dt.year == 2023]
        self.col_config = col_config
        self.nonitem_cols = list(col_config.loc[col_config['material'].isnull()]['name'])
        self.item_cols = list(col_config.loc[col_config['material'].notnull()]['name'])
        self.ext = ext
        # Creates subdirectory for graphs
        self.image_dir = os.path.join(data_dir, "Graphs")
        os.makedirs(self.image_dir, exist_ok=True)
        # Group by year
        self.annual_data = cleanup.group_by_year(sos_data, col_config)
        self.sos_sites = None
        self.sos_cigs = None

    def write_fig(self, fig, fig_name):
        file_path = os.path.join(self.image_dir, fig_name + self.ext)
        fig.write_image(file_path)

    def circle_packing_graph(self,
                             min_items=None,
                             plot_colors=None,
                             opacity=.5,
                             year=None,
                             fig_name=None):
        """
        Plot circle packing graph of cleanup items using the circlify package.
        Item type and number of items will be displayed on graph if there are at least
        min_items. All item types and corresponding numbers will appear as hover data.
        Circles will be color coded based on their material.

        :param int/None min_items: Minimum nbr of items to show text inside circle without hovering
            If none: use percentages of largest number.
        :param None/str plot_colors: Dict with colors corresponding to material or plotly colorscale name
        :param float opacity: Opacity of colors
        :param int year: Year for which to plot graph
        :param str/None fig_name: If not None, save graph with this name
        :return go.Figure fig: Plotly circle packing figure
        """
        if plot_colors is not None:
            assert isinstance(plot_colors, str), \
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

        if year is None:
            # Default is all years
            col_sum = self.sos_data.copy()
            fig_title = "Total Number of Items Collected By Category and Material 2013-2023"
        elif year == 2023:
            col_sum = self.sos23.copy()
            fig_title = "Total Number of Items Collected By Category and Material in 2023"
        else:
            assert 2013 <= year <= 2023, "Year must be within 2013-2023"
            col_sum = self.sos_data[sos_data['Date'].dt.year == year]
            fig_title = "Total Number of Items Collected By Category and Material in {}".format(year)

        # Compute total of columns
        col_sum.drop(self.nonitem_cols, axis=1, inplace=True)
        col_sum = col_sum.sum(axis=0, numeric_only=True)
        # Sort values, circlify wants values sorted in descending order
        col_sum = col_sum.sort_values(ascending=False)
        # Remove zeros
        col_sum = col_sum[col_sum > 0]
        # Set a min item if none
        if min_items is None:
            min_items = int(col_sum.iloc[0] / 100)
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
            material = self.col_config.loc[self.col_config['name'] == item, 'material'].iloc[0]
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
            title=fig_title,
        )
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig

    def annual_total_bar(self, item_nbr=None, fig_name=None):
        """
        Bar plot of total number of items collected over all years. Either all item categories
        or top item_nbr.

        :param int item_nbr: Plot only top item_nbr trash categories
        :param str fig_name: If not None, save fig with given name
        :return px.fig fig: Bar plot of total trash items
        """
        annual_items = self.annual_data[self.annual_data.columns.intersection(self.item_cols)]
        fig_title = "Total Number of Items Collected By Category, 2013-23"
        if item_nbr is not None:
            assert item_nbr < annual_items.shape[1], \
                'item_nbr must be smaller than total number of items'
            annual_items = annual_items.iloc[:, :item_nbr]
            fig_title = "Top {} Number of Items Collected By Category, 2013-23".format(item_nbr)

        fig = px.bar(annual_items, x=annual_items.index, y=annual_items.columns)
        fig.update_layout(
            autosize=False,
            width=1000,
            height=700,
            title=fig_title,
            yaxis_title='Total Number of Items By Category',
            xaxis_title='Year',
            legend_title='Item Category',
        )
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig

    def annual_volunteers(self, fig_name=None):
        """
        Bar graph showing total number of volunteers over the years.

        :param str fig_name: If not None, save fig with given name
        :return px.bar fig: Plotly figure bar plot
        """
        # Create bar graph for number of volunteers over the years 2013-23
        fig = px.bar(self.annual_data,
                     x=self.annual_data.index,
                     y='Total Volunteers',
                     title="Total Number of Volunteers By Year")
        fig.update_layout(
            autosize=False,
            width=850,
            height=400,
            yaxis_title='Number of Volunteers',
            xaxis_title='Year',
        )
        fig.update_traces(marker_color=self.sos_blue)
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig

    def item_per_volunteer(self, fig_name=None):
        """
        Line graph of number of trash items collected per volunteer over the years.

        :param str fig_name: If not None, save fig with given name
        :return px.line fig: Plotly line figure
        """
        annual_volunteer = self.annual_data.copy()
        # Normalize by total volunteers
        annual_volunteer[self.item_cols] = annual_volunteer[self.item_cols].div(annual_volunteer['Total Volunteers'], axis=0)
        # Make sure that items numbers are sorted in descending order
        annual_volunteer = annual_volunteer[annual_volunteer.columns.intersection(self.item_cols)]
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
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig

    def make_sos_sites(self):
        """
        Helper function create a dataframe grouped by cleanup site
        """
        sos_sites = self.sos_data.copy()
        sos_sites['Cleanup Site'].replace([0, 1], np.NaN, inplace=True)
        sos_sites.dropna(subset=['Cleanup Site', 'Date'], inplace=True)
        nonnumeric_cols = list(
            self.col_config.loc[~self.col_config['type'].isin(['int', 'float'])]['name'],
        )
        nonnumeric_cols.remove('Cleanup Site')
        sos_sites.drop(nonnumeric_cols, axis=1, inplace=True)
        sos_sites = sos_sites.groupby('Cleanup Site').sum()
        self.sos_sites = sos_sites.reset_index()

    def volunteers_by_site(self, fig_name=None):
        """
        Bar graph of top 25 sites where the most volunteers participated in cleanups.

        :param str fig_name: If not None, save fig with given name
        :return go.Figure fig: Plotly bar graph
        """
        if self.sos_sites is None:
            self.make_sos_sites()
        sos_volunteers = self.sos_sites.copy()
        sos_volunteers.sort_values('Total Volunteers', ascending=False, inplace=True)
        sos_volunteers = sos_volunteers.head(25)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=sos_volunteers['Cleanup Site'],
            x=sos_volunteers['Adult Volunteers'],
            orientation='h',
            name='Total Cleanup Volunteers',
            marker=dict(color=self.sos_blue),
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
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig

    def items_by_site(self, fig_name=None):
        """
        Bar graph of top 25 sites with the most trash items collected.

        :param str fig_name: If not None, save fig with given name
        :return go.Figure fig: Plotly bar graph
        """
        if self.sos_sites is None:
            self.make_sos_sites()
        sos_sites = self.sos_sites
        sos_sites.sort_values('Total Items', ascending=False, inplace=True)
        sos_sites = sos_sites.head(25)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=sos_sites['Cleanup Site'],
            x=sos_sites['Total Items'],
            orientation='h',
            name='Total Number of Items Cleaned Up',
            marker=dict(color=self.sos_blue),
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
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig

    def make_sos_cigs(self, cig_df):
        """
        Helper function to create dataframe with cigarette butt data
        """
        self.sos_cigs = cig_df[['Cleanup Site', 'County/City', 'Cigarette Butts']]
        self.sos_cigs = self.sos_cigs.groupby('Cleanup Site').sum()
        self.sos_cigs = self.sos_cigs.reset_index()
        self.sos_cigs.sort_values(by=['Cigarette Butts'], ascending=False, inplace=True)
        # Load file containing coordinates for site names and join it with the cigarette butt data
        coords = pd.read_csv(os.path.join(self.data_dir, 'cleanup_site_coordinates.csv'))
        self.sos_cigs = pd.merge(self.sos_cigs, coords, how='left', on="Cleanup Site")

    def cigarette_map(self,
                      year=None,
                      map_bounds=None,
                      w=None,
                      h=None,
                      single_color=True,
                      fig_name=None):
        """
        Plot sites where cigarettes have been cleaned up as circles on a map.
        The size of the circle corresponds to the amount of cigarette butts.

        :param int/None year: Plot cigarette butts for specific year or all years if None
        :param dict map_bounds: Min and max latitudes and longitude for map boundary
        :param int/None w: Graph width
        :param int/None h: Graph height
        :param bool single_color: Plots either single color or colorscale
        :param str fig_name: If not None, save fig with given name
        :return plotly.graph_objs fig: Map with circles corresponding to cigarette butts
        """
        if year is None:
            # Default is all years
            cig_df = self.sos_data.copy()
        elif year == 2023:
            cig_df = self.sos23.copy()
        else:
            assert 2013 <= year <= 2023, "Year must be within 2013-2023"
            cig.df = self.sos_data[sos_data['Date'].dt.year == year]

        self.make_sos_cigs(cig_df)

        if map_bounds is None:
            map_bounds = {
                "west": self.sos_cigs['Longitude'].min() - .1,
                "east": self.sos_cigs['Longitude'].max() + .1,
                "south": self.sos_cigs['Latitude'].min() - .01,
                "north": self.sos_cigs['Latitude'].max() + .01,
            }
        if w is None:
            w = 1000
        if h is None:
            h = 1000
        if single_color:
            fig = px.scatter_mapbox(
                data_frame=self.sos_cigs,
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
                data_frame=self.sos_cigs,
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
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig

    def activity_graph(self, fig_name=None):
        """
        Bar graph where trash items are sorted by activity. Activities are defined in the
        NOAA marine debris report as:
        Eating and drinking, Smoking, Personal Hygiene, Recreation,Dumping and disaster,
        Fishing and Various (Various are items that could not be determined to be related
        to one of the first six categories).

        :param str fig_name: If not None, save fig with given name
        :return go.Figure fig: Plotly bar figure
        """
        col_sum = self.sos_data.copy()
        # Sum total items
        col_sum.drop(self.nonitem_cols, axis=1, inplace=True)
        col_sum = col_sum.sum(axis=0, numeric_only=True)
        col_sum = col_sum.sort_values(ascending=False)
        # Add activity to dataframe
        col_sum = col_sum.to_frame(name='count')
        col_sum.insert(0, 'name', col_sum.index)
        col_sum.reset_index(drop=True, inplace=True)
        col_sum = pd.merge(col_sum, self.col_config, how='left', on="name")
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
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig

    def smoking_line_graph(self, fig_name=None):
        """
        Line graph showing smoking related trash items over the years.

        :param str fig_name: If not None, save fig with given name
        :return go.Figure fig: Plotly line figure
        """
        annual_smoking = self.annual_data[['Cigarette Butts', 'Cigar Tips', 'E-Waste', 'Tobacco', 'Lighters']].copy()
        annual_smoking = annual_smoking.div(self.annual_data['Total Volunteers'], axis=0)
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
        if fig_name is not None:
            self.write_fig(fig, fig_name)
        return fig


def make_and_save_graphs(sos_data, col_config, data_dir, ext='.png'):
    """
    Manipulate the data frame to extract features, plot graphs, and write
    them to an output directory, which is a subdirectory of the input data directory
    named 'Graphs'.

    :param pd.DataFrame sos_data: SOS data collected over the years.
    :param pd.DataFrame col_config: Column information
    :param str data_dir: Data directory
    :param str ext: Graph file extention (default: '.png')
    """
    graph_maker = GraphMaker(data_dir, sos_data, col_config, ext)
    # Get data from 2023 and make circle packing graph
    graph_maker.circle_packing_graph(
        plot_colors=None,
        fig_name="Circle_packing_items_materials_2013-23",
    )
    # All items over the years
    graph_maker.annual_total_bar(fig_name="Bar_graph_all_items_2013-23")
    # Top 5 items over the years
    graph_maker.annual_total_bar(item_nbr=5, fig_name="Bar_graph_top_5_items_2013-23")
    # Annual volunteers
    graph_maker.annual_volunteers(fig_name="Bar_graph_number_volunteers_2013-23")
    # Number of item per volunteer line graph 2013-23
    graph_maker.item_per_volunteer(
        fig_name="Line_graph_number_items_per_volunteers_2013-23",
    )
    # Number of volunteers by site 2013-23
    graph_maker.volunteers_by_site(fig_name="Bar_graph_top25_sites_by_volunteers_2013-23")
    # Select top 25 sites with most items cleaned up
    graph_maker.items_by_site(fig_name="Bar_graph_top25_sites_by_items_2013-23")
    # Map of cigarette butt locations by number 2023
    graph_maker.cigarette_map(
        single_color=False,
        fig_name="Map_cigarette_butts_by_location_2013-23",
    )
    # Santa Cruz only
    map_bounds = {
        "west": -122.35,
        "east": -121.59,
        "south": 36.92,
        "north": 37}
    graph_maker.cigarette_map(
        map_bounds=map_bounds,
        h=600,
        single_color=False,
        fig_name="Map_cigarette_butts_Santa_Cruz_2013-23",
    )
    # Debris caused by smoking 2013-23
    graph_maker.smoking_line_graph(fig_name="Line_graph_smoking_per_volunteers_2013-23")
    # Debris by activity
    graph_maker.activity_graph(fig_name="Debris_by_activity_2013-23")


if __name__ == '__main__':
    args = cleanup.parse_args()
    sos_data, col_config = cleanup.read_data(args.dir)
    make_and_save_graphs(sos_data, col_config, args.dir)
