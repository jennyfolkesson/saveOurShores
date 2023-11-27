import argparse
import os
import numpy as np
import pandas as pd


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
        sos_data = sos_data.set_index(col_names[0]).rename_axis(None)
        sos_data = sos_data.T
        # Drop NaN columns
        sos_data.drop([np.nan], axis=1, inplace=True)
        # Drop NaN rows
        sos_data = sos_data.dropna(how='all')
        # Sum all 'Other:' items so we don't have hundreds of columns
        col_names = list(sos_data)
        if 'Other:' in col_names:
            other_idx = sos_data.columns.get_loc('Other:')
            sos_data['Other Sum'] = sos_data[col_names[other_idx:]].sum(axis=1)
            # Drop the columns whos values have been summed in 'Other Sum'
            sos_data.drop(col_names[other_idx:], axis=1, inplace=True)
    return sos_data


def rename_data(sos_data):
    """
    Rename columns with cumbersome names, and columns that have similar
    or overlapping names.

    :param pd.DataFrame sos_data: SOS data
    """
    sos_data.rename(
        columns={'Date of Cleanup Event/Fecha': 'Date',
                 'Cleanup Date': 'Date',
                 'Cleanup Site/Sitio de limpieza': 'Cleanup Site',
                 'Estimated size of location cleaned (sq miles)': 'Cleaned size (sq miles)',
                 'Cleanup Area': 'Cleaned size (sq miles)',
                 'Total Cleanup Duration (hrs)': 'Duration (hrs)',
                 '# of Volunteers': 'Adult Volunteers',
                 'Pounds of Trash Collected': 'Pounds of Trash',
                 'Pounds of Recycle Collected': 'Pounds of Recycling',
                 'County/City where the event was held?': 'County/City',
                 'County': 'County/City',
                 'Appliances (refrigerators, washers, etc.)': 'Appliances',
                 'Beverages Sachets/Pouches': 'Beverage Pouches',
                 'Beverages Sachets': 'Beverage Pouches',
                 'Toys and Beach Accessories': 'Beach Toys/Accessories',
                 'Beach chairs, toys umbrellas': 'Beach Toys/Accessories',
                 'Balloons or ribbon': 'Balloons',
                 'Bandaids or bandages': 'Bandaids',
                 'Clothes, cloth': 'Clothes/Cloth',
                 'Clothes or towels': 'Clothes/Cloth',
                 'Footwear (shoes/slippers)': 'Footwear',
                 'Shoes': 'Footwear',
                 'Glass Pieces and Chunks': 'Glass Pieces',
                 'Pieces and Chunks': 'Glass Pieces',  # 2022 has pieces and chunks, are they glass?
                 'Disposable lighters': 'Lighters',
                 'Paper Newpapers/ Magazines': 'Newspapers/Magazines',
                 'Other Plastic/ Foam Packaging': 'Other Plastic/Foam Packaging',
                 'Plastic food wrappers (ie chips or candy)': 'Plastic food wrappers',
                 'Polystyrene Foodware (foam)': 'Polystyrene Foodware',
                 'Personal Protective Equipment (masks, gloves)': 'PPE',
                 'Personal Protective Equipment': 'PPE',
                 'Lids (Plastic)': 'Plastic Lids',
                 'Rope (1 yard/meter = 1 piece)': 'Rope (yard pieces)',
                 'Syringes or needles': 'Syringes/Needles',
                 'Utensils (plastic)': 'Utensils',
                 'Forks, Knives, Spoons': 'Utensils',
                 'Wood pallets, pieces and processed wood': 'Wood pieces',
                 }, inplace=True)


def read_sheet(file_path):
    """
    Reads an xlsx spreadsheet containing one year's worth of cleanup data

    :param file_path: Path to xlsx spreadsheet
    :return pd.DataFrame sos_data: Dataframe containing spreadsheet data
    """
    sos_data = pd.read_excel(file_path, na_values=['UNK', 'Unk', '-'])
    sos_data = orient_data(sos_data)
    rename_data(sos_data)
    # All datasets must contain date and site (this also removes any summary)
    sos_data.dropna(subset=['Cleanup Site', 'Date'], inplace=True)
    sos_data = sos_data.reset_index(drop=True)
    return sos_data


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
    for source_col in source_cols:
        if source_col in existing_cols:
            if target_col != source_col and sos_data[source_col].dtype != 'O':
                sos_data[target_col] += sos_data.fillna(0)[source_col]
                sos_data.drop([source_col], axis=1, inplace=True)
        else:
            print("{} not in data frame".format(source_col))


def merge_columns(sos_data):
    """
    Merge columns inspired by NOAA's ocean debris report.
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

    :param pd.DataFrame sos_data: Dataframe containing cleanup data
    :return pd.DataFrame df: Merged Dataframe
    """
    df = sos_data.copy()
    # Merge columns

    # Beverage Containers
    _add_cols(df,
              'Beverage Containers',
              ['Cups, Plates (Paper)',
               'Cups, Plates (Plastic)',
               'Cups, Plates (Foam)'])
    # Bags
    _add_cols(df,
              'Bags',
              ['Shopping bags',
               'Other Plastic Bags',
               'Paper Bags',
               'Plastic Bags (grocery, shopping)',
               'Plastic Bags (trash) ',
               'Plastic Bags (ziplock, snack)'])
    # Bottle Caps
    _add_cols(df,
              'Bottle Caps',
              ['Bottle Caps',
               'Bottle Caps and Rings',
               'Metal Bottle Caps',
               'Plastic Bottle Caps and Rings',
               'Metal bottle caps or can pulls'])  # Not separated by material
    # Cardboard
    _add_cols(df,
              'Cardboard',
              ['Cardboard', 'Paper Cardboard'])
    # Cans
    _add_cols(df,
              'Cans',
              ['Beverage Cans',
               'Beer Cans',
               'Soda Cans',
               'Metal beverage cans'])
    # E-waste
    _add_cols(df,
              'E-Waste',
              ['E-waste',
               'Vape items/ E-smoking devices',
               'E-cigarettes'])
    # Fishing gear
    _add_cols(df,
              'Fishing Gear',
              ['Fishing gear (lures, nets, etc.)',
               'Fishing Lines, Nets, Traps, Ropes, Pots',
               'Plastic fishing line, nets, lures, floats',
               'Fishing Net & Pieces',
               'Fishing Line (1 yard/meter = 1 piece)',
               'Fishing Buoys, Pots & Traps',
               'Metal fishing hooks or lures'])
    # Food Containers
    _add_cols(df,
              'Food Containers',
              ['Food containers, cups, plates, bowls',
               'Food containers (plastic)',
               'Food containers (foam)',
               'Food Containers/ Cups/ Plates/ Bowls',
               'Paper food containers, cups, plates',
               'Paper food containers, cups, plates, bowls',
               'Paper/ Cardboard Food containers, cups, plates, bowls',
               'Plastic Polystyrene cups/plates/bowls (foam)',
               'Plastic cups, lids/plates/utensils',
               'Polystyrene Foodware',
               'Styrofoam food containers',
               'Styrofoam Cups, Plates and Bowls '])
    # Personal hygiene
    _add_cols(df,
              'Personal Hygiene',
              ['Personal Hygiene',
               'Condoms',
               'Diapers',
               'Tampons/Tampon Applicators',
               'Cotton Bud Sticks (swabs)',
               'Feminine Hygeine Products'])
    # Packaging
    _add_cols(df,
              'Plastic Packaging',
              ['Foam packaging',
               'Other Plastic/Foam Packaging',
               'Other Packaging (Clean Swell)',  # Assuming this is plastic
               'Styrofoam peanuts or packing materials'])
    # Plastic Bottles
    _add_cols(df,
              'Plastic Bottles',
              ['Plastic Bottles',
               'Other Plastic Bottles (oil, bleach, etc.)',
               'Plastic motor oil bottles'])
    # Plastic and foam pieces
    _add_cols(df,
              'Plastic Pieces',
              ['Plastic Pieces',
               'Polystyrene Pieces',
               'Foam Dock Pieces',
               'Styrofoam pieces',
               'Foam pieces'])
    # Plastic and foam (merge) to go
    _add_cols(df,
              'Plastic To-Go Items',
              ['Plastic To-Go Items',
               'Plastic Polystyrene food "to-go" containers',
               'Take Out/Away Containers (Foam)',
               'Take Out/Away Containers (Plastic)'])
    # Smoking, tobacco
    _add_cols(df,
              'Smoking/Tobacco',
              ['Smoking, tobacco (not e-waste or butts)',
               'Tobacco Packaging/Wrap',
               'Smoking, tobacco, vape items (not butts)',
               'Cigarette box or wrappers',
               'Other tobacco (packaging, lighter, etc.)'])
    # Other
    _add_cols(df,
              'Other',
              ['Other, small',
               'Other, large',
               'Other Plastics Waste',
               'Other waste (metal, paper, etc.)',
               'Other Trash (Clean Swell)',
               'Other Sum'])
    return df


def merge_sites(sos_data):
    """
    Standardizing cleanup site names, so each site has its own name that
    is consistent across data sets.

    :param pd.DataFrame sos_data: Dataframe processed with the merge_columns function
    """
    row_names = {'Three-Mile State Beach': '3-Mile State Beach',
                 '4 Mile Beach': '4-Mile State Beach',
                 'Beer Can Beach (also known as Dolphin/Sumner Beach)': 'Beer Can Beach',
                 'Carmel Meadows Beach': 'Carmel Meadows',
                 'Carmel Meadows State Beach': 'Carmel Meadows',
                 'Capitola City Beach': 'Capitola Beach',
                 'Corcoran': 'Corcoran Lagoon',
                 'Corcoran Beach':'Corcoran Lagoon',
                 '20th Ave Beach & Corcoran Lagoon': 'Corcoran Lagoon @ 20th Ave',
                 'Cowell Beach': 'Cowell/Main Beach',
                 'Cowell/ Main Beach': 'Cowell/Main Beach',
                 'Cowell and Main Beach': 'Cowell/Main Beach',
                 'Davenport Main Beach': 'Davenport Landing Beach',
                 'Del Monte Beach at Wharf II': 'Del Monte Beach at Wharf 2',
                 'Del Monte Wharf 2': 'Del Monte Beach at Wharf 2',
                 'Del Monte Beach - Wharf II': 'Del Monte Beach at Wharf 2',
                 'Del Monte State Beach/ Wharf II': 'Del Monte Beach at Wharf 2',
                 'Elkhorn Slough @ Moss Landing (Monterey Bay Kayaks)':  'Elkhorn Slough Reserve',
                 'Ford Ord Dunes State Beach': 'Fort Ord Dunes State Beach',
                 'Ft. Ord Dunes State Park': 'Fort Ord Dunes State Beach',
                 "It's Beach/Lighthouse Field State Beach": 'Lighthouse Field State Beach',
                 "It's Beach/Lighthouse":  'Lighthouse Field State Beach',
                 'Lighthouse Field':  'Lighthouse Field State Beach',
                 'Marina State Beach at Reservation Rd': 'Marina State Beach',
                 "Mitchell's Cove Beach": "Mitchell's Cove",
                 'Monterey State Beach (North of Best Western)': 'Monterey State Beach',
                 'Monterey State Beach/Tides Hotel': 'Monterey State Beach',
                 'New Brighton Beach State Park': 'New Brighton State Beach',
                 'Natural Bridges': 'Natural Bridges State Beach',
                 'North Del Monte/Tide Avenue/Casa Verde Beach': 'North Del Monte Tide Ave',
                 'Palm Beach State Park': 'Palm State Beach',
                 'Rio Del Mar': 'Rio Del Mar State Beach',
                 'San Lorenzo River at Felker St. (HWY 1 overpass) to Soquel Ave': 'SLR @ Felker to Soquel',
                 'SLR @ Felton Covered Bridge ': 'SLR @ Felton',
                 'SLR @ Felton Covered Bridge (DT Felton, New Leaf, Cremer House, to Felton Covered Bridge Park)': 'SLR @ Felton',
                 'SLR at Laurel St. Bridge':  'SLR @ Laurel St',
                 'San Lorenzo R. @ Laurel St to Riverside Ave':  'SLR @ Laurel St to Riverside Ave',
                 'San Lorenzo R. @ Riverside Ave to Main Beach':  'SLR @ Riverside Ave to Main Beach',
                 'SLR at Riverside Ave.':  'SLR @ Riverside Ave.',
                 'SLR at Soquel St. Bridge':  'SLR @ Soquel St. Bridge',
                 'San Lorenzo River (Soquel bridge to Riverside bridge)':  'SLR @ Soquel St. to Riverside',
                 'SLR Cleanup @ Soquel Ave to Laurel St.': 'SLR @ Soquel Ave to Laurel St.',
                 'San Lorenzo R. @ Soquel Ave to Laurel St': 'SLR @ Soquel Ave to Laurel St.',
                 'SLR @ Tannery ': 'SLR @ The Tannery Arts Center',
                 'SLR at Tannery': 'SLR @ The Tannery Arts Center',
                 'San Lorenzo River @ The Tannery Arts Center': 'SLR @ The Tannery Arts Center',
                 'San Lorenzo River, The Tannery': 'SLR @ The Tannery Arts Center',
                 'SLR @ Tannery Arts': 'SLR @ The Tannery Arts Center',
                 'San Lorenzo River @ Tannery': 'SLR @ The Tannery Arts Center',
                 'San Lorenzo R. @ The Tannery': 'SLR @ The Tannery Arts Center',
                 'San Lorenzo R. @ Water St to Soquel Ave': 'SLR @ Water St to Soquel Ave',
                 'SLR @ Water St to Soquel': 'SLR @ Water St to Soquel Ave',
                 'SLR: Water St. Bridge to Soquel': 'SLR @ Water St to Soquel Ave',
                 'Salinas River State Beach at Molera Rd.': 'Salinas River State Beach',
                 'Salinas River National Wildlife Reuge':  'Salinas River National Wildlife Refuge',
                 'Sand City Beach at West Bay St.': 'Sand City Beach',
                 'Shark Fin Cove': 'Shark Fin Cove State Beach',
                 'Seacliff': 'Seacliff State Beach',
                 'Seacliff ': 'Seacliff State Beach',
                 'Sunset State Beach ': 'Sunset State Beach',
                 }

    df = sos_data.set_index('Cleanup Site').rename_axis(None)
    df.rename(index=row_names, inplace=True)
    df['Cleanup Site'] = df.index
    df.reset_index(drop=True)
    return df


def merge_data(data_dir):
    file_names = os.listdir(data_dir)
    merged_data = None
    for file_name in file_names:
        file_path = os.path.join(data_dir, file_name)
        sos_data = read_sheet(file_path)
        sos_data = merge_columns(sos_data)
        sos_data = merge_sites(sos_data)
        if merged_data is None:
            merged_data = sos_data
        else:
            merged_data = pd.concat([merged_data, sos_data], axis=0, ignore_index=True)
    return merged_data


if __name__ == '__main__':
    args = parse_args()
    merged_df = merge_data(args.dir)
    merged_df.to_csv(os.path.join(args.dir, "merged_sos_data.csv"))
