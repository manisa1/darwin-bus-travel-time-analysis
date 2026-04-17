## Darwin Bus Travel Time Prediction
## Overview

This project aims to predict bus travel times in Darwin, Australia using machine learning techniques. By analysing public transport data, the project identifies key factors influencing travel time and evaluates different models for prediction accuracy.

The focus is on estimating total travel time per trip, using route and schedule characteristics derived from GTFS data.

## Problem Definition

The objective of this project is to predict the total travel time of a bus trip, calculated as the time difference between the first and last stop of each trip.

The prediction is based on features such as:

Trip distance
Number of stops
Time of day

This helps understand how route design and scheduling affect service efficiency.

## Dataset

The analysis uses data in GTFS (General Transit Feed Specification) format, a standard used for public transport systems.

**Key files used:

stop_times.txt — arrival and departure times for each stop
trips.txt — trip-level information
stops.txt — stop locations
routes.txt — route details

## Data Preprocessing

Several preprocessing steps were applied to prepare the data:

Converted time values from HH:MM:SS format into minutes for numerical analysis
Removed missing or inconsistent records
Filtered extreme values (outliers) to improve model stability
Aggregated stop-level data into trip-level summaries

These steps ensured that the dataset was clean and suitable for machine learning models.

## Feature Engineering

The following features were created to represent each trip:

Trip distance — derived from cumulative distance (shape_dist_traveled)
Number of stops — calculated from stop sequence count
Start time — extracted from the first departure time of each trip

These features were selected because they directly influence travel time and reflect route characteristics.

## Models

Two regression models were implemented:

Linear Regression
Used as a baseline model
Assumes a linear relationship between variables
Decision Tree Regression
Captures non-linear relationships
Able to model interactions between features

## Model Evaluation

The models were evaluated using the following metrics:

MAE (Mean Absolute Error) — average prediction error
RMSE (Root Mean Squared Error) — penalises large errors
R² (R-squared) — proportion of variance explained
Model	MAE	RMSE	R²
Linear Regression	3.24	4.13	0.91
Decision Tree	1.86	2.53	0.97

The Decision Tree model achieved lower error and higher explanatory power.

## Visualisations

The analysis includes several visualisations:

Travel Time vs Distance — shows strong positive relationship
Predicted vs Actual (Linear Regression)
Predicted vs Actual (Decision Tree)

These visualisations help evaluate model performance and understand patterns in the data.

## Results & Discussion

The results show that:

Distance is the strongest predictor of travel time
Number of stops increases travel time, due to frequent stopping
The Decision Tree model outperforms Linear Regression, indicating that relationships between variables are not purely linear

The Decision Tree model achieved an average error of approximately 1.86 minutes, demonstrating good predictive performance.

## Limitations

This project has several limitations:

The dataset is based on scheduled timetable data, not real-time data
It does not account for traffic conditions, delays, or weather
No passenger demand data is available, limiting evaluation of service usefulness
Decision Tree models may be prone to overfitting with limited features

As a result, predictions represent ideal conditions rather than real-world variability.

## Future Improvements

Future work could improve the model by:

Incorporating real-time data (delays, traffic conditions)
Adding passenger demand information
Using more advanced models such as Random Forest or Gradient Boosting
Including additional features such as route type or service frequency
🧾 Conclusion

This project demonstrates that machine learning models can effectively predict bus travel time using route and schedule data.

The Decision Tree model provided the best performance due to its ability to capture non-linear relationships. These findings highlight how data-driven approaches can support transport planning and improve service efficiency.
