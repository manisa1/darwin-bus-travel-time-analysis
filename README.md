# Darwin Bus Travel Time Prediction

## Overview
This project predicts bus travel times in Darwin, Australia using public transport data. Machine learning models, including Linear Regression and Decision Tree Regression, are used to estimate travel time based on key factors such as trip distance, number of stops, and start time.

## Dataset
The analysis uses bus schedule data in GTFS (General Transit Feed Specification) format, a standard used by transport agencies to share public transit information.

Key files used:
- stop_times.txt
- trips.txt
- stops.txt
- routes.txt

## Methods
Two models were developed:
- Linear Regression (baseline model)
- Decision Tree Regression (captures non-linear patterns)

## Features
- Trip distance  
- Number of stops  
- Start time (hour of day)

## Results
The Decision Tree model outperformed Linear Regression:

| Model | MAE | RMSE | R² |
|------|------|------|------|
| Linear Regression | 3.24 | 4.13 | 0.91 |
| Decision Tree | 1.86 | 2.53 | 0.97 |

This indicates that the Decision Tree model provides more accurate predictions and better captures relationships in the data.

## Visualisations
The analysis includes:
- Travel Time vs Distance
- Predicted vs Actual (Linear Regression)
- Predicted vs Actual (Decision Tree)

## Limitations
The dataset is based on scheduled timetable data and does not account for real-world factors such as traffic or delays. As a result, model performance may differ in real-world conditions.

## Conclusion
Decision Tree Regression is more effective for predicting bus travel times in this dataset due to its ability to model non-linear relationships.