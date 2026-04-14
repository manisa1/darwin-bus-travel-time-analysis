import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# -----------------------------
# 1. LOAD DATA
# -----------------------------
stop_times = pd.read_csv("stop_times.txt")
trips = pd.read_csv("trips.txt")
stops = pd.read_csv("stops.txt")
routes = pd.read_csv("routes.txt")


# -----------------------------
# 2. PREPROCESSING
# -----------------------------
# Convert GTFS time strings into timedeltas
stop_times["arrival_td"] = pd.to_timedelta(stop_times["arrival_time"], errors="coerce")
stop_times["departure_td"] = pd.to_timedelta(stop_times["departure_time"], errors="coerce")

# Drop rows where time conversion failed
stop_times = stop_times.dropna(subset=["arrival_td", "departure_td"])

# Keep only rows with valid trip_id
stop_times = stop_times.dropna(subset=["trip_id"])

# Ensure stop_sequence and shape_dist_traveled are numeric
stop_times["stop_sequence"] = pd.to_numeric(stop_times["stop_sequence"], errors="coerce")
stop_times["shape_dist_traveled"] = pd.to_numeric(
    stop_times["shape_dist_traveled"], errors="coerce"
)

stop_times = stop_times.dropna(subset=["stop_sequence", "shape_dist_traveled"])


# -----------------------------
# 3. CREATE TRIP-LEVEL DATASET
# -----------------------------
trip_summary = stop_times.groupby("trip_id").agg(
    start_time=("departure_td", "min"),
    end_time=("arrival_td", "max"),
    num_stops=("stop_sequence", "max"),
    trip_distance=("shape_dist_traveled", "max")
).reset_index()

# Calculate trip travel time in minutes
trip_summary["travel_time_min"] = (
    trip_summary["end_time"] - trip_summary["start_time"]
).dt.total_seconds() / 60

# Remove invalid rows
trip_summary = trip_summary.dropna(
    subset=["travel_time_min", "trip_distance", "num_stops"]
)

# Merge with trips file to get route/service information
trip_summary = trip_summary.merge(trips, on="trip_id", how="left")

# Create time-of-day feature from trip start time
trip_summary["start_hour"] = trip_summary["start_time"].dt.total_seconds() / 3600

# Final model dataset
model_data = trip_summary[
    [
        "trip_id",
        "route_id",
        "service_id",
        "num_stops",
        "trip_distance",
        "start_hour",
        "travel_time_min",
    ]
].dropna()

print("Preview of model data:")
print(model_data.head())
print("\nShape of model data:")
print(model_data.shape)
print("\nDescriptive statistics:")
print(model_data.describe())


# -----------------------------
# 4. SET UP FEATURES AND TARGET
# -----------------------------
X = model_data[["trip_distance", "num_stops", "start_hour"]]
y = model_data["travel_time_min"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)


# -----------------------------
# 5. LINEAR REGRESSION
# -----------------------------
linear_model = LinearRegression()
linear_model.fit(X_train, y_train)

y_pred = linear_model.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("\nLinear Regression Results")
print("MAE:", mae)
print("RMSE:", rmse)
print("R2:", r2)

print("\nLinear Regression Coefficients:")
for feature, coef in zip(X.columns, linear_model.coef_):
    print(f"{feature}: {coef:.4f}")
print("Intercept:", round(linear_model.intercept_, 4))


# -----------------------------
# 6. DECISION TREE REGRESSION
# -----------------------------
tree_model = DecisionTreeRegressor(max_depth=5, random_state=42)
tree_model.fit(X_train, y_train)

y_pred_tree = tree_model.predict(X_test)

mae_tree = mean_absolute_error(y_test, y_pred_tree)
rmse_tree = np.sqrt(mean_squared_error(y_test, y_pred_tree))
r2_tree = r2_score(y_test, y_pred_tree)

print("\nDecision Tree Results")
print("MAE:", mae_tree)
print("RMSE:", rmse_tree)
print("R2:", r2_tree)


# -----------------------------
# 7. MODEL COMPARISON
# -----------------------------
comparison = pd.DataFrame({
    "Model": ["Linear Regression", "Decision Tree"],
    "MAE": [mae, mae_tree],
    "RMSE": [rmse, rmse_tree],
    "R2": [r2, r2_tree]
})

print("\nModel Comparison")
print(comparison)


# -----------------------------
# 8. VISUALISATIONS
# -----------------------------
# Graph 1: Travel Time vs Distance
plt.figure(figsize=(8, 5))
plt.scatter(model_data["trip_distance"], model_data["travel_time_min"], alpha=0.7)
plt.xlabel("Trip Distance")
plt.ylabel("Travel Time (minutes)")
plt.title("Travel Time vs Distance")
plt.grid(True)
plt.show()

# Graph 2: Actual vs Predicted (Linear Regression)
plt.figure(figsize=(8, 5))
plt.scatter(y_test, y_pred, alpha=0.7)
plt.xlabel("Actual Travel Time (minutes)")
plt.ylabel("Predicted Travel Time (minutes)")
plt.title("Actual vs Predicted Travel Time - Linear Regression")
plt.grid(True)
plt.show()

# Graph 3: Actual vs Predicted (Decision Tree)
plt.figure(figsize=(8, 5))
plt.scatter(y_test, y_pred_tree, alpha=0.7)
plt.xlabel("Actual Travel Time (minutes)")
plt.ylabel("Predicted Travel Time (minutes)")
plt.title("Actual vs Predicted Travel Time - Decision Tree")
plt.grid(True)
plt.show()

# -------- FINAL GRAPH: Predicted vs Actual --------

plt.figure(figsize=(8,5))
plt.scatter(y_test, y_pred, alpha=0.7)

plt.xlabel("Actual Travel Time (minutes)")
plt.ylabel("Predicted Travel Time (minutes)")
plt.title("Predicted vs Actual Travel Time (Linear Regression)")

# Add perfect prediction line
plt.plot(
    [y_test.min(), y_test.max()],
    [y_test.min(), y_test.max()],
    color='red',
    linestyle='--'
)

plt.grid(True)
plt.show()