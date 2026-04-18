# Darwin Bus Network — Travel Time Prediction

**PRT564 Data Analytics & Visualisation | Group 10 | Charles Darwin University**

---

## Research Question

> *To what extent can bus travel time be predicted based on route characteristics such as distance travelled, number of stops, and time of day?*

---

## Overview

This project implements an end-to-end regression pipeline to predict bus trip travel times across the Darwin bus network. It integrates three heterogeneous data sources and evaluates three machine learning models using cross-validation and statistical tests.

---

## Data Sources

| Source | Description |
|---|---|
| **NT Government GTFS Feed** | Scheduled transit data: `stop_times.txt`, `trips.txt`, `stops.txt`, `routes.txt`, `calendar.txt` |
| **ABS Census 2021 (SA2)** | Population and population density for Greater Darwin suburbs (`darwin_sa2_population.csv`) |
| **Geographic Reference** | Darwin Interchange CBD coordinates used to compute Haversine distances per stop |

---

## Pipeline Stages (`pipeline.py`)

1. **Data Loading** — 6 source files loaded
2. **Preprocessing** — GTFS time parsing, numeric coercion, IQR outlier removal (1st–99th percentile)
3. **Feature Engineering** — peak-hour flags (AM 7–9, PM 16–18), weekday/weekend service type
4. **Heterogeneous Integration** — Haversine CBD distance + nearest-SA2 population density joined to each trip
5. **Exploratory Data Analysis** — 5 figures saved to `outputs/`
6. **Regression Modelling** — 3 models trained on 8 features (80/20 split)
7. **Cross-Validation & Statistical Tests** — 5-fold CV, paired t-tests, global F-test
8. **Residual Diagnostics** — Shapiro-Wilk normality test, Q-Q plot
9. **Prediction Plots** — Actual vs Predicted for all 3 models, feature importances
10. **Summary Output** — all CSVs and figures saved to `outputs/`

---

## Features Used

| Feature | Source |
|---|---|
| `trip_distance_km` | GTFS (`shape_dist_traveled`) |
| `num_stops` | GTFS (`stop_sequence`) |
| `start_hour` | GTFS (`departure_time`) |
| `is_peak` | Derived (AM/PM peak hours) |
| `is_weekend_only` | GTFS (`calendar.txt`) |
| `mean_dist_from_cbd_km` | Geographic (Haversine) |
| `max_dist_from_cbd_km` | Geographic (Haversine) |
| `mean_sa2_density` | ABS Census 2021 |

---

## Models & Results

| Model | MAE (min) | RMSE (min) | R² |
|---|---|---|---|
| Linear Regression | 3.40 | 4.31 | 0.847 |
| Decision Tree (depth=8) | 0.87 | 2.14 | 0.962 |
| **Random Forest (200 trees)** | **0.58** | **1.71** | **0.976** |

All pairwise differences are statistically significant (paired t-tests, p < 0.01).

---

## Statistical Tests

- **Paired t-tests** on 5-fold CV RMSE — all three model pairs significantly different
- **Global F-test** on Linear Regression — model is globally significant (p < 0.0001)
- **Shapiro-Wilk** on residuals — residuals are non-normal (p < 0.05); LR confidence intervals should be interpreted cautiously

---

## Output Files (`outputs/`)

| File | Description |
|---|---|
| `01_distributions.png` | Travel time & distance distributions |
| `02_correlation_heatmap.png` | Pearson correlation matrix |
| `03_scatter_distance_vs_time.png` | Distance vs time coloured by SA2 density |
| `04_boxplots_day_type.png` | Peak vs off-peak, weekday vs weekend |
| `05_top_routes_by_time.png` | Top 20 routes by mean travel time |
| `06_residual_diagnostics.png` | Residuals vs fitted, Q-Q plot, histogram |
| `07_actual_vs_predicted.png` | All 3 models side by side |
| `08_feature_importance.png` | Decision Tree & Random Forest importances |
| `holdout_results.csv` | MAE, RMSE, R² for all models |
| `cv_rmse_per_fold.csv` | CV RMSE per fold |
| `paired_ttests.csv` | Paired t-test results |
| `lr_coefficients.csv` | Linear Regression coefficients |
| `descriptive_statistics.csv` | Dataset summary statistics |

---

## How to Run

```bash
# Install dependencies
pip install pandas numpy scikit-learn matplotlib seaborn scipy

# Run the main pipeline
python pipeline.py

# Verify data integrity
python verify_data_pipeline.py

# Rebuild the presentation
python build_presentation.py
```

---

## Key Findings

- **Trip distance** is the strongest predictor (~1.2 min added per extra km)
- **Number of stops** adds ~0.32 min per stop
- **Peak hour and weekend** effects are minimal in Darwin's scheduled network
- **Random Forest** achieves R² = 0.976, predicting travel time to within 1.7 minutes on average

---

## Limitations

- Based on **scheduled** timetable data — real delays and traffic not captured
- SA2 demographic join uses **nearest centroid** (approximate spatial match)
- No passenger demand data available
- GTFS snapshot may not reflect seasonal timetable changes

---

## Team

| Name | Student ID | Role |
|---|---|---|
| Aashish Sharma | S396419 | Visualisation Lead |
| Manisha Paudel | S380490 | Data Acquisition & Preparation Lead |
| Rahul Sharma | S388446 | Reporting & Integration Lead |
| Roshan Neupane | S395086 | Data Analysis Lead |

**Dataset:** [NT Government GTFS Feed](https://data.nt.gov.au/dataset/bus-timetable-data-and-geographic-information-darwin) | [ABS 2021 Census](https://www.abs.gov.au)
