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


def group_by_year(df, col_config):
    """
    Take the dataframe containing entries from all year, group by year
    and sum items. Sort by item sum in descending order.

    :param pd.Dataframe df: SOS data
    :param pd.DataFrame col_config: Column configuration including type, material
    :return pd.DataFrame annual_data: SOS data grouped by year
    """
    annual_data = df.copy()
    # Compute total of columns
    nonnumeric_cols = list(
        col_config.loc[~col_config['type'].isin(['int', 'float'])]['name'],
    )
    nonnumeric_cols.remove('Date')
    annual_data.drop(nonnumeric_cols, axis=1, inplace=True)
    annual_data['Date'] = pd.to_datetime(
        annual_data['Date'],
        format='%Y-%m-%d',
        errors='coerce')
    annual_data = annual_data.set_index('Date').rename_axis(None)
    annual_data = annual_data.groupby(annual_data.index.year).sum()
    # Sort items by sum in descending order so it's easier to decipher variables
    s = annual_data.sum()
    s = s.sort_values(ascending=False)
    annual_data = annual_data[s.index]
    return annual_data


def orient_data(sos_data):
    """
    Some of the older datasets have items as rows and cleanups as columns.
    Check if this is the case, and if so, transpose the dataframe.
    Some datasets also have 'Other' items each listed as its own column (or
    row if transposed). If so, merge them into one single 'Other' column.

    :param pd.DataFrame sos_data: One year's worth of SOS data
    :return pd.DataFrame sos_data: Data with items in its columns and
    cleanups in its rows.
    """
    col_names = list(sos_data)
    # Check if table axes are flipped (items should be in columns)
    nbr_unknowns = [col for col in col_names if isinstance(col, str) and 'Unnamed' in col]
    if len(nbr_unknowns) > 0:
        # Set index to be totals before transposing
        sos_data = sos_data.set_index(col_names[0]).rename_axis(None)
        sos_data = sos_data.T
        # Drop NaN columns
        if sos_data.columns.isna().any():
            sos_data.drop([np.nan], axis=1, inplace=True)
        # Drop NaN rows
        sos_data = sos_data.dropna(how='all')
    return sos_data


def add_coords(sos_data):
    """
    This function is intended to look up lat, lon coordinates for
    cleanup sites, but I'm currently running into a timeout error
    when trying it for a sos_data dataframe.
    TODO: use known coordinates from csv first and only look up missing coords

    :param pd.DataFrame sos_data: SOS data
    :return pd.DataFrame sos_coords: SOS data with lat, lon
    """
    geolocator = Nominatim(user_agent="save_our_shores")
    # sos_data['Latitude'] = 0.
    # sos_data['Longitude'] = 0.
    for idx, row in sos_data.iterrows():
        if row['Latitude'] != row['Latitude']:
            geo_str = row['Cleanup Site'] + ', ' + row['County/City'] + ', CA'
            geo_info = geolocator.geocode(geo_str)
            if geo_info is not None:
                coords = geo_info[1]
                sos_data.loc[idx, 'Latitude'] = coords[0]
                sos_data.loc[idx, 'Longitude'] = coords[1]
    sos_coords = sos_data[(sos_data['Latitude'] > 30) & (sos_data['Longitude'] < 100)]
    return sos_coords


def _add_cols(sos_data, target_col, source_cols):
    """
    Helper function for merging columns

    :param pd.DataFrame sos_data: Raw data from xlsx sheet
    :param str target_col: Name of new/existing target column
    :param list (str) source_cols: Columns to be merged into new column
    """
    # Check if target col already exists
    existing_cols = list(sos_data)
    if target_col not in existing_cols:
        sos_data[target_col] = 0.
    else:
        if sos_data[target_col].dtype == 'O':
            sos_data[target_col] = 0.
    for source_col in source_cols:
        if source_col in existing_cols:
            if target_col != source_col:
                if sos_data[source_col].dtype == 'O':
                    # Sometimes there are both numbers and strings in cols *sigh*
                    sos_data[source_col] = sos_data[source_col].apply(
                        lambda x: 0 if isinstance(x, str) else x)
                sos_data[target_col] += sos_data[source_col]
                sos_data.drop([source_col], axis=1, inplace=True)


def _rename_site(sos_data, site_name, site_keys):
    """
    Helper function that renames sites to commonly used names

    :param pd.Dataframe sos_data: Data
    :param str site_name: Final site name given key substring
    :param list site_key: Any site containing this substring will be
        renamed to site_name
    """
    if isinstance(site_keys, str):
        site_keys = [site_keys]
    for site_key in site_keys:
        sos_data['Cleanup Site'] = sos_data['Cleanup Site'].apply(
            lambda s: site_name if s.find(site_key) >= 0 else s)


def _replace_name(sos_data, old_str, new_str):
    sos_data['Cleanup Site'] = sos_data['Cleanup Site'].apply(
        lambda s: str(s).replace(old_str, new_str))


def site_names_from_coords(sos_data, coords, dist_thresh=1.):
    """
    Some Cleanup Sites have coordinates in string format instead of names.
    Try to replace them with names for know sites if possible.

    :param pd.DataFrame sos_data: SOS data
    :param pd.DataFrame coords: Cleanup sites with known coordinates
    :param float dist_thresh: Max distance for site name assignment (km)
    """
    coord_sites = sos_data[sos_data['Cleanup Site'].str.contains(', ')]
    for idx, row in coord_sites.iterrows():
        c = row['Cleanup Site'].split(', ')
        if c[0].isdigit() and c[1][1:].isdigit():
            lat = float('0.' + c[0]) * 100
            lon = - float('0.' + c[1][1:]) * 1000
            c1 = (lat, lon)
            min_dist = 10000
            min_name = ''
            for c_idx, c_row in coords.iterrows():
                c2 = (c_row['Latitude'], c_row['Longitude'])
                dist = distance.distance(c1, c2).km
                if dist < min_dist:
                    min_dist = dist
                    min_name = c_row['Cleanup Site']
            if min_dist < dist_thresh:
                sos_data.loc[idx, 'Cleanup Site'] = min_name


def merge_sites(sos_data, coords, config_name='site_categories.yml'):
    """
    Standardizing cleanup site names, so each site has its own name that
    is consistent across data sets.

    TODO: Much of the 2020 data is given in lon, lat coords instead of names.
    Need to convert these, and convert names to lon, lat for map plots.
    geopy Nominatim seems to not work for many types on input...
    Find other free service?

    :param pd.DataFrame sos_data: Dataframe processed with the merge_columns function
    :param str config_name: Path to YAML file containing site names and search keys
    :param pd.DataFrame coords: Dataframe containing lat, lon coords for common sites
    """
    # First remove leading and trailing spaces
    sos_data['Cleanup Site'] = sos_data['Cleanup Site'].apply(
        lambda s: s.strip())
    # Capitalize names
    sos_data['Cleanup Site'] = sos_data['Cleanup Site'].apply(
        lambda s: str(s).title())
    # Remove . in strings
    _replace_name(sos_data, ".", "")
    _replace_name(sos_data, " To ", " - ")
    # Remove St and Ave
    _replace_name(sos_data, " Street", "")
    _replace_name(sos_data, " Ave", "")
    # Call San Lorenzo River 'SLR'
    _replace_name(sos_data, "Slr", "SLR")
    _replace_name(sos_data, 'Sl River -', 'SLR @')
    _replace_name(sos_data, "San Lorenzo River", "SLR")
    _replace_name(sos_data, "San Lorenzo R", "SLR")
    _replace_name(sos_data, "SLR:", "SLR @")
    _replace_name(sos_data, "SLR-", "SLR @")
    _replace_name(sos_data, "SLR At", "SLR @")
    _replace_name(sos_data, 'SLR -', "SLR @")
    _replace_name(sos_data, 'SLR Cleanup', 'SLR')

    config = read_yml(config_name)
    # Apply some renaming according to config (check with SOS)
    for site_name in list(config.keys()):
        _rename_site(sos_data, site_name, config[site_name])

    # Find Cleanup Sites that are coordinates instead of names
    site_names_from_coords(sos_data, coords)

    return sos_data


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


def read_col_config(column_config='column_categories.yml'):
    """
    Read column config file.

    :param str column_config: Name of config file (assumed in dir for now0
    :return pd.DataFrame col_info: Info for each column in dataset:
        Name str
        Type str: datetime, str, int, float
        Required bool
        Material str
        Sources list of str
    """
    config = read_yml(column_config)
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


def clean_columns(sos_data, config):
    """
    Reads a config yaml file that specifies which columns should
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
    TODO: todo make config file name an input

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
    sos_data.columns = map(lambda x: str(x).title(), sos_data.columns)
    # Create destination dataframe
    df = pd.DataFrame()
    # Create table containing item info
    dest_cols = list(config)
    # Start with the required column Date
    col_isect = _get_source_cols(
        col_info=config['Date'],
        sos_names=list(sos_data),
    )
    # All dates must be datetime objects
    sos_data[col_isect[0]] = pd.to_datetime(
        sos_data[col_isect[0]],
        format='%Y-%m-%d',
        errors='coerce')
    sos_data.dropna(subset=[col_isect[0]], inplace=True)
    sos_data = sos_data.reset_index(drop=True)
    dest_cols.remove('Date')
    df['Date'] = sos_data[col_isect[0]].copy()
    sos_data.drop(col_isect[0], axis=1, inplace=True)
    # Old data has 'Volunteer Hours', which is 'Duration (Hrs)' * 'Adult Volunteers'
    if 'Volunteer Hours' in sos_data.columns:
        sos_data['# Of Volunteers'].replace(0, 1, inplace=True)
        sos_data['Duration (Hrs)'] = sos_data['Volunteer Hours'] / sos_data['# Of Volunteers'].fillna(1)
        sos_data.drop('Volunteer Hours', axis=1, inplace=True)
    # Loop through remaining names in config
    for dest_name in dest_cols:
        col_info = config[dest_name]
        col_isect = _get_source_cols(
            col_info=col_info,
            sos_names=list(sos_data),
        )
        if len(col_isect) > 0:
            if col_info['type'] == 'str':
                df[dest_name] = sos_data[col_isect[0]].astype(str)
                sos_data.drop([col_isect[0]], axis=1, inplace=True)
            elif col_info['type'] == 'datetime':
                df[dest_name] = pd.to_datetime(sos_data[col_isect[0]])
                sos_data.drop([col_isect[0]], axis=1, inplace=True)
            else:
                df[dest_name] = 0.
                for col_name in col_isect:
                    # Sometimes there are both numbers and strings in cols *sigh*
                    # sos_data[col_name] = sos_data[col_name].apply(
                    #     lambda x: 0 if isinstance(x, str) else x)
                    sos_data[col_name] = pd.to_numeric(sos_data[col_name], errors='coerce')
                    df[dest_name] += sos_data[col_name].fillna(0)
                    sos_data.drop([col_name], axis=1, inplace=True)
    # Sum rest of the data in an 'Other' column
    df['Other'] = sos_data.fillna(0).sum(axis=1, numeric_only=True)
    return df


def merge_data(data_dir):
    """
    Assumes that all xlsx sheets (one, sometimes two, for each year) are all in
    the same directory. There may also be a file containing site names and their
    coordinates named 'Cleanup Site Coordinates.xlsx'.

    :param str data_dir: Directory containing data files
    :return pd.DataFrame merged_data: One dataframe containing all data over
        the years, cleaned.
    """
    file_paths = glob.glob(os.path.join(data_dir, '*.xlsx'))
    # Remove coordinates file
    file_paths = [s for s in file_paths if not s.endswith('Coordinates.xlsx')]
    config = read_col_config()
    coords = pd.read_csv(os.path.join(data_dir, 'cleanup_site_coordinates.csv'))
    cleaned_data = []
    for file_path in file_paths:
        print("Analyzing file: ", file_path)
        sos_data = pd.read_excel(file_path, na_values=['UNK', 'Unk', '-', '#REF!'])
        sos_data = orient_data(sos_data)
        sos_data = clean_columns(sos_data, config)
        # Can't have numeric values in cleanup site
        sos_data['Cleanup Site'].replace([0, 1], np.NaN, inplace=True)
        sos_data['Date'].replace(0, np.NaN, inplace=True)
        # All datasets must contain date and site (this also removes any summary)
        sos_data.dropna(subset=['Cleanup Site', 'Date'], inplace=True)
        # TODO: separate site names and lat, lon coordinates
        sos_data = merge_sites(sos_data, coords=coords)
        cleaned_data.append(sos_data)
    # Concatenate the dataframes
    merged_data = pd.concat(
        cleaned_data,
        axis=0,
        ignore_index=True,
    )
    # Sort by date
    merged_data.sort_values(by='Date', inplace=True)
    return merged_data, config


def read_data(data_dir):
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
        sos_data = cleanup.merge_data(data_dir)
        sos_data.to_csv(os.path.join(data_dir, "merged_sos_data.csv"), index=False)

    # Read config for columns (created when running cleanup main)
    col_config = pd.read_csv(os.path.join(data_dir, 'sos_column_info.csv'))
    # find column names that do not correspond to items (material is nan)
    nonitem_cols = list(col_config.loc[col_config['material'].isnull()]['name'])
    # Create bar graph for years 2013-23
    # Add Total Volunteers and Total Items to col config
    col_config.loc[len(col_config.index)] = ['Total Volunteers', ['Adult + 0.5*Youth'], 'float', False, np.NaN, np.NaN]
    col_config.loc[len(col_config.index)] = ['Total Items', ['Sum of items per event'], 'int', False, np.NaN, np.NaN]
    # ...and to dataframe
    items = sos_data.copy()
    items.drop(nonitem_cols, axis=1, inplace=True)
    sos_data['Total Items'] = items.sum(axis=1, numeric_only=True)
    sos_data['Total Volunteers'] = sos_data['Adult Volunteers'].fillna(0) + 0.5 * sos_data['Youth Volunteers'].fillna(0)
    return sos_data, col_config


if __name__ == '__main__':
    args = parse_args()
    merged_data, config = merge_data(args.dir)
    # Save dataframe with all years combined
    merged_data.to_csv(
        os.path.join(args.dir, "merged_sos_data.csv"),
        index=False,
    )
    # Save cleaned config file
    config = pd.DataFrame.from_dict(config)
    config = config.T
    config.insert(0, 'name', config.index)
    config = config.reset_index(drop=True)
    config.to_csv(
        os.path.join(args.dir, "sos_column_info.csv"),
        index=False,
    )
