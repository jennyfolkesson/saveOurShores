import pandas as pd


def read_sheet(file_path):
    """
    Reads an xlsx spreadsheet containing one year's worth of cleanup data

    :param file_path: Path to xlsx spreadsheet
    :return pd.DataFrame sos_data: Dataframe containing spreadsheet data
    """
    sos_data = pd.read_excel(file_path, na_values=['UNK', '-'])
    # Check if there's a summary and remove it
    summary = sos_data.loc[0]
    if pd.isnull(summary['Date of Cleanup Event/Fecha']):
        sos_data = sos_data.drop([0])
    sos_data = sos_data.reset_index(drop=True)
    return sos_data


def _add_cols(sos_data, target_col, source_cols):
    """
    Helper function for merging columns

    :param pd.DataFrame sos_data: Raw data from xlsx sheet
    :param str target_col: Name of new/existing target column
    :param list (str) source_cols: Columns to be merged into new column
    """
    if target_col not in source_cols:
        sos_data[target_col] = 0.
    existing_cols = list(sos_data)
    for source_col in source_cols:
        if source_col in existing_cols:
            if target_col != source_col:
                sos_data[target_col] += sos_data.fillna(0)[source_col]
                sos_data.drop([source_col], axis=1, inplace=True)
        else:
            print("{} not in data frame".format(source_col))


def merge_columns(sos_data):
    """
    Merge columns inspired by NOAA's ocean debris report.

    :param pd.DataFrame sos_data: Dataframe containing cleanup data
    :return pd.DataFrame df: Merged Dataframe
    """
    df = sos_data.copy()
    # Merge columns
    # Cans
    _add_cols(df, 'Cans', ['Beverage Cans', 'Beer Cans', 'Soda Cans'])
    # Food Containers
    _add_cols(df,
              'Food Containers',
              ['Food containers, cups, plates, bowls',
               'Food containers (plastic)',
               'Food containers (foam)'])
    # Beverage Containers
    _add_cols(df,
              'Beverage Containers',
              ['Cups, Plates (Paper)',
               'Cups, Plates (Plastic)',
               'Cups, Plates (Foam)'])
    # Bags
    _add_cols(df,
              'Bags',
              ['Shopping bags', 'Other Plastic Bags', 'Paper Bags'])
    # Bottle Caps
    _add_cols(df, 'Bottle Caps', ['Bottle Caps', 'Bottle Caps and Rings'])
    # Plastic Bottles
    _add_cols(df, 'Plastic Bottles', ['Plastic Bottles', 'Other Plastic Bottles (oil, bleach, etc.)'])
    # Fishing gear
    _add_cols(df,
              'Fishing Gear',
              ['Fishing gear (lures, nets, etc.)',
               'Fishing Lines, Nets, Traps, Ropes, Pots',
               'Fishing Net & Pieces',
               'Fishing Line (1 yard/meter = 1 piece)'])
    # Smoking, tobacco
    _add_cols(df,
              'Smoking/Tobacco',
              ['Smoking, tobacco (not e-waste or butts)', 'Tobacco Packaging/Wrap'])
    # Personal hygiene
    _add_cols(df,
              'Personal Hygiene',
              ['Personal Hygiene', 'Condoms', 'Diapers', 'Tampons/Tampon Applicators', 'Cotton Bud Sticks (swabs)'])
    # Packaging
    _add_cols(df,
              'Plastic Packaging',
              ['Foam packaging', 'Other Plastic/ Foam Packaging'])
    # Add plastic and foam pieces
    _add_cols(df,
              'Plastic Pieces',
              ['Plastic Pieces', 'Polystyrene Pieces', 'Foam Dock Pieces'])
    # E-waste
    _add_cols(df,
              'E-Waste',
              ['E-waste', 'Vape items/ E-smoking devices'])
    # Other
    _add_cols(df,
              'Other',
              ['Other, large',
               'Other, small',
               'Other Plastics Waste',
               'Other waste (metal, paper, etc.)']
              )
    # Shorten names
    df.rename(columns={'Date of Cleanup Event/Fecha': 'Date',
                       'Cleanup Site/Sitio de limpieza': 'Cleanup Site',
                       'Total Cleanup Duration (hrs)': 'Duration (hrs)',
                       'County/City where the event was held?': 'County/City',
                       'Wood pallets, pieces and processed wood': 'Wood pieces',
                       'Appliances (refrigerators, washers, etc.)': 'Appliances',
                       'Rope (1 yard/meter = 1 piece)': 'Rope (yard pieces)',
                       'Toys and Beach Accessories': 'Beach Toys/Accessories',
                       'Footwear (shoes/slippers)': 'Footwear',
                       'Disposable lighters': 'Lighters',
                       'Polystyrene Foodware (foam)': 'Polystyrene Foodware',
                       'Personal Protective Equipment (masks, gloves)': 'PPE',
                       'Beverages Sachets/Pouches': 'Beverage Pouches',
                       'Lids (Plastic)': 'Plastic Lids',
                       'Utensils (plastic)': 'Plastic Utensils',
                       }, inplace=True)

    return df


def merge_sites(df):
    """
    Standardizing cleanup site names

    :param pd.DataFrame df: Dataframe processed with the merge_columns function
    """
    row_names = {'4 Mile Beach': '4-Mile State Beach',
                 'Carmel Meadows Beach': 'Carmel Meadows',
                 'Cowell Beach': 'Cowell/Main Beach',
                 'Cowell and Main Beach': 'Cowell/Main Beach',
                 'Davenport Main Beach': 'Davenport Landing Beach',
                 'Del Monte Beach at Wharf II': 'Del Monte Beach at Wharf 2',
                 'Del Monte Wharf 2': 'Del Monte Beach at Wharf 2',
                 'Marina State Beach at Reservation Rd': 'Marina State Beach',
                 "Mitchell's Cove Beach": "Mitchell's Cove",
                 'New Brighton Beach State Park': 'New Brighton State Beach',
                 'North Del Monte/Tide Avenue/Casa Verde Beach': 'North Del Monte Tide Ave',
                 'Palm Beach State Park': 'Palm State Beach',
                 'SLR @ Felton Covered Bridge ': 'SLR @ Felton',
                 'SLR @ Tannery ': 'SLR @ The Tannery Arts Center',
                 'Salinas River State Beach at Molera Rd.': 'Salinas River State Beach',
                 'Sand City Beach at West Bay St.': 'Sand City Beach',
                 'San Lorenzo River at Felker St. (HWY 1 overpass) to Soquel Ave': 'SLR @ Felker to Soquel',
                 'SLR Cleanup @ Soquel Ave to Laurel St.' : 'SLR @ Soquel Ave to Laurel St.',
                 }

    df = df.set_index('Cleanup Site').rename_axis(None)
    df.rename(index=row_names, inplace=True)
    df['Cleanup Site'] = df.index
    df.reset_index(drop=True)
