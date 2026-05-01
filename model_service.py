from datetime import datetime, timezone

from config import FEATURE_CONFIG
from data_loader import (
    build_matrix,
    load_dataset,
    split_dataset,
    summarize_dataset,
    to_feature_value,
)
from ml_model import (
    analyze_skill_gaps,
    build_feature_impact,
    compute_scaling_stats,
    evaluate_model,
    predict_probability,
    predict_with_forest,
    predict_with_svm,
    scale_matrix,
    train_logistic_regression,
    train_random_forest,
    train_svm,
)


def format_percent(value):
    return f"{value * 100:.2f}%"


def create_model_bundle():
    rows = load_dataset()
    train_rows, test_rows = split_dataset(rows)
    train_x, train_y = build_matrix(train_rows)
    test_x, test_y = build_matrix(test_rows)

    scaling_stats = compute_scaling_stats(train_x)
    scaled_train_x = scale_matrix(train_x, scaling_stats)
    scaled_test_x = scale_matrix(test_x, scaling_stats)
    
    # Train Logistic Regression with fewer epochs for faster startup
    lr_model = train_logistic_regression(scaled_train_x, train_y, epochs=200, learning_rate=0.1)
    lr_metrics = evaluate_model(scaled_test_x, test_y, lr_model)

    # Train Random Forest and SVM for a real ensemble output
    rf_model = train_random_forest(scaled_train_x, train_y, num_trees=5)
    rf_metrics = evaluate_model(scaled_test_x, test_y, rf_model)

    svm_model = train_svm(scaled_train_x, train_y)
    svm_metrics = evaluate_model(scaled_test_x, test_y, svm_model)

    # Get placed students for skill gap analysis
    placed_rows = [row for row in train_rows if row["PlacementStatus"] == "Placed"]
    placed_x, _ = build_matrix(placed_rows)
    placed_scaled_x = scale_matrix(placed_x, scaling_stats)
    
    return {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "models": {
            "logisticRegression": lr_model,
            "randomForest": rf_model,
            "svm": svm_model,
        },
        "scalingStats": scaling_stats,
        "metrics": {
            "logisticRegression": lr_metrics,
            "randomForest": rf_metrics,
            "svm": svm_metrics,
        },
        "datasetSummary": summarize_dataset(rows),
        "featureImpact": build_feature_impact(lr_model),
        "placedStudentsMatrix": placed_scaled_x,
        "trainingInfo": {
            "algorithms": ["Logistic Regression", "Random Forest", "SVM"],
            "trainSize": len(train_rows),
            "testSize": len(test_rows),
            "featureCount": len(FEATURE_CONFIG),
        },
    }


MODEL_BUNDLE = create_model_bundle()


def predict_placement(payload):
    scaled_row = []
    for index, feature in enumerate(FEATURE_CONFIG):
        value = payload.get(feature["key"])
        if value in (None, ""):
            raise ValueError(f"Missing field: {feature['label']}")
        numeric = to_feature_value(feature["type"], value)
        scaled_value = (
            numeric - MODEL_BUNDLE["scalingStats"]["means"][index]
        ) / MODEL_BUNDLE["scalingStats"]["stds"][index]
        scaled_row.append(scaled_value)

    # Get predictions from all models
    lr_prob = predict_probability(scaled_row, MODEL_BUNDLE["models"]["logisticRegression"])
    rf_prob = predict_with_forest(scaled_row, MODEL_BUNDLE["models"]["randomForest"])
    svm_prob = predict_with_svm(scaled_row, MODEL_BUNDLE["models"]["svm"])
    
    # Average probability
    avg_probability = (lr_prob + rf_prob + svm_prob) / 3
    confidence = abs(avg_probability - 0.5) * 2
    
    return {
        "probability": avg_probability,
        "prediction": "Placed" if avg_probability >= 0.5 else "NotPlaced",
        "confidence": confidence,
        "probabilityLabel": format_percent(avg_probability),
        "confidenceLabel": format_percent(confidence),
        "modelPredictions": {
            "logisticRegression": {
                "probability": lr_prob,
                "prediction": "Placed" if lr_prob >= 0.5 else "NotPlaced",
            },
            "randomForest": {
                "probability": rf_prob,
                "prediction": "Placed" if rf_prob >= 0.5 else "NotPlaced",
            },
            "svm": {
                "probability": svm_prob,
                "prediction": "Placed" if svm_prob >= 0.5 else "NotPlaced",
            },
        },
    }


def get_skill_gaps(payload):
    """Get skill gap analysis for a student"""
    student_features = []
    for feature in FEATURE_CONFIG:
        value = payload.get(feature["key"])
        if value in (None, ""):
            raise ValueError(f"Missing field: {feature['label']}")
        numeric = to_feature_value(feature["type"], value)
        scaled_value = (
            numeric - MODEL_BUNDLE["scalingStats"]["means"][len(student_features)]
        ) / MODEL_BUNDLE["scalingStats"]["stds"][len(student_features)]
        student_features.append(scaled_value)
    
    gaps = analyze_skill_gaps(student_features, MODEL_BUNDLE["placedStudentsMatrix"])
    return {
        "skillGaps": gaps,
        "improvementAreas": [gap for gap in gaps if gap["needsImprovement"]],
    }


def build_overview_payload():
    dataset = dict(MODEL_BUNDLE["datasetSummary"])
    dataset["placementRateLabel"] = format_percent(dataset["placementRate"])

    metrics_data = {}
    for model_name, metrics in MODEL_BUNDLE["metrics"].items():
        metrics_data[model_name] = {
            "accuracy": metrics.get("accuracy", 0),
            "accuracyLabel": format_percent(metrics.get("accuracy", 0)),
            "precision": metrics.get("precision", 0),
            "precisionLabel": format_percent(metrics.get("precision", 0)),
            "recall": metrics.get("recall", 0),
            "recallLabel": format_percent(metrics.get("recall", 0)),
            "f1Score": metrics.get("f1Score", 0),
            "f1ScoreLabel": format_percent(metrics.get("f1Score", 0)),
            "confusionMatrix": metrics.get("confusionMatrix", {}),
        }

    return {
        "dataset": dataset,
        "trainingInfo": MODEL_BUNDLE["trainingInfo"],
        "metrics": metrics_data,
        "featureImpact": MODEL_BUNDLE["featureImpact"],
        "createdAt": MODEL_BUNDLE["createdAt"],
    }
