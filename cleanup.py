import argparse
from geopy import distance
from geopy import Nominatim
import glob
import os
import numpy as np
import pandas as pd
import yaml


def parse_args():
    """
    Parse command line arguments
    The

    :return args: namespace containing the arguments passed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dir', '-d',
        type=str,
        help='Path to directory containing SOS xlsx files',
    )
    return parser.parse_args()


def read_yml(yml_name):
    """
    Read YAML file

    :param str yml_name: File name of config yaml with its full path
    :return: dict config: Configuration parameters
    """
    with open(yml_name, 'r') as f:
        config = yaml.safe_load(f)
    return config


def read_data(file_path, is_csv=False):
    """
    Reads csv or xlsx file if present in data_dir

    :param str file_path: Path to csv or xlsx data
    :param bool is_csv: If file is csv (if not, it assumes xlsx)
    :return pd.DataFrame data_frame: Dataframe with the most common site names
    and their coordinates.
    """
    try:
        if is_csv:
            data_frame = pd.read_csv(file_path)
        else:
            data_frame = pd.read_excel(file_path, na_values=['UNK', 'Unk', '-', '#REF!'])
    except FileNotFoundError:
        print("File not found: {}".format(file_path))
        data_frame = None
    return data_frame


class DataPipeline:
    """
    Class for extracting, transforming and loading Save Our Shores
    cleanup data.
    Extract: Read all xslx files in a given directory
    Transform: Check if columns are on the right axes, flip if not.
    Consolidate debris categories that can have various names and
    spellings. Consolidate site names that can have various names
    and spellings. If a site name is listed as geographic coordinates,
    try to match them to a list of site names with known coordinates.
    Load: Save a csv file with data from all years combined.
    SOS might eventually setup a relational database on a server,
    in which case an ORM can be used to load data there.
    """
    def __init__(self,
                 data_dir):
        self.data_dir = data_dir
        # Read config file for columns (date, location, debris categories etc)
        self.col_config = self.read_col_config()
        coords_path = os.path.join(self.data_dir, 'cleanup_site_coordinates.csv')
        self.site_coords = read_data(coords_path, is_csv=True)
        self.cleaned_data = []
        # Find data files
        self.file_paths = self.find_data_files()
        self.sos_data = None

    def transform_data(self):
        for file_path in self.file_paths:
            print("Analyzing file: ", file_path)
            self.sos_data = read_data(file_path)
            self.orient_data()
            self.clean_columns()
            # Can't have numeric values in cleanup site
            self.sos_data['Cleanup Site'].replace([0, 1], np.nan)
            self.sos_data['Date'].replace(0, np.nan)
            # All datasets must contain date and site (this also removes any summary)
            self.sos_data.dropna(subset=['Cleanup Site', 'Date'])
            self.merge_sites()
            # Find Cleanup Sites that are coordinates instead of names
            # Try to match them to sites with known coordinates
            self.site_names_from_coords()
            self.cleaned_data.append(self.sos_data)

    @staticmethod
    def read_col_config(column_config_name='column_categories.yml'):
        """
        Read column config file.

        :param str column_config_name: Name of config file (assumed in dir for now0
        :return pd.DataFrame col_info: Info for each column in dataset:
            Name str
            Type str: datetime, str, int, float
            Required bool
            Material str
            Sources list of str
        """
        config = read_yml(column_config_name)
        col_names = list(config.keys())
        assert 'Date' in col_names, "Date has to be included in the config"
        for col_name in col_names:
            col_info = config[col_name]
            source_names = [col_name]
            material = 'Mixed'
            required = False
            col_type = 'int'
            activity = 'Various'
            if col_info is not None:
                if 'sources' in col_info:
                    source_names += col_info['sources']
                if 'material' in col_info:
                    material = col_info['material']
                if 'activity' in col_info:
                    activity = col_info['activity']
                if 'required' in col_info and isinstance(col_info['required'], bool):
                    required = col_info['required']
                if 'type' in col_info and isinstance(col_info['type'], str):
                    if col_info['type'] in {'datetime', 'float', 'str', 'int'}:
                        col_type = col_info['type']
            config[col_name] = {
                'sources': source_names,
                'type': col_type,
                'required': required,
                'material': material,
                'activity': activity,
            }
        # Add 'Other' to config as well
        config['Other'] = {
            'sources': ['Any items not in config'],
            'type': 'int',
            'required': False,
            'material': 'Mixed',
            'activity': 'Various',
        }
        return config

    def find_data_files(self):
        file_paths = glob.glob(os.path.join(self.data_dir, '*.xlsx'))
        # Remove coordinates file
        file_paths = [s for s in file_paths if not s.endswith('Coordinates.xlsx')]
        assert len(file_paths) > 0, "No xlsx files in {}".format(self.data_dir)
        return file_paths

    def orient_data(self):
        """
        Some of the older datasets have items as rows and cleanups as columns.
        Check if this is the case, and if so, transpose the dataframe.
        Some datasets also have 'Other' items each listed as its own column (or
        row if transposed). If so, merge them into one single 'Other' column.

        :param pd.DataFrame sos_data: One year's worth of SOS data
        :return pd.DataFrame sos_data: Data with items in its columns and
        cleanups in its rows.
        """
        col_names = list(self.sos_data)
        # Check if table axes are flipped (items should be in columns)
        nbr_unknowns = [col for col in col_names if isinstance(col, str) and 'Unnamed' in col]
        if len(nbr_unknowns) > 0:
            # Set index to be totals before transposing
            self.sos_data = self.sos_data.set_index(col_names[0]).rename_axis(None)
            self.sos_data = self.sos_data.T
            # Drop NaN columns
            if self.sos_data.columns.isna().any():
                self.sos_data = self.sos_data.drop([np.nan], axis=1)
            # Drop NaN rows
            self.sos_data = self.sos_data.dropna(how='all')

    def clean_columns(self):
        """
        Uses the column config yaml file that specifies which columns should
        be in the destination dataframe and where to look for them in the
        source data.
        Each entry in the config specifies column name in the destination
        data, which column names in the source file (+ destination name)
        that should be searched for and potentially combined, the data format
        for that column, and if it's required. Date is a special case that has to
        be included in the config. E.g:
        Date:
          sources: ['Date Of Cleanup Event/Fecha', 'Cleanup Date']
          type: datetime
          required: True

        Valid types: 'datetime', 'float', 'str' and 'int'.
        If type isn't specified, default is int.
        required can be True or False. If unspecified, default is False.
        Source columns with numeric content that are not listed in the config file
        will be combined into one destination column named 'Other'.

        Comments:  Inspired by NOAA's ocean debris report.
        It's hard to completely follow NOAA's categories because some of the
        SOS data is bundled differently.
        E.g. NOAA has fishing.line, fishing.net and fishinggear,
        whereas SOS has categories such as
        'Fishing Lines, Nets, Traps, Ropes, Pots', 'Fishing gear (lures, nets, etc.)'
        as well as several other variations. In this case I've bundled them as
        'Fishing Gear'.
        There is also the question if you should lump categories together by items
        or materials. I believe NOAA did both, but that might have been two
        different processes.

        :param pd.DataFrame sos_data: Source data, after orienting columns
        :param dict config: Column info from config file
        :return pd.DataFrame df: Destination data, with columns specified by config
        """
        # Change all source column names to uppercase
        self.sos_data.columns = map(lambda x: str(x).title(), self.sos_data.columns)
        # Create destination dataframe
        sos_cleaned = pd.DataFrame()
        # Create table containing item info
        dest_cols = list(self.col_config)
        # Start with the required column Date
        col_isect = self._get_source_cols(
            col_info=self.col_config['Date'],
            sos_names=list(self.sos_data),
        )
        # All dates must be datetime objects
        self.sos_data[col_isect[0]] = pd.to_datetime(
            self.sos_data[col_isect[0]],
            format='%Y-%m-%d',
            errors='coerce')
        self.sos_data = self.sos_data.dropna(subset=[col_isect[0]])
        self.sos_data = self.sos_data.reset_index(drop=True)
        dest_cols.remove('Date')
        sos_cleaned['Date'] = self.sos_data[col_isect[0]].copy()
        self.sos_data = self.sos_data.drop(col_isect[0], axis=1)
        # Old data has 'Volunteer Hours', which is 'Duration (Hrs)' * 'Adult Volunteers'
        if 'Volunteer Hours' in self.sos_data.columns:
            self.sos_data['# Of Volunteers'] = \
                self.sos_data['# Of Volunteers'].replace(0, 1)
            self.sos_data['Duration (Hrs)'] = (
                    self.sos_data['Volunteer Hours'] /
                    self.sos_data['# Of Volunteers'].fillna(1))
            self.sos_data = self.sos_data.drop('Volunteer Hours', axis=1)
        # Loop through remaining names in config
        sos_names = list(self.sos_data)
        for dest_name in dest_cols:
            col_info = self.col_config[dest_name]
            col_isect = self._get_source_cols(
                col_info=col_info,
                sos_names=sos_names,
            )
            if len(col_isect) > 0:
                if col_info['type'] == 'str':
                    sos_cleaned[dest_name] = self.sos_data[col_isect[0]].astype(str)
                    self.sos_data = self.sos_data.drop([col_isect[0]], axis=1)
                elif col_info['type'] == 'datetime':
                    sos_cleaned[dest_name] = pd.to_datetime(self.sos_data[col_isect[0]])
                    self.sos_data = self.sos_data.drop([col_isect[0]], axis=1)
                else:
                    sos_cleaned[dest_name] = 0.
                    for col_name in col_isect:
                        # Sometimes there are both numbers and strings in cols *sigh*
                        # sos_data[col_name] = sos_data[col_name].apply(
                        #     lambda x: 0 if isinstance(x, str) else x)
                        self.sos_data[col_name] = pd.to_numeric(
                            self.sos_data[col_name], errors='coerce',
                        )
                        sos_cleaned[dest_name] += self.sos_data[col_name].fillna(0)
                        self.sos_data = self.sos_data.drop([col_name], axis=1)
        # Sum rest of the data in an 'Other' column
        sos_cleaned['Other'] = self.sos_data.fillna(0).sum(axis=1, numeric_only=True)
        # Assign sos_cleaned as sos_data
        self.sos_data = sos_cleaned.copy()

    @staticmethod
    def _get_source_cols(col_info, sos_names):
        """
        Find desired columns in source data, given a config column name.

        :param dict col_info: Info for column name
        :param list sos_names: List of column names in source data
        :return list col_isect: Intersection of columns to search for and
            columns in the source data.
        """
        col_isect = list(set(col_info['sources']).intersection(set(sos_names)))
        # if column is required, there must be exactly one source column
        if col_info['required']:
            assert len(col_isect) == 1, (
                "Can't find required column")
        # if type is str or datetime, they can't be added together
        if col_info['type'] == 'str' or col_info['type'] == 'datetime':
            assert len(col_isect) <= 1, (
                "Can't add columns {} of type {}".format(col_isect, col_info['type']))
        return col_isect

    def merge_sites(self, site_config_name='site_categories.yml'):
        """
        Standardizing cleanup site names, so each site has its own name that
        is consistent across data sets.

        :param pd.DataFrame sos_data: Dataframe processed with the merge_columns function
        :param str site_config_name: Path to YAML file containing site names and search keys
        """
        # First remove leading and trailing spaces
        self.sos_data['Cleanup Site'] = self.sos_data['Cleanup Site'].apply(
            lambda s: s.strip())
        # Capitalize names
        self.sos_data['Cleanup Site'] = self.sos_data['Cleanup Site'].apply(
            lambda s: str(s).title())
        # Remove . in strings
        self._replace_name(".", "")
        self._replace_name(" To ", " - ")
        # Remove St and Ave
        self._replace_name(" Street", "")
        self._replace_name(" Ave", "")
        # Call San Lorenzo River 'SLR'
        self._replace_name("Slr", "SLR")
        self._replace_name("Sl River -", "SLR @")
        self._replace_name("San Lorenzo River", "SLR")
        self._replace_name("San Lorenzo R", "SLR")
        self._replace_name("SLR:", "SLR @")
        self._replace_name("SLR-", "SLR @")
        self._replace_name("SLR At", "SLR @")
        self._replace_name("SLR -", "SLR @")
        self._replace_name("SLR Cleanup", "SLR")

        site_config = read_yml(site_config_name)
        # Apply some renaming according to config (check with SOS)
        for site_name in list(site_config.keys()):
            self._rename_site(site_name, site_config[site_name])

    def _replace_name(self, old_str, new_str):
        """
        Replaces Cleanup Site names
        """
        self.sos_data['Cleanup Site'] = self.sos_data['Cleanup Site'].apply(
            lambda s: str(s).replace(old_str, new_str))

    def _rename_site(self, site_name, site_keys):
        """
        Helper function that renames sites to commonly used names

        :param str site_name: Final site name given key substring
        :param list site_key: Any site containing this substring will be
            renamed to site_name
        """
        if isinstance(site_keys, str):
            site_keys = [site_keys]
        for site_key in site_keys:
            self.sos_data['Cleanup Site'] = self.sos_data['Cleanup Site'].apply(
                lambda s: site_name if s.find(site_key) >= 0 else s)

    def site_names_from_coords(self, dist_thresh=1.5):
        """
        Some Cleanup Sites have coordinates in string format instead of names.
        Replace them with names for knows sites if possible. A replacement
        with a site name is made if if the geographic coordinates are within
        a min_thresh distance (km) from a known site.

        :param float dist_thresh: Max distance for site name assignment (km)
        """
        coord_sites = self.sos_data[self.sos_data['Cleanup Site'].str.contains(', ')]
        for idx, row in coord_sites.iterrows():
            c = row['Cleanup Site'].split(', ')
            # If coordinates are read as integer strings
            if c[0].isdigit() and c[1][1:].isdigit():
                # Convert to valid geographic coordinates
                lat = float('0.' + c[0]) * 100
                lon = - float('0.' + c[1][1:]) * 1000
                c1 = (lat, lon)
                # Compute distances to sites with known coordinates
                min_dist = 10000
                min_name = ''
                for c_idx, c_row in self.site_coords.iterrows():
                    c2 = (c_row['Latitude'], c_row['Longitude'])
                    dist = distance.distance(c1, c2).km
                    # If this is shortest distance yet, update min
                    if dist < min_dist:
                        min_dist = dist
                        min_name = c_row['Cleanup Site']
                # Assign a site name if min distance is less than threshold
                print(min_dist, min_name)
                if min_dist < dist_thresh:
                    self.sos_data.loc[idx, 'Cleanup Site'] = min_name


def add_coords(sos_data):
    """
    This function is intended to look up lat, lon coordinates for
    cleanup sites.
    Use known site coordinates from csv first and only look up less common
    sites with missing coordinates in order to avoid running into
    timeout errors due to heavy usage:
    https://operations.osmfoundation.org/policies/nominatim/

    :param pd.DataFrame sos_data: SOS data
    :return pd.DataFrame sos_coords: SOS data with lat, lon coordinates
    """
    geolocator = Nominatim(user_agent="save_our_shores")

    for idx, row in sos_data.iterrows():
        if row['Latitude'] != row['Latitude']:
            geo_str = row['Cleanup Site'] + ', ' + row['County/City'] + ', CA'
            # If using this, need to add a 1 second delay
            geo_info = geolocator.geocode(geo_str)
            if geo_info is not None:
                coords = geo_info[1]
                sos_data.loc[idx, 'Latitude'] = coords[0]
                sos_data.loc[idx, 'Longitude'] = coords[1]
    sos_coords = sos_data[(sos_data['Latitude'] > 30) & (sos_data['Longitude'] < 100)]
    return sos_coords


def merge_data(data_dir):
    """
    Assumes that all xlsx sheets (one, sometimes two, for each year) are all in
    the same directory. There may also be a file containing site names and their
    coordinates named 'Cleanup Site Coordinates.xlsx'.

    :param str data_dir: Directory containing data files
    :return pd.DataFrame merged_data: One dataframe containing all data over
        the years, cleaned.
    """
    data_etl = DataPipeline(data_dir)
    # Analyze all files
    data_etl.transform_data()
    # Concatenate the dataframes from all years
    merged_data = pd.concat(
        data_etl.cleaned_data,
        axis=0,
        ignore_index=True,
    )
    # Sort by date
    merged_data = merged_data.sort_values(by='Date')
    # Save transformed data (may later be replaced with load to database)
    merged_data.to_csv(
        os.path.join(args.dir, "merged_sos_data.csv"),
        index=False,
    )
    # Save cleaned config file
    col_config = pd.DataFrame.from_dict(data_etl.col_config)
    col_config = col_config.T
    col_config.insert(0, 'name', col_config.index)
    col_config = col_config.reset_index(drop=True)
    col_config.to_csv(
        os.path.join(args.dir, "sos_column_info.csv"),
        index=False,
    )


def read_data_and_config(data_dir):
    """
    Check if csv file for merged data exists and reads if it does, creates if
    it doesn't. Also reads column info file.
    Adds total volunteers (adult volunteers + 0.5 * youth volunteers) and
    total items to dataframe.

    :param str data_dir: Path to data directory
    :return pd.DataFrame sos_data: Merged SOS data over all years
    :return pd.DataFrame col_config: Column info (name, sources, type,
        material, activity)
    """
    existing_file = glob.glob(os.path.join(data_dir, 'merged_sos_data.csv'))
    if len(existing_file) == 1:
        sos_data = pd.read_csv(existing_file[0])
        sos_data['Date'] = pd.to_datetime(sos_data['Date'], errors='coerce')
    else:
        merge_data(data_dir)
        sos_data = pd.read_csv(existing_file[0])

    # Read config for columns (created when running cleanup main)
    col_config = pd.read_csv(os.path.join(data_dir, 'sos_column_info.csv'))
    # find column names that do not correspond to items (material is nan)
    nonitem_cols = list(col_config.loc[col_config['material'].isnull()]['name'])
    # Create bar graph for years 2013-23
    # Add Total Volunteers and Total Items to col config
    col_config.loc[len(col_config.index)] = ['Total Volunteers', ['Adult + 0.5*Youth'], 'float', False, np.nan, np.nan]
    col_config.loc[len(col_config.index)] = ['Total Items', ['Sum of items per event'], 'int', False, np.nan, np.nan]
    # ...and to dataframe
    items = sos_data.copy()
    items.drop(nonitem_cols, axis=1)
    sos_data['Total Items'] = items.sum(axis=1, numeric_only=True)
    sos_data['Total Volunteers'] = sos_data['Adult Volunteers'].fillna(0) + 0.5 * sos_data['Youth Volunteers'].fillna(0)
    return sos_data, col_config


if __name__ == '__main__':
    args = parse_args()
    merge_data(args.dir)
