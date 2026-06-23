import cdsapi
import xarray as xr
import geopandas as gpd
import pandas as pd
import os
import math
import time
from shapely.geometry import box


def download_era5(area, variables, date_from, date_to, times, output_file):
    c = cdsapi.Client(quiet=True)
    for attempt in range(3):
        try:
            c.retrieve(
                "reanalysis-era5-single-levels",
                {
                    "product_type": "reanalysis",
                    "variable": variables,
                    "date": f"{date_from}/{date_to}",
                    "time": times,
                    "area": area,
                    "data_format": "netcdf",
                },
                output_file
            )
            return
        except Exception:
            time.sleep(5)
    raise RuntimeError("ERA5 download failed after retries")


# All 24 hourly time steps — used when Daily Min / Max / Mean is selected
ALL_24_HOURS = [f"{h:02d}:00" for h in range(24)]


def run_etl(shapefile_path, variable, date_from, date_to, time_selected, plugin_dir, method="weighted"):
    """
    time_selected: either a single hour string like "12:00"
                   OR one of "Daily Min", "Daily Max", "Daily Mean"
    """
    start_time = time.time()

    # Determine whether user selected a single time step or a daily statistic
    is_daily_stat = time_selected in ("Daily Min", "Daily Max", "Daily Mean")
    times_to_download = ALL_24_HOURS if is_daily_stat else [time_selected]

    gdf = gpd.read_file(shapefile_path).to_crs("EPSG:4326")
    gdf["poly_id"] = range(len(gdf))
    results = []

    for pid, poly in gdf.iterrows():
        poly_geom = poly.geometry
        centroid = poly_geom.centroid
        minx, miny, maxx, maxy = poly_geom.bounds
        grid_res = 0.25
        west  = math.floor((minx + 180) / grid_res) * grid_res - 180
        east  = math.ceil( (maxx + 180) / grid_res) * grid_res - 180
        south = math.floor((miny + 90)  / grid_res) * grid_res - 90
        north = math.ceil( (maxy + 90)  / grid_res) * grid_res - 90
        west  -= grid_res
        east  += grid_res
        south -= grid_res
        north += grid_res
        area = [north, west, south, east]

        output_nc = os.path.join(plugin_dir, f"era5_poly_{pid}.nc")
        download_era5(
            area,
            [variable],
            date_from,
            date_to,
            times_to_download,
            output_nc
        )

        ds = xr.open_dataset(output_nc)

        if variable == "2m_temperature":
            data = ds["t2m"] - 273.15
        elif variable == "total_precipitation":
            data = ds["tp"] * 1000
        elif variable == "surface_pressure":
            data = ds["sp"] / 100
        else:
            raise ValueError("Unknown variable")

        # ── Group time steps by date ──────────────────────────────────────
        # For single time step: one entry per date
        # For daily stat: collect all 24 hourly values then reduce
        import numpy as np
        from collections import defaultdict

        # Build a dict: date_str -> list of (time, layer) pairs
        date_layers = defaultdict(list)
        for t in data.valid_time.values:
            date_str = pd.to_datetime(t).strftime("%Y-%m-%d")
            date_layers[date_str].append(data.sel(valid_time=t))

        for date_str, layers in sorted(date_layers.items()):

            if is_daily_stat:
                # Compute spatial value for each of the 24 hours, then reduce
                hourly_values = []
                for layer in layers:
                    v = _compute_spatial_value(layer, poly_geom, centroid, method)
                    if v is not None:
                        hourly_values.append(v)

                if not hourly_values:
                    value = None
                elif time_selected == "Daily Min":
                    value = float(np.min(hourly_values))
                elif time_selected == "Daily Max":
                    value = float(np.max(hourly_values))
                elif time_selected == "Daily Mean":
                    value = float(np.mean(hourly_values))

            else:
                # Single time step — existing behaviour
                layer = layers[0]
                value = _compute_spatial_value(layer, poly_geom, centroid, method)

            results.append({"DATE_STR": date_str, pid: value})

        ds.close()

    df_final = pd.DataFrame(results)
    df_final = df_final.groupby("DATE_STR").first().reset_index()

    end_time = time.time()
    runtime = end_time - start_time
    from qgis.utils import iface
    iface.messageBar().pushMessage(
        "Runtime",
        f"{method} / {time_selected} finished in {runtime:.2f} seconds",
        level=0,
        duration=5
    )
    return df_final


def _compute_spatial_value(layer, poly_geom, centroid, method):
    """
    Compute a single scalar value from one ERA5 layer for one polygon.
    Extracted as a helper so it can be called once per hour for daily stats.
    """
    df = layer.to_dataframe().reset_index()
    df["value"] = df.iloc[:, -1]

    lon = layer.longitude.values
    lat = layer.latitude.values
    dx = abs(lon[1] - lon[0]) / 2 if len(lon) > 1 else 0.125
    dy = abs(lat[1] - lat[0]) / 2 if len(lat) > 1 else 0.125

    grid_polys = []
    vals = []
    for _, r in df.iterrows():
        cell = box(
            r.longitude - dx,
            r.latitude  - dy,
            r.longitude + dx,
            r.latitude  + dy
        )
        grid_polys.append(cell)
        vals.append(r["value"])

    grid = gpd.GeoDataFrame(
        {"value": vals},
        geometry=grid_polys,
        crs="EPSG:4326"
    )

    if method == "centroid":
        points = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df.longitude, df.latitude),
            crs="EPSG:4326"
        )
        points["dist"] = points.geometry.distance(centroid)
        nearest = points.sort_values("dist").iloc[0]
        return nearest["value"]

    elif method == "gridmean":
        inter = grid[grid.intersects(poly_geom)]
        if inter.empty:
            return None
        return inter["value"].mean()

    else:  # weighted (default)
        inter = gpd.overlay(
            gpd.GeoDataFrame(geometry=[poly_geom], crs="EPSG:4326"),
            grid,
            how="intersection"
        )
        if inter.empty:
            return None
        inter_m = inter.to_crs(3857)
        inter["area"] = inter_m.area
        inter["weighted"] = inter["value"] * inter["area"]
        return inter["weighted"].sum() / inter["area"].sum()