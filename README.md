# Environmental ETL - QGIS Plugin
## README - How to Use the Plugin

Author: Praveenkumar Saminathan | Supervisor: Prof. Lorenzo Gianquintieri
Politecnico di Milano | MSc Geoinformatics Engineering | 2025-2026

This plugin was developed as part of an MSc thesis in Geoinformatics Engineering
at Politecnico di Milano (2025-2026), supervised by Prof. Lorenzo Gianquintieri.

Repository: https://github.com/Orange3456/environmental-etl-qgis-plugin

---

## WHAT THIS PLUGIN DOES

Environmental ETL is a QGIS plugin that automatically downloads ERA5 climate
data from the Copernicus Climate Data Store (CDS) and extracts polygon-level
daily values for your shapefile. No programming required.

You select a polygon layer already loaded in QGIS, choose a variable, date
range, time step or daily statistic, and aggregation method. The plugin
downloads ERA5 data for each polygon, applies spatial aggregation, and saves
the results as a CSV file automatically loaded into your QGIS project.

---

## REQUIREMENTS

- QGIS 3.x (tested on QGIS 3.42)
- Python 3.10+
- A Copernicus CDS account and API key

Python libraries (install via pip or OSGeo4W shell):
  pip install cdsapi xarray geopandas pandas shapely numpy

CDS API key setup:
  1. Register at https://cds.climate.copernicus.eu
  2. Go to your profile and copy your API key
  3. Create a file at C:\Users\YourName\.cdsapirc (Windows)
     or ~/.cdsapirc (Mac/Linux)
  4. Paste the following into that file:
     url: https://cds.climate.copernicus.eu/api/v2
     key: YOUR-UID:YOUR-API-KEY

---

## INSTALLATION

1. Download the plugin folder (environmentaletl)
2. Copy the entire folder to:
   Windows: C:\Users\YourName\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\
   Mac/Linux: ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
3. Open QGIS
4. Go to Plugins > Manage and Install Plugins
5. Click the Installed tab and enable Environmental ETL
6. The plugin appears under Plugins > EnvironmentalETL > Environmental ETL
   and as a toolbar icon

---

## PLUGIN FILES

environmentaletl/
  environmental_etl.py          - Main plugin UI layer
  etl_engine.py                 - ERA5 download and aggregation engine
  EnvironmentalETL_dialog.py    - Dialog class loader
  EnvironmentalETL_dialog_base.ui - Qt dialog layout
  __init__.py                   - Plugin entry point
  metadata.txt                  - Plugin metadata
  icon.png                      - Toolbar icon
  resources.py                  - Qt resources

---

## HOW TO USE - STEP BY STEP

Step 1: Load your shapefile
  Open QGIS and load your polygon shapefile via Layer > Add Layer > Add Vector Layer.
  The shapefile must be a polygon layer (not points or lines).
  Any coordinate reference system is supported - the plugin reprojects to WGS84 internally.

Step 2: Open the plugin
  Go to Plugins > EnvironmentalETL > Environmental ETL
  OR click the Environmental ETL icon in the toolbar.

Step 3: Select Polygon Layer
  The dropdown is populated automatically from all polygon layers currently
  loaded in your QGIS project. Select the layer you want to process.

Step 4: Set Date Range
  Date From - the start date of the ERA5 data you want to extract.
  Date To   - the end date.
  ERA5 data is available from 1940-01-01 to approximately 5 days before today.
  Use the calendar popup by clicking the arrow on each date picker.
  Important: ERA5 has a ~5 day data availability lag. If you request recent
  dates, the output will silently stop at the last available date.

Step 5: Choose Option A or Option B (not both)

  OPTION A - Single Time Step:
    Select one hourly time step (00:00 to 23:00 UTC).
    The plugin downloads ERA5 at that specific hour for each day in your range.
    Output: one value per polygon per day at that hour.
    Example: selecting 12:00 gives midday values for each day.

  OPTION B - Daily Min / Max / Mean:
    Select Daily Min, Daily Max, or Daily Mean.
    The plugin downloads all 24 hourly ERA5 values for each polygon per day,
    applies your chosen spatial aggregation to each hour, then reduces the
    24 values to one number using min, max, or mean.
    Output: one daily minimum/maximum/mean value per polygon per day.
    Note: Option B downloads 24x more data than Option A and takes
    significantly longer to run.

  Important: Option A and Option B are mutually exclusive. Choosing a time
  step will clear the daily stat selection and vice versa.

Step 6: Choose ERA5 Variable
  2m Temperature      - Near-surface air temperature. Output in degrees Celsius.
                        ERA5 internal name: t2m. Converted from Kelvin: value - 273.15
  Total Precipitation - Daily total precipitation. Output in millimetres.
                        ERA5 internal name: tp. Converted from metres: value x 1000
  Surface Pressure    - Atmospheric pressure at the surface. Output in hPa.
                        ERA5 internal name: sp. Converted from Pascals: value / 100

Step 7: Choose Aggregation Method
  Centroid:
    Assigns the value of the nearest ERA5 grid point to the polygon centroid.
    Fastest method. Best for small compact polygons.
    Not recommended for large, irregular, or topographically complex polygons.

  Point-based Averaging (Polygon Mean):
    Computes the mean of all ERA5 grid points whose centres fall within the polygon.
    Better than Centroid for most polygon sizes.
    Good balance of accuracy and speed.
    Recommended for temperature and pressure when speed matters.

  Area-weighted Averaging:
    Computes a weighted mean of all ERA5 grid cells that overlap the polygon,
    with weights proportional to the fractional overlap area.
    Most accurate method. Recommended reference standard.
    Especially recommended for precipitation and for polygons with complex shapes.
    Slowest method due to geometric overlay computation.

Step 8: Click OK
  The plugin will begin downloading ERA5 data polygon by polygon.
  A message appears in the QGIS message bar when processing starts.
  Do not close QGIS while the plugin is running.
  When complete, a success message shows the output file path and runtime.

---

## OUTPUT

File format: CSV
File name: output_{variable}_{timestamp}.csv
File location: Same folder as the plugin directory

CSV structure:
  - First column: DATE_STR (format: YYYY-MM-DD)
  - Remaining columns: one column per polygon, named by polygon index (0, 1, 2, ...)
  - Each row: one date
  - Each cell: the aggregated ERA5 value for that polygon on that date

Example (2m Temperature, Centroid, 3 polygons, 3 days):
  DATE_STR,   0,      1,      2
  2026-01-01, 2.45,  -3.12,   8.90
  2026-01-02, 1.98,  -4.01,   9.12
  2026-01-03, 3.20,  -2.88,   8.55

The CSV is automatically loaded into your QGIS project as a vector layer
named: ERA5_{variable}_{shapefile_name}

---

## RUNTIME ESTIMATES

Runtime scales approximately linearly with polygon count.

Expected processing time per run (Option A, single time step):
  ~30 seconds per polygon
  30 polygons  -> ~15 minutes
  36 polygons  -> ~18 minutes
  96 polygons  -> ~48 minutes

Option B (Daily Min/Max/Mean) downloads 24x more ERA5 data per polygon
and will take approximately 10-20x longer than Option A for the same date range.

These estimates assume normal CDS API server load. During peak hours
(typically 08:00-18:00 UTC) the CDS server may be slower.

---

## REPRODUCIBILITY

The plugin uses a per-polygon download strategy: ERA5 data is downloaded
separately for each polygon using that polygon's own bounding box, snapped
to the ERA5 0.25 degree grid. This guarantees that the same polygon always
produces the same output value regardless of what other polygons are in the
same shapefile. Results are fully reproducible across runs and machines
provided the same CDS API version is used.

---

## KNOWN LIMITATIONS

1. ERA5 data availability lag (~5 days)
   ERA5 data is not available up to the current date. If your end date is
   within 5 days of today, the output CSV will contain fewer rows than
   expected. No error is raised - the file simply ends at the last
   available date.

2. Processing time scales with polygon count
   For shapefiles with many polygons (100+), processing may take several
   hours. The plugin cannot be interrupted once started without closing QGIS.

3. CDS API rate limits
   The CDS API has usage limits. If you submit many runs in rapid succession,
   requests may be queued or delayed. The plugin retries failed downloads
   up to 3 times with 5-second delays.

4. Supported variables
   The current version supports 3 ERA5 variables: 2m temperature, total
   precipitation, and surface pressure. Other ERA5 variables are not yet
   supported.

5. Option B runtime
   Daily Min/Max/Mean (Option B) downloads all 24 hourly ERA5 values per
   polygon per run, making it significantly slower than Option A. For large
   shapefiles, Option B may take many hours.

---

## CONTACT

Author: Praveenkumar Saminathan
Email:  praveennathan10@gmail.com / praveenkumar.saminathan@mail.polimi.it
Supervisor: Prof. Lorenzo Gianquintieri
Department of Electronics, Information and Bioengineering (DEIB)
Politecnico di Milano

---

## License

This project is licensed under the GNU General Public License v2.0 - see the [LICENSE](LICENSE) file for details.
