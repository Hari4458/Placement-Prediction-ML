import math

from config import FEATURE_CONFIG


def sigmoid(value):
    if value < -40:
        return 0.0
    if value > 40:
        return 1.0
    return 1.0 / (1.0 + math.exp(-value))


def compute_scaling_stats(features):
    feature_count = len(features[0])
    means = [0.0] * feature_count
    stds = [0.0] * feature_count

    for row in features:
        for index, value in enumerate(row):
            means[index] += value

    sample_count = len(features)
    means = [value / sample_count for value in means]

    for row in features:
        for index, value in enumerate(row):
            diff = value - means[index]
            stds[index] += diff * diff

    stds = [math.sqrt(value / sample_count) or 1.0 for value in stds]
    return {"means": means, "stds": stds}


def scale_matrix(features, scaling_stats):
    scaled = []
    for row in features:
        scaled.append(
            [
                (value - scaling_stats["means"][index]) / scaling_stats["stds"][index]
                for index, value in enumerate(row)
            ]
        )
    return scaled


def train_logistic_regression(
    features, labels, learning_rate=0.08, epochs=1600, regularization=0.0008
):
    weights = [0.0] * len(features[0])
    bias = 0.0
    sample_count = len(features)

    for _ in range(epochs):
        gradient = [0.0] * len(weights)
        bias_gradient = 0.0

        for row, actual in zip(features, labels):
            linear = bias + sum(weight * value for weight, value in zip(weights, row))
            prediction = sigmoid(linear)
            error = prediction - actual

            for index, value in enumerate(row):
                gradient[index] += error * value
            bias_gradient += error

        for index in range(len(weights)):
            average_gradient = (
                gradient[index] / sample_count + regularization * weights[index]
            )
            weights[index] -= learning_rate * average_gradient

        bias -= learning_rate * (bias_gradient / sample_count)

    return {"weights": weights, "bias": bias}


def predict_probability(scaled_row, model):
    linear = model["bias"] + sum(
        weight * value for weight, value in zip(model["weights"], scaled_row)
    )
    return sigmoid(linear)


def evaluate_model(features, labels, model):
    correct = 0
    true_positive = 0
    true_negative = 0
    false_positive = 0
    false_negative = 0

    for row, actual in zip(features, labels):
        if model.get("type") == "random_forest":
            probability = predict_with_forest(row, model)
        elif model.get("type") == "svm":
            probability = predict_with_svm(row, model)
        else:
            probability = predict_probability(row, model)
        
        prediction = 1 if probability >= 0.5 else 0

        if prediction == actual:
            correct += 1
        if prediction == 1 and actual == 1:
            true_positive += 1
        elif prediction == 0 and actual == 0:
            true_negative += 1
        elif prediction == 1 and actual == 0:
            false_positive += 1
        else:
            false_negative += 1

    accuracy = correct / len(features)
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    f1_score = (2 * precision * recall) / max(precision + recall, 1e-12)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1Score": f1_score,
        "confusionMatrix": {
            "truePositive": true_positive,
            "trueNegative": true_negative,
            "falsePositive": false_positive,
            "falseNegative": false_negative,
        },
    }


def build_feature_impact(model):
    max_weight = max(abs(weight) for weight in model["weights"]) or 1.0
    feature_impact = []
    for index, feature in enumerate(FEATURE_CONFIG):
        weight = model["weights"][index]
        feature_impact.append(
            {
                "key": feature["key"],
                "label": feature["label"],
                "weight": weight,
                "impact": abs(weight) / max_weight,
            }
        )
    feature_impact.sort(key=lambda item: item["impact"], reverse=True)
    return feature_impact


def calculate_confidence_interval(predictions, true_labels, confidence_level=0.95):
    """Calculate confidence intervals for model predictions"""
    correct = sum(1 for p, t in zip(predictions, true_labels) if (p >= 0.5) == (t == 1))
    n = len(predictions)
    accuracy = correct / n if n > 0 else 0
    
    # Standard error for binomial proportion
    se = math.sqrt((accuracy * (1 - accuracy)) / n) if n > 0 else 0
    
    # Z-score for 95% confidence
    z_score = 1.96 if confidence_level == 0.95 else 1.645
    margin_of_error = z_score * se
    
    return {
        "accuracy": accuracy,
        "lower_bound": max(0, accuracy - margin_of_error),
        "upper_bound": min(1, accuracy + margin_of_error),
        "margin_of_error": margin_of_error,
    }


def train_random_forest(features, labels, num_trees=3):
    """Simple Random Forest implementation"""
    import random
    
    forest = []
    
    for _ in range(num_trees):
        sample_indices = [random.randint(0, len(features) - 1) for _ in range(len(features))]
        sampled_features = [features[i] for i in sample_indices]
        sampled_labels = [labels[i] for i in sample_indices]
        
        if sampled_features and sampled_labels:
            tree = train_logistic_regression(sampled_features, sampled_labels, epochs=400)
            forest.append(tree)
    
    return {"forest": forest, "type": "random_forest"}


def predict_with_forest(scaled_row, forest_model):
    """Predict using Random Forest"""
    if not forest_model.get("forest"):
        return 0.5
    
    predictions = [predict_probability(scaled_row, tree) for tree in forest_model["forest"]]
    return sum(predictions) / len(predictions) if predictions else 0.5


def train_svm(features, labels, learning_rate=0.05, epochs=300, c_param=1.0):
    """SVM with hinge-loss using batch sub-gradient descent."""
    num_features = len(features[0])
    num_samples = len(features)
    weights = [0.0] * num_features
    bias = 0.0

    # Convert labels: 0 -> -1, 1 -> +1
    y_svm = [1 if label == 1 else -1 for label in labels]

    for epoch in range(epochs):
        # Decaying learning rate for stable convergence
        lr = learning_rate / (1 + 0.01 * epoch)

        # Accumulate gradients over the full batch
        grad_w = [0.0] * num_features
        grad_b = 0.0

        for row, y in zip(features, y_svm):
            margin = y * (bias + sum(w * x for w, x in zip(weights, row)))

            if margin < 1:
                # Hinge-loss gradient: push weights toward correct side
                for i in range(num_features):
                    grad_w[i] += -y * row[i]
                grad_b += -y

        # Update: regularization (w) + C * average hinge gradient
        for i in range(num_features):
            weights[i] -= lr * (weights[i] + c_param * grad_w[i] / num_samples)
        bias -= lr * (c_param * grad_b / num_samples)

    return {"weights": weights, "bias": bias, "type": "svm"}


def predict_with_svm(scaled_row, svm_model):
    """Predict using SVM"""
    decision = svm_model["bias"] + sum(w * x for w, x in zip(svm_model["weights"], scaled_row))
    return sigmoid(decision)


def analyze_skill_gaps(student_features, placed_students_matrix):
    """Analyze skill gaps for a student"""
    if not placed_students_matrix:
        return []
    
    placed_means = [0.0] * len(student_features)
    for row in placed_students_matrix:
        for i, val in enumerate(row):
            placed_means[i] += val
    
    for i in range(len(placed_means)):
        placed_means[i] /= len(placed_students_matrix)
    
    gaps = []
    for i, feature in enumerate(FEATURE_CONFIG):
        student_val = student_features[i]
        avg_placed = placed_means[i]
        gap = avg_placed - student_val
        
        gaps.append({
            "key": feature["key"],
            "label": feature["label"],
            "studentValue": round(student_val, 2),
            "averagePlaced": round(avg_placed, 2),
            "gap": round(gap, 2),
            "needsImprovement": gap > 0.05,
        })
    
    gaps.sort(key=lambda x: abs(x["gap"]), reverse=True)
    return gaps
