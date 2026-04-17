"""
PRT564 - Assessment 2: Darwin Bus Network Regression Pipeline
==============================================================

Research Question (from Assessment 1, Q1):
    To what extent can bus travel time be predicted based on route
    characteristics such as distance travelled, number of stops,
    and time of day?

This pipeline implements the end-to-end analysis required by AT2:
    1. Data preprocessing with justification
    2. Heterogeneous data integration (GTFS + ABS + geographic)
    3. Exploratory data analysis
    4. Feature engineering
    5. Regression modelling (3 models)
    6. Cross-validated evaluation with statistical tests
    7. Residual diagnostics

Data sources (heterogeneous integration):
    (a) Darwin GTFS public transit feed (Northern Territory Government)
        - Scheduled/temporal/spatial data
    (b) ABS Census 2021 Statistical Area Level 2 (SA2) population
        - External demographic data for Greater Darwin
        - Source: https://www.abs.gov.au (2021 Census DataPacks / QuickStats)
    (c) Geographic reference point - Darwin Interchange CBD centroid
        - Derived feature: Haversine distance from CBD

Group 10 - PRT564 Data Analytics & Visualisation
"""

from __future__ import annotations

import os
import warnings
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.tree import DecisionTreeRegressor

warnings.filterwarnings("ignore", category=FutureWarning)
sns.set_theme(style="whitegrid", context="talk")

# -----------------------------------------------------------------------------
# PATHS / CONFIG
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Darwin Interchange (CBD reference) - stop_id 83 in stops.txt
DARWIN_CBD = (-12.464786, 130.844340)

RANDOM_STATE = 42


# -----------------------------------------------------------------------------
# HELPER: HAVERSINE DISTANCE (km)
# -----------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometres."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def nearest_sa2(stop_lat: float, stop_lon: float, sa2_df: pd.DataFrame) -> pd.Series:
    """Return the row of sa2_df closest to (stop_lat, stop_lon)."""
    dists = sa2_df.apply(
        lambda r: haversine_km(stop_lat, stop_lon, r["centroid_lat"], r["centroid_lon"]),
        axis=1,
    )
    return sa2_df.iloc[dists.idxmin()]


# =============================================================================
# 1. LOAD DATA
# =============================================================================
print("=" * 70)
print("STAGE 1: DATA LOADING")
print("=" * 70)

stop_times = pd.read_csv(BASE_DIR / "stop_times.txt")
trips = pd.read_csv(BASE_DIR / "trips.txt")
stops = pd.read_csv(BASE_DIR / "stops.txt")
routes = pd.read_csv(BASE_DIR / "routes.txt")
calendar = pd.read_csv(BASE_DIR / "calendar.txt")
sa2 = pd.read_csv(BASE_DIR / "darwin_sa2_population.csv")

print(f"  stop_times:  {stop_times.shape[0]:>6,} rows")
print(f"  trips:       {trips.shape[0]:>6,} rows")
print(f"  stops:       {stops.shape[0]:>6,} rows")
print(f"  routes:      {routes.shape[0]:>6,} rows")
print(f"  calendar:    {calendar.shape[0]:>6,} rows")
print(f"  ABS SA2:     {sa2.shape[0]:>6,} suburbs (external source)")


# =============================================================================
# 2. PREPROCESSING (with documented justifications)
# =============================================================================
print("\n" + "=" * 70)
print("STAGE 2: PREPROCESSING")
print("=" * 70)

# --- 2.1 Parse GTFS time strings --------------------------------------------
# GTFS times can exceed 24:00:00 (e.g., 25:30:00 for next-day service).
# pd.to_timedelta handles this correctly; pd.to_datetime would NOT.
stop_times["arrival_td"] = pd.to_timedelta(stop_times["arrival_time"], errors="coerce")
stop_times["departure_td"] = pd.to_timedelta(stop_times["departure_time"], errors="coerce")

n_before = len(stop_times)
stop_times = stop_times.dropna(subset=["arrival_td", "departure_td"])
print(f"  Dropped {n_before - len(stop_times)} rows with unparseable times "
      f"(preserves GTFS timedelta semantics incl. next-day trips).")

# --- 2.2 Ensure numeric columns ---------------------------------------------
stop_times["stop_sequence"] = pd.to_numeric(stop_times["stop_sequence"], errors="coerce")
stop_times["shape_dist_traveled"] = pd.to_numeric(
    stop_times["shape_dist_traveled"], errors="coerce"
)
stop_times = stop_times.dropna(subset=["stop_sequence", "shape_dist_traveled"])

# --- 2.3 Aggregate to trip level --------------------------------------------
# Justification: Each row of stop_times is a stop-event. The regression target
# (total trip travel time) is inherently a trip-level quantity, so aggregation
# is required before modelling.
trip_summary = (
    stop_times.groupby("trip_id")
    .agg(
        start_time=("departure_td", "min"),
        end_time=("arrival_td", "max"),
        num_stops=("stop_sequence", "max"),
        trip_distance_km=("shape_dist_traveled", "max"),
    )
    .reset_index()
)
trip_summary["travel_time_min"] = (
    trip_summary["end_time"] - trip_summary["start_time"]
).dt.total_seconds() / 60
trip_summary["start_hour"] = trip_summary["start_time"].dt.total_seconds() / 3600

# Drop trivially short/zero trips (suspected data errors or non-service rows)
trip_summary = trip_summary[
    (trip_summary["travel_time_min"] > 0)
    & (trip_summary["trip_distance_km"] > 0)
    & (trip_summary["num_stops"] >= 2)
].copy()

# Remove extreme outliers using IQR rule on target (keep ~99% of trips).
# Justification: linear regression is sensitive to high-leverage outliers.
q1, q3 = trip_summary["travel_time_min"].quantile([0.01, 0.99])
n_before = len(trip_summary)
trip_summary = trip_summary[
    (trip_summary["travel_time_min"] >= q1) & (trip_summary["travel_time_min"] <= q3)
]
print(f"  Trimmed {n_before - len(trip_summary)} extreme outliers (<1st / >99th pct).")

print(f"  Trip-level dataset: {len(trip_summary):,} trips")


# =============================================================================
# 3. FEATURE ENGINEERING (GTFS internal)
# =============================================================================
print("\n" + "=" * 70)
print("STAGE 3: FEATURE ENGINEERING")
print("=" * 70)

# --- 3.1 Merge route/service info -------------------------------------------
trip_summary = trip_summary.merge(
    trips[["trip_id", "route_id", "service_id", "direction_id"]],
    on="trip_id",
    how="left",
)
trip_summary = trip_summary.merge(
    routes[["route_id", "route_short_name", "route_long_name"]],
    on="route_id",
    how="left",
)

# --- 3.2 Day-type features from calendar.txt --------------------------------
# Justification: travel-time patterns differ between weekdays and weekends
# because of differing scheduled services.
cal = calendar.copy()
cal["weekday_service"] = cal[["monday", "tuesday", "wednesday", "thursday", "friday"]].sum(axis=1)
cal["weekend_service"] = cal[["saturday", "sunday"]].sum(axis=1)
cal["is_weekend_only"] = (cal["weekday_service"] == 0) & (cal["weekend_service"] > 0)
cal["is_weekday_only"] = (cal["weekday_service"] > 0) & (cal["weekend_service"] == 0)
cal["service_days_per_week"] = cal[
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
].sum(axis=1)
trip_summary = trip_summary.merge(
    cal[["service_id", "is_weekend_only", "is_weekday_only", "service_days_per_week"]],
    on="service_id",
    how="left",
)

# --- 3.3 Peak-hour indicator ------------------------------------------------
# Darwin AM peak ~07:00-09:00, PM peak ~16:00-18:00
trip_summary["is_am_peak"] = (
    (trip_summary["start_hour"] >= 7) & (trip_summary["start_hour"] < 9)
).astype(int)
trip_summary["is_pm_peak"] = (
    (trip_summary["start_hour"] >= 16) & (trip_summary["start_hour"] < 18)
).astype(int)
trip_summary["is_peak"] = (trip_summary["is_am_peak"] | trip_summary["is_pm_peak"]).astype(int)


# =============================================================================
# 4. HETEROGENEOUS DATA INTEGRATION
# =============================================================================
print("\n" + "=" * 70)
print("STAGE 4: HETEROGENEOUS DATA INTEGRATION")
print("=" * 70)

# --- 4.1 Enrich stops with CBD distance + nearest-SA2 density ---------------
# Geographic source: external reference point (Darwin Interchange CBD).
print("  Computing per-stop CBD distance + SA2 lookup...")

stops_work = stops.dropna(subset=["stop_lat", "stop_lon"]).copy()
stops_work["dist_from_cbd_km"] = stops_work.apply(
    lambda r: haversine_km(r["stop_lat"], r["stop_lon"], *DARWIN_CBD), axis=1
)

# Assign each stop to its nearest SA2 centroid
# (Simple nearest-centroid spatial join; suitable given SA2 centroid density.)
sa2_lookup = sa2.set_index("sa2_name")
sa2_names, sa2_densities, sa2_pops = [], [], []
for _, row in stops_work.iterrows():
    nearest = nearest_sa2(row["stop_lat"], row["stop_lon"], sa2)
    sa2_names.append(nearest["sa2_name"])
    sa2_densities.append(nearest["population_density_per_km2"])
    sa2_pops.append(nearest["population_2021"])
stops_work["sa2_name"] = sa2_names
stops_work["sa2_density"] = sa2_densities
stops_work["sa2_population"] = sa2_pops

# --- 4.2 Aggregate stop-level features up to trip level --------------------
# For each trip, compute the mean CBD distance and mean SA2 density across all
# stops on that trip (weighted implicitly equal by count).
trip_stop_features = (
    stop_times.merge(stops_work[["stop_id", "dist_from_cbd_km", "sa2_density"]], on="stop_id")
    .groupby("trip_id")
    .agg(
        mean_dist_from_cbd_km=("dist_from_cbd_km", "mean"),
        max_dist_from_cbd_km=("dist_from_cbd_km", "max"),
        mean_sa2_density=("sa2_density", "mean"),
    )
    .reset_index()
)
trip_summary = trip_summary.merge(trip_stop_features, on="trip_id", how="left")

# Drop rows where integration failed (should be near zero)
trip_summary = trip_summary.dropna(
    subset=["mean_dist_from_cbd_km", "mean_sa2_density"]
)

print(f"  Integration complete - final modelling dataset: {len(trip_summary):,} trips, "
      f"{trip_summary.shape[1]} columns")


# =============================================================================
# 5. EXPLORATORY DATA ANALYSIS
# =============================================================================
print("\n" + "=" * 70)
print("STAGE 5: EXPLORATORY DATA ANALYSIS")
print("=" * 70)

# Descriptive stats
desc = trip_summary[
    [
        "travel_time_min",
        "trip_distance_km",
        "num_stops",
        "start_hour",
        "mean_dist_from_cbd_km",
        "mean_sa2_density",
    ]
].describe()
desc.to_csv(OUTPUT_DIR / "descriptive_statistics.csv")
print(desc.round(2))

# --- 5.1 Distribution of target --------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].hist(trip_summary["travel_time_min"], bins=40, color="#2E86AB", edgecolor="white")
axes[0].set_xlabel("Travel time (min)")
axes[0].set_ylabel("Frequency")
axes[0].set_title("Distribution of trip travel time")
axes[1].hist(trip_summary["trip_distance_km"], bins=40, color="#A23B72", edgecolor="white")
axes[1].set_xlabel("Trip distance (km)")
axes[1].set_ylabel("Frequency")
axes[1].set_title("Distribution of trip distance")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "01_distributions.png", dpi=120)
plt.close()

# --- 5.2 Correlation heatmap ----------------------------------------------
numeric_cols = [
    "travel_time_min",
    "trip_distance_km",
    "num_stops",
    "start_hour",
    "mean_dist_from_cbd_km",
    "max_dist_from_cbd_km",
    "mean_sa2_density",
    "is_peak",
    "is_weekend_only",
]
corr = trip_summary[numeric_cols].corr(numeric_only=True)
fig, ax = plt.subplots(figsize=(11, 8))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax,
            cbar_kws={"label": "Pearson r"})
ax.set_title("Feature correlation matrix")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "02_correlation_heatmap.png", dpi=120)
plt.close()

# --- 5.3 Scatter: distance vs travel time, coloured by SA2 density --------
fig, ax = plt.subplots(figsize=(10, 6))
sc = ax.scatter(
    trip_summary["trip_distance_km"],
    trip_summary["travel_time_min"],
    c=trip_summary["mean_sa2_density"],
    cmap="viridis",
    alpha=0.6,
    s=18,
)
ax.set_xlabel("Trip distance (km)")
ax.set_ylabel("Travel time (min)")
ax.set_title("Travel time vs distance (colour = mean SA2 population density)")
plt.colorbar(sc, label="SA2 density (per km²)")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "03_scatter_distance_vs_time.png", dpi=120)
plt.close()

# --- 5.4 Boxplot: peak vs off-peak ----------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
trip_summary.boxplot(column="travel_time_min", by="is_peak", ax=axes[0])
axes[0].set_xlabel("Peak hour (0=off-peak, 1=peak)")
axes[0].set_ylabel("Travel time (min)")
axes[0].set_title("Travel time: peak vs off-peak")
trip_summary.boxplot(column="travel_time_min", by="is_weekend_only", ax=axes[1])
axes[1].set_xlabel("Weekend-only service")
axes[1].set_ylabel("Travel time (min)")
axes[1].set_title("Travel time: weekday vs weekend services")
plt.suptitle("")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "04_boxplots_day_type.png", dpi=120)
plt.close()

# --- 5.5 Travel time by route ---------------------------------------------
route_agg = (
    trip_summary.groupby("route_short_name")
    .agg(mean_time=("travel_time_min", "mean"), n_trips=("trip_id", "count"))
    .sort_values("mean_time", ascending=False)
    .head(20)
)
fig, ax = plt.subplots(figsize=(11, 7))
route_agg["mean_time"].plot.barh(ax=ax, color="#F18F01")
ax.invert_yaxis()
ax.set_xlabel("Mean travel time (min)")
ax.set_ylabel("Route")
ax.set_title("Top 20 routes by mean travel time")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "05_top_routes_by_time.png", dpi=120)
plt.close()

print("  Saved 5 EDA figures to outputs/")


# =============================================================================
# 6. REGRESSION MODELLING
# =============================================================================
print("\n" + "=" * 70)
print("STAGE 6: REGRESSION MODELLING")
print("=" * 70)

# Final feature set (mixes GTFS + geographic + demographic = heterogeneous)
FEATURES = [
    "trip_distance_km",
    "num_stops",
    "start_hour",
    "is_peak",
    "is_weekend_only",
    "mean_dist_from_cbd_km",
    "max_dist_from_cbd_km",
    "mean_sa2_density",
]
TARGET = "travel_time_min"

model_df = trip_summary[FEATURES + [TARGET]].dropna().copy()
model_df["is_weekend_only"] = model_df["is_weekend_only"].astype(int)

X = model_df[FEATURES].values
y = model_df[TARGET].values

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=RANDOM_STATE
)
print(f"  Train: {len(X_train):,}  |  Test: {len(X_test):,}")
print(f"  Features: {FEATURES}")

models = {
    "Linear Regression": LinearRegression(),
    "Decision Tree": DecisionTreeRegressor(max_depth=8, random_state=RANDOM_STATE),
    "Random Forest": RandomForestRegressor(
        n_estimators=200, max_depth=12, random_state=RANDOM_STATE, n_jobs=-1
    ),
}

# --- 6.1 Fit each model + hold-out evaluation ------------------------------
holdout_results = []
predictions = {}
for name, model in models.items():
    model.fit(X_train, y_train)
    y_hat = model.predict(X_test)
    predictions[name] = y_hat
    holdout_results.append(
        dict(
            Model=name,
            MAE=mean_absolute_error(y_test, y_hat),
            RMSE=np.sqrt(mean_squared_error(y_test, y_hat)),
            R2=r2_score(y_test, y_hat),
        )
    )
holdout_df = pd.DataFrame(holdout_results)
holdout_df.to_csv(OUTPUT_DIR / "holdout_results.csv", index=False)
print("\n  Hold-out performance:")
print(holdout_df.round(3).to_string(index=False))


# =============================================================================
# 7. CROSS-VALIDATION + STATISTICAL TESTS
# =============================================================================
print("\n" + "=" * 70)
print("STAGE 7: CROSS-VALIDATION + STATISTICAL TESTS")
print("=" * 70)

cv = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
cv_rmse = {}
for name, model in models.items():
    neg_mse = cross_val_score(
        model, X, y, cv=cv, scoring="neg_mean_squared_error", n_jobs=-1
    )
    cv_rmse[name] = np.sqrt(-neg_mse)
    print(f"  {name:20s} CV RMSE = {cv_rmse[name].mean():.3f} ± {cv_rmse[name].std():.3f}")

cv_df = pd.DataFrame(cv_rmse)
cv_df.index = [f"fold_{i+1}" for i in range(len(cv_df))]
cv_df.to_csv(OUTPUT_DIR / "cv_rmse_per_fold.csv")

# --- 7.1 Paired t-tests on CV RMSE -----------------------------------------
# H0: mean RMSE of model A == mean RMSE of model B (paired across folds)
# Paired design is appropriate: same folds, same data, dependent samples.
print("\n  Paired t-tests (H0: equal mean CV-RMSE between models):")
model_names = list(models.keys())
ttest_rows = []
for i in range(len(model_names)):
    for j in range(i + 1, len(model_names)):
        a, b = model_names[i], model_names[j]
        t_stat, p_val = stats.ttest_rel(cv_rmse[a], cv_rmse[b])
        signif = "significant" if p_val < 0.05 else "not significant"
        ttest_rows.append(dict(
            Comparison=f"{a} vs {b}",
            Mean_RMSE_A=cv_rmse[a].mean(),
            Mean_RMSE_B=cv_rmse[b].mean(),
            t_statistic=t_stat,
            p_value=p_val,
            Result_at_alpha_0_05=signif,
        ))
        print(f"    {a:20s} vs {b:20s}  t={t_stat:+.3f}  p={p_val:.4f}  ({signif})")
ttest_df = pd.DataFrame(ttest_rows)
ttest_df.to_csv(OUTPUT_DIR / "paired_ttests.csv", index=False)

# --- 7.2 F-test / overall significance of Linear Regression ----------------
# This demonstrates a second relevant statistical test: is the LR model
# globally significant against a null (intercept-only) model?
lr_full = LinearRegression().fit(X_train, y_train)
ss_res = np.sum((y_train - lr_full.predict(X_train)) ** 2)
ss_tot = np.sum((y_train - y_train.mean()) ** 2)
n, p = X_train.shape[0], X_train.shape[1]
r2_full = 1 - ss_res / ss_tot
F = (r2_full / p) / ((1 - r2_full) / (n - p - 1))
p_F = 1 - stats.f.cdf(F, p, n - p - 1)
print(f"\n  LR global F-test: F({p}, {n - p - 1}) = {F:.2f}, p = {p_F:.4e}")


# =============================================================================
# 8. RESIDUAL DIAGNOSTICS (Linear Regression assumption checks)
# =============================================================================
print("\n" + "=" * 70)
print("STAGE 8: RESIDUAL DIAGNOSTICS")
print("=" * 70)

y_pred_lr = models["Linear Regression"].predict(X_test)
residuals = y_test - y_pred_lr

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
axes[0].scatter(y_pred_lr, residuals, alpha=0.5, s=14)
axes[0].axhline(0, color="red", ls="--")
axes[0].set_xlabel("Predicted travel time")
axes[0].set_ylabel("Residual")
axes[0].set_title("Residuals vs fitted")
stats.probplot(residuals, dist="norm", plot=axes[1])
axes[1].set_title("Q-Q plot of residuals")
axes[2].hist(residuals, bins=40, color="#2E86AB", edgecolor="white")
axes[2].set_xlabel("Residual")
axes[2].set_ylabel("Frequency")
axes[2].set_title("Residual distribution")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "06_residual_diagnostics.png", dpi=120)
plt.close()

# Shapiro-Wilk test for normality on a random subsample (full set too large)
sample = np.random.RandomState(RANDOM_STATE).choice(residuals, size=min(500, len(residuals)), replace=False)
sw_stat, sw_p = stats.shapiro(sample)
print(f"  Shapiro-Wilk on residuals (n=500): W={sw_stat:.4f}, p={sw_p:.4e}")
print(f"  {'Residuals appear NON-normal' if sw_p < 0.05 else 'Residuals appear normal'}")


# =============================================================================
# 9. ACTUAL vs PREDICTED PLOTS (all 3 models)
# =============================================================================
print("\n" + "=" * 70)
print("STAGE 9: PREDICTION PLOTS")
print("=" * 70)

fig, axes = plt.subplots(1, 3, figsize=(17, 5))
for ax, (name, y_hat) in zip(axes, predictions.items()):
    ax.scatter(y_test, y_hat, alpha=0.5, s=14)
    lo, hi = min(y_test.min(), y_hat.min()), max(y_test.max(), y_hat.max())
    ax.plot([lo, hi], [lo, hi], "r--", lw=1.5, label="perfect prediction")
    ax.set_xlabel("Actual travel time (min)")
    ax.set_ylabel("Predicted travel time (min)")
    ax.set_title(f"{name}")
    ax.legend()
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "07_actual_vs_predicted.png", dpi=120)
plt.close()

# --- Feature importances for tree-based models ----------------------------
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, (name, model) in zip(axes, [("Decision Tree", models["Decision Tree"]),
                                     ("Random Forest", models["Random Forest"])]):
    imp = pd.Series(model.feature_importances_, index=FEATURES).sort_values()
    imp.plot.barh(ax=ax, color="#A23B72")
    ax.set_title(f"Feature importance - {name}")
    ax.set_xlabel("Importance")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "08_feature_importance.png", dpi=120)
plt.close()

# --- Linear regression coefficients ----------------------------------------
lr = models["Linear Regression"]
coef_df = pd.DataFrame({
    "feature": FEATURES,
    "coefficient": lr.coef_,
})
coef_df.to_csv(OUTPUT_DIR / "lr_coefficients.csv", index=False)
print("\n  Linear Regression coefficients:")
print(coef_df.round(4).to_string(index=False))
print(f"  Intercept: {lr.intercept_:.4f}")


# =============================================================================
# 10. SUMMARY
# =============================================================================
print("\n" + "=" * 70)
print("PIPELINE COMPLETE")
print("=" * 70)
print(f"  All outputs saved to: {OUTPUT_DIR}")
print("  CSVs:")
for f in sorted(OUTPUT_DIR.glob("*.csv")):
    print(f"    - {f.name}")
print("  Figures:")
for f in sorted(OUTPUT_DIR.glob("*.png")):
    print(f"    - {f.name}")
