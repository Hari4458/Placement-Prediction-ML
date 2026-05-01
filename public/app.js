let predictorBundle = null;
let lastPredictionResult = null;
let lastPredictionPayload = null;
let overviewData = null;

async function loadBundle() {
  const response = await fetch("./data/model-bundle.json");
  if (!response.ok) {
    throw new Error("Unable to load model bundle");
  }
  return response.json();
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function sigmoid(value) {
  if (value < -40) return 0;
  if (value > 40) return 1;
  return 1 / (1 + Math.exp(-value));
}

function toFeatureValue(featureType, rawValue) {
  if (featureType === "binary") {
    return String(rawValue).trim().toLowerCase() === "yes" ? 1 : 0;
  }
  return Number(rawValue);
}

function formatPercent(value) {
  return `${(value * 100).toFixed(2)}%`;
}

function setOverview(data) {
  const { dataset, trainingInfo, metrics, featureImpact, createdAt } = data;
  const lrMetrics = metrics.logisticRegression || metrics;

  setText("hero-accuracy", lrMetrics.accuracyLabel || "--");
  setText("hero-dataset", dataset.totalStudents.toLocaleString());
  setText("hero-rate", dataset.placementRateLabel);
  setText("metric-accuracy", lrMetrics.accuracyLabel || "--");
  setText("metric-precision", lrMetrics.precisionLabel || "--");
  setText("metric-recall", lrMetrics.recallLabel || "--");
  setText("metric-f1", lrMetrics.f1ScoreLabel || "--");
  setText("total-students", dataset.totalStudents.toLocaleString());
  setText("placed-count", dataset.placedCount.toLocaleString());
  setText("not-placed-count", dataset.notPlacedCount.toLocaleString());
  setText("split-info", `${trainingInfo.trainSize} / ${trainingInfo.testSize}`);
  setText("tp", (lrMetrics.confusionMatrix?.truePositive || 0).toLocaleString());
  setText("fp", (lrMetrics.confusionMatrix?.falsePositive || 0).toLocaleString());
  setText("tn", (lrMetrics.confusionMatrix?.trueNegative || 0).toLocaleString());
  setText("fn", (lrMetrics.confusionMatrix?.falseNegative || 0).toLocaleString());
  setText(
    "trained-at",
    `Trained ${new Date(createdAt).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric"
    })}`
  );

  const featureContainer = document.getElementById("feature-impact");
  featureContainer.innerHTML = "";
  featureImpact.forEach((feature) => {
    const wrapper = document.createElement("div");
    wrapper.className = "feature-row";
    wrapper.innerHTML = `
      <div class="feature-meta">
        <strong>${feature.label}</strong>
        <span>${(feature.impact * 100).toFixed(0)}%</span>
      </div>
      <div class="feature-bar">
        <span style="width:${(feature.impact * 100).toFixed(1)}%"></span>
      </div>
    `;
    featureContainer.appendChild(wrapper);
  });
}

function getSkillGaps(payload) {
  if (!predictorBundle || !predictorBundle.placedStudentsMatrix) return null;

  const studentFeatures = predictorBundle.featureConfig.map((feature, index) => {
    const value = toFeatureValue(feature.type, payload[feature.key]);
    return (value - predictorBundle.means[index]) / predictorBundle.stds[index];
  });

  const matrix = predictorBundle.placedStudentsMatrix;
  const numFeatures = studentFeatures.length;
  const placedMeans = new Array(numFeatures).fill(0);

  matrix.forEach((row) => {
    row.forEach((val, i) => {
      placedMeans[i] += val;
    });
  });

  placedMeans.forEach((_, i) => {
    placedMeans[i] /= matrix.length;
  });

  const gaps = predictorBundle.featureConfig.map((feature, i) => {
    const studentVal = studentFeatures[i];
    const avgPlaced = placedMeans[i];
    const gap = avgPlaced - studentVal;

    return {
      key: feature.key,
      label: feature.label,
      studentValue: Number(
        toFeatureValue(feature.type, payload[feature.key]).toFixed(2)
      ),
      averagePlaced: Number(
        (
          avgPlaced * predictorBundle.stds[i] +
          predictorBundle.means[i]
        ).toFixed(2)
      ),
      gap: Number(gap.toFixed(2)),
      needsImprovement: gap > 0.05,
    };
  });

  return {
    skillGaps: gaps.sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap)),
    improvementAreas: gaps.filter((g) => g.needsImprovement),
  };
}

async function predictPlacement(payload) {
  // Use client-side prediction if bundle is loaded
  if (predictorBundle) {
    const scaledRow = predictorBundle.featureConfig.map((feature, index) => {
      const value = toFeatureValue(feature.type, payload[feature.key]);
      return (
        (value - predictorBundle.means[index]) / predictorBundle.stds[index]
      );
    });

    const linear =
      predictorBundle.bias +
      scaledRow.reduce(
        (sum, val, i) => sum + val * predictorBundle.weights[i],
        0
      );
    const probability = sigmoid(linear);
    const confidence = Math.abs(probability - 0.5) * 2;

    return {
      probability,
      prediction: probability >= 0.5 ? "Placed" : "NotPlaced",
      confidence,
      probabilityLabel: formatPercent(probability),
      confidenceLabel: formatPercent(confidence),
      skillGaps: getSkillGaps(payload),
    };
  }

  // Fallback to API (for local dev or if bundle fails)
  const response = await fetch("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(errorPayload.error || "Unable to generate prediction");
  }

  return response.json();
}

async function handlePrediction(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());

  try {
    const result = await predictPlacement(payload);
    lastPredictionResult = result;
    lastPredictionPayload = payload;
    
    setText("prediction-label", result.prediction);
    setText("probability-value", result.probabilityLabel);
    setText("confidence-value", result.confidenceLabel);
    document.getElementById("probability-bar").style.width = result.probabilityLabel;

    document.getElementById("prediction-copy").textContent =
      result.prediction === "Placed"
        ? "The model sees this profile as likely to get placed based on academic strength, training, and overall readiness."
        : "The model suggests this profile is currently at risk. Improving aptitude score, training exposure, projects, and academic consistency can help.";

    const gapContainer = document.getElementById("skill-gaps-list");
    if (gapContainer && result.skillGaps) {
      gapContainer.innerHTML = "";
      const improvements = result.skillGaps.improvementAreas;
      if (improvements.length > 0) {
        improvements.slice(0, 3).forEach((gap) => {
          const div = document.createElement("div");
          div.className = "gap-item";
          div.style.padding = "10px";
          div.style.background = "var(--bg-secondary)";
          div.style.borderRadius = "8px";
          div.style.marginBottom = "8px";
          div.innerHTML = `
            <strong style="display:block;margin-bottom:4px;font-size:0.9rem;">${gap.label}</strong>
            <p style="margin:0;font-size:0.8rem;color:var(--muted);">Target: ${gap.averagePlaced} | Current: ${gap.studentValue}</p>
          `;
          gapContainer.appendChild(div);
        });
      } else {
        gapContainer.innerHTML = "<p class='success-text'>No major gaps identified!</p>";
      }
    }
  } catch (error) {
    document.getElementById("prediction-copy").textContent = error.message;
  }
}

function downloadReport() {
  if (!lastPredictionResult || !lastPredictionPayload) {
    alert("Please generate a prediction first.");
    return;
  }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.width;

  // Header
  doc.setFillColor(15, 23, 42);
  doc.rect(0, 0, pageWidth, 40, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(22);
  doc.text("PlacementVision AI", 20, 25);
  doc.setFontSize(10);
  doc.text("Student Placement Prediction Report", pageWidth - 20, 25, { align: "right" });

  // Body
  doc.setTextColor(15, 23, 42);
  doc.setFontSize(18);
  doc.text("Prediction Result", 20, 60);

  // Summary Table
  doc.autoTable({
    startY: 70,
    head: [["Metric", "Value"]],
    body: [
      ["Prediction", lastPredictionResult.prediction],
      ["Probability", lastPredictionResult.probabilityLabel],
      ["Confidence", lastPredictionResult.confidenceLabel],
    ],
    theme: "striped",
    headStyles: { fillColor: [16, 185, 129] },
  });

  // Student Profile Table
  doc.setFontSize(16);
  doc.text("Student Profile", 20, doc.lastAutoTable.finalY + 20);

  const profileBody = Object.entries(lastPredictionPayload).map(([key, value]) => [
    key.replace(/([A-Z])/g, " $1").trim(),
    value,
  ]);

  doc.autoTable({
    startY: doc.lastAutoTable.finalY + 30,
    head: [["Field", "Value"]],
    body: profileBody,
    theme: "grid",
    headStyles: { fillColor: [29, 78, 216] },
  });

  // Model Performance
  if (overviewData) {
    doc.setFontSize(16);
    doc.text("Model Performance (Overall)", 20, doc.lastAutoTable.finalY + 20);
    
    const lrMetrics = overviewData.metrics.logisticRegression || overviewData.metrics;
    const perfBody = [
      ["Accuracy", lrMetrics.accuracyLabel],
      ["Precision", lrMetrics.precisionLabel],
      ["Recall", lrMetrics.recallLabel],
      ["F1 Score", lrMetrics.f1ScoreLabel],
    ];

    doc.autoTable({
      startY: doc.lastAutoTable.finalY + 30,
      head: [["Metric", "Value"]],
      body: perfBody,
      theme: "striped",
      headStyles: { fillColor: [71, 85, 105] },
    });

    // Confusion Matrix
    doc.setFontSize(16);
    doc.text("Confusion Matrix (Test Set)", 20, doc.lastAutoTable.finalY + 20);
    
    const cm = lrMetrics.confusionMatrix || {};
    const cmBody = [
      ["True Positive (TP)", cm.truePositive || 0],
      ["False Positive (FP)", cm.falsePositive || 0],
      ["True Negative (TN)", cm.trueNegative || 0],
      ["False Negative (FN)", cm.falseNegative || 0],
    ];

    doc.autoTable({
      startY: doc.lastAutoTable.finalY + 30,
      head: [["Metric", "Count"]],
      body: cmBody,
      theme: "grid",
      headStyles: { fillColor: [100, 116, 139] },
    });
  }

  // Skill Gaps
  if (lastPredictionResult.skillGaps && lastPredictionResult.skillGaps.improvementAreas.length > 0) {
    doc.setFontSize(16);
    doc.text("Skill Gap Analysis", 20, doc.lastAutoTable.finalY + 20);
    
    const gapsBody = lastPredictionResult.skillGaps.improvementAreas.map(gap => [
      gap.label,
      gap.studentValue,
      gap.averagePlaced,
      gap.gap
    ]);

    doc.autoTable({
      startY: doc.lastAutoTable.finalY + 30,
      head: [["Area", "Your Value", "Placed Avg.", "Gap"]],
      body: gapsBody,
      theme: "striped",
      headStyles: { fillColor: [245, 158, 11] },
    });
  }

  // Footer
  const date = new Date().toLocaleString();
  doc.setFontSize(8);
  doc.setTextColor(100, 116, 139);
  doc.text(`Generated on ${date}`, 20, doc.internal.pageSize.height - 10);
  doc.text(`Page 1`, pageWidth - 20, doc.internal.pageSize.height - 10, { align: "right" });

  doc.save("placement_report.pdf");
}

window.downloadReport = downloadReport;

async function initialize() {
  try {
    const bundle = await loadBundle();
    predictorBundle = bundle.predictor;
    overviewData = bundle.overview;
    setOverview(bundle.overview);
    document
      .getElementById("prediction-form")
      .addEventListener("submit", handlePrediction);
  } catch (error) {
    setText("prediction-label", "Unable to load dashboard");
    document.getElementById("prediction-copy").textContent = error.message;
  }
}

initialize();
