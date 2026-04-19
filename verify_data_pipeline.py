"""
Data-pipeline integrity verification
-------------------------------------
Runs the preprocessing + feature-engineering + heterogeneous-integration
stages of `pipeline.py` using ONLY numpy/pandas/matplotlib — no sklearn/scipy —
so the data side can be validated independently of the modelling stack.

Produces a small report (data_verification_report.txt) with sanity checks.
"""
from math import asin, cos, radians, sin, sqrt
import numpy as np
import pandas as pd

# PATHS / CONFIG
from config import DATASET_DIR, DARWIN_BUS_TRAVEL_DATA_DIR , DARWIN_CBD, OUTPUT_DIR


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))


report = []
def log(msg):
    print(msg)
    report.append(msg)


log("=" * 70)
log("DATA PIPELINE VERIFICATION")
log("=" * 70)

# 1. Load
stop_times = pd.read_csv(DARWIN_BUS_TRAVEL_DATA_DIR / "stop_times.txt")
trips = pd.read_csv(DARWIN_BUS_TRAVEL_DATA_DIR / "trips.txt")
stops = pd.read_csv(DARWIN_BUS_TRAVEL_DATA_DIR / "stops.txt")
routes = pd.read_csv(DARWIN_BUS_TRAVEL_DATA_DIR / "routes.txt")
calendar = pd.read_csv(DARWIN_BUS_TRAVEL_DATA_DIR / "calendar.txt")
sa2 = pd.read_csv(DATASET_DIR / "darwin_sa2_population_dataset.csv")

log(f"\n[LOAD] stop_times={len(stop_times):,} | trips={len(trips):,} | "
    f"stops={len(stops):,} | routes={len(routes):,} | sa2={len(sa2)}")

# 2. Preprocess
stop_times["arrival_td"] = pd.to_timedelta(stop_times["arrival_time"], errors="coerce")
stop_times["departure_td"] = pd.to_timedelta(stop_times["departure_time"], errors="coerce")
stop_times = stop_times.dropna(subset=["arrival_td", "departure_td"])
stop_times["stop_sequence"] = pd.to_numeric(stop_times["stop_sequence"], errors="coerce")
stop_times["shape_dist_traveled"] = pd.to_numeric(stop_times["shape_dist_traveled"], errors="coerce")
stop_times = stop_times.dropna(subset=["stop_sequence", "shape_dist_traveled"])

# 3. Trip aggregation
trip_summary = stop_times.groupby("trip_id").agg(
    start_time=("departure_td", "min"),
    end_time=("arrival_td", "max"),
    num_stops=("stop_sequence", "max"),
    trip_distance_km=("shape_dist_traveled", "max"),
).reset_index()
trip_summary["travel_time_min"] = (
    trip_summary["end_time"] - trip_summary["start_time"]
).dt.total_seconds() / 60
trip_summary["start_hour"] = trip_summary["start_time"].dt.total_seconds() / 3600
trip_summary = trip_summary[
    (trip_summary["travel_time_min"] > 0)
    & (trip_summary["trip_distance_km"] > 0)
    & (trip_summary["num_stops"] >= 2)
].copy()
q1, q3 = trip_summary["travel_time_min"].quantile([0.01, 0.99])
trip_summary = trip_summary[
    (trip_summary["travel_time_min"] >= q1) & (trip_summary["travel_time_min"] <= q3)
]
log(f"[TRIPS] After preprocessing: {len(trip_summary):,} trips")

# 4. Merge route/service metadata
trip_summary = trip_summary.merge(
    trips[["trip_id", "route_id", "service_id", "direction_id"]], on="trip_id", how="left"
)
trip_summary = trip_summary.merge(
    routes[["route_id", "route_short_name", "route_long_name"]], on="route_id", how="left"
)
cal = calendar.copy()
cal["weekday_service"] = cal[["monday","tuesday","wednesday","thursday","friday"]].sum(axis=1)
cal["weekend_service"] = cal[["saturday","sunday"]].sum(axis=1)
cal["is_weekend_only"] = ((cal["weekday_service"]==0) & (cal["weekend_service"]>0)).astype(int)
cal["is_weekday_only"] = ((cal["weekday_service"]>0) & (cal["weekend_service"]==0)).astype(int)
cal["service_days_per_week"] = cal[["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]].sum(axis=1)
trip_summary = trip_summary.merge(
    cal[["service_id","is_weekend_only","is_weekday_only","service_days_per_week"]],
    on="service_id", how="left"
)
trip_summary["is_peak"] = (
    ((trip_summary["start_hour"]>=7)&(trip_summary["start_hour"]<9))
    | ((trip_summary["start_hour"]>=16)&(trip_summary["start_hour"]<18))
).astype(int)

# 5. Heterogeneous integration
stops_work = stops.dropna(subset=["stop_lat","stop_lon"]).copy()
stops_work["dist_from_cbd_km"] = stops_work.apply(
    lambda r: haversine_km(r["stop_lat"], r["stop_lon"], *DARWIN_CBD), axis=1
)

# Vectorised nearest-SA2 via numpy distance matrix
slat = stops_work["stop_lat"].to_numpy()[:, None]
slon = stops_work["stop_lon"].to_numpy()[:, None]
clat = sa2["centroid_lat"].to_numpy()[None, :]
clon = sa2["centroid_lon"].to_numpy()[None, :]
# vectorised haversine
R = 6371.0
dlat = np.radians(clat - slat)
dlon = np.radians(clon - slon)
a = np.sin(dlat/2)**2 + np.cos(np.radians(slat))*np.cos(np.radians(clat))*np.sin(dlon/2)**2
dists = 2 * R * np.arcsin(np.sqrt(a))
nearest_idx = dists.argmin(axis=1)
stops_work["sa2_name"] = sa2["sa2_name"].to_numpy()[nearest_idx]
stops_work["sa2_density"] = sa2["population_density_per_km2"].to_numpy()[nearest_idx]

trip_stop_features = (
    stop_times.merge(stops_work[["stop_id","dist_from_cbd_km","sa2_density"]], on="stop_id")
    .groupby("trip_id")
    .agg(
        mean_dist_from_cbd_km=("dist_from_cbd_km","mean"),
        max_dist_from_cbd_km=("dist_from_cbd_km","max"),
        mean_sa2_density=("sa2_density","mean"),
    ).reset_index()
)
trip_summary = trip_summary.merge(trip_stop_features, on="trip_id", how="left")
trip_summary = trip_summary.dropna(subset=["mean_dist_from_cbd_km","mean_sa2_density"])

log(f"[MERGED] Final dataset: {len(trip_summary):,} trips, {trip_summary.shape[1]} columns")

# 6. Sanity checks
log("\n[SANITY CHECKS]")
tt = trip_summary["travel_time_min"]
log(f"  Travel time (min):    min={tt.min():.1f}  median={tt.median():.1f}  max={tt.max():.1f}  mean={tt.mean():.1f}")
td = trip_summary["trip_distance_km"]
log(f"  Trip distance (km):   min={td.min():.2f}  median={td.median():.2f}  max={td.max():.2f}  mean={td.mean():.2f}")
ns = trip_summary["num_stops"]
log(f"  # stops per trip:     min={ns.min()}  median={ns.median()}  max={ns.max()}  mean={ns.mean():.1f}")
cd = trip_summary["mean_dist_from_cbd_km"]
log(f"  Mean CBD distance km: min={cd.min():.2f}  median={cd.median():.2f}  max={cd.max():.2f}  mean={cd.mean():.2f}")
dd = trip_summary["mean_sa2_density"]
log(f"  Mean SA2 density:     min={dd.min():.0f}  median={dd.median():.0f}  max={dd.max():.0f}  mean={dd.mean():.0f}")

# 7. Quick feature-target correlations
log("\n[PEARSON CORRELATIONS with travel_time_min]")
cols = ["trip_distance_km","num_stops","start_hour","is_peak","is_weekend_only",
        "mean_dist_from_cbd_km","max_dist_from_cbd_km","mean_sa2_density"]
for c in cols:
    r = trip_summary[[c,"travel_time_min"]].corr().iloc[0,1]
    log(f"  {c:26s} r = {r:+.3f}")

# 8. Manual OLS closed-form fit (no sklearn) - just to sanity-check modelling pipeline
log("\n[OLS CLOSED-FORM SANITY FIT]")
feats = ["trip_distance_km","num_stops","start_hour","is_peak","is_weekend_only",
         "mean_dist_from_cbd_km","max_dist_from_cbd_km","mean_sa2_density"]
md = trip_summary[feats + ["travel_time_min"]].dropna()
md["is_weekend_only"] = md["is_weekend_only"].astype(int)
X = np.column_stack([np.ones(len(md)), md[feats].to_numpy().astype(float)])
y = md["travel_time_min"].to_numpy().astype(float)
# Ridge-like safeguard: tiny L2 if singular
try:
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
except np.linalg.LinAlgError:
    beta = np.linalg.solve(X.T@X + 1e-6*np.eye(X.shape[1]), X.T@y)
yhat = X @ beta
ss_res = ((y - yhat)**2).sum()
ss_tot = ((y - y.mean())**2).sum()
r2 = 1 - ss_res/ss_tot
rmse = float(np.sqrt(((y-yhat)**2).mean()))
mae = float(np.abs(y-yhat).mean())
log(f"  In-sample OLS: R2={r2:.4f}  RMSE={rmse:.3f}  MAE={mae:.3f}")
log(f"  Intercept: {beta[0]:.3f}")
for name, b in zip(feats, beta[1:]):
    log(f"  {name:26s}  coef = {b:+.4f}")

# Save report
out_path = OUTPUT_DIR / "data_verification_report.txt"
out_path.write_text("\n".join(report))
log(f"\nReport saved -> {out_path}")
