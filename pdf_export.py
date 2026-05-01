from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_prediction_report(student_data, prediction_result, skill_gaps, overview_data=None):
    """Generate a polished PDF report for placement prediction."""

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.55 * inch,
        title="Student Placement Prediction Report",
        author="PlacementVision AI",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=10,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0f172a"),
        )
    )

    story = [
        Paragraph("Student Placement Prediction Report", styles["ReportTitle"]),
        Paragraph(
            f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            styles["ReportSubTitle"],
        ),
        _build_summary_table(student_data, prediction_result, styles),
        Spacer(1, 0.16 * inch),
        Paragraph("Student Profile", styles["SectionHeading"]),
        _build_profile_table(student_data, styles),
        Spacer(1, 0.16 * inch),
        Paragraph("Prediction Result", styles["SectionHeading"]),
        _build_prediction_table(prediction_result, styles),
    ]

    if prediction_result.get("modelPredictions"):
        story.extend([
            Spacer(1, 0.16 * inch),
            Paragraph("Model Comparison", styles["SectionHeading"]),
            _build_model_table(prediction_result["modelPredictions"], styles),
        ])

    if skill_gaps is not None:
        story.extend([
            Spacer(1, 0.16 * inch),
            Paragraph("Skill Gap Analysis", styles["SectionHeading"]),
            _build_skill_gap_section(skill_gaps, styles),
        ])

    if overview_data:
        story.extend([
            Spacer(1, 0.16 * inch),
            Paragraph("Model Performance (Overall)", styles["SectionHeading"]),
            _build_performance_table(overview_data.get("metrics", {}), styles),
            Spacer(1, 0.16 * inch),
            Paragraph("Confusion Matrix (Test Set)", styles["SectionHeading"]),
            _build_confusion_matrix_table(overview_data.get("metrics", {}), styles),
        ])

    document.build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _decorate_page(canvas, document):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0f172a"))
    canvas.rect(0, height - 42, width, 42, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(document.leftMargin, height - 26, "PlacementVision AI")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(
        width - document.rightMargin,
        height - 26,
        "Student Placement Prediction Report",
    )
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - document.rightMargin, 18, f"Page {document.page}")
    canvas.restoreState()


def _build_summary_table(student_data, prediction_result, styles):
    data = [
        [
            Paragraph("Overall Prediction", styles["BodyBold"]),
            Paragraph(_pretty_value(prediction_result.get("prediction", "N/A")), styles["BodySmall"]),
            Paragraph("Placement Probability", styles["BodyBold"]),
            Paragraph(_pretty_value(prediction_result.get("probabilityLabel", "N/A")), styles["BodySmall"]),
        ],
        [
            Paragraph("Confidence Level", styles["BodyBold"]),
            Paragraph(_pretty_value(prediction_result.get("confidenceLabel", "N/A")), styles["BodySmall"]),
            Paragraph("Student Name", styles["BodyBold"]),
            Paragraph(_pretty_value(student_data.get("Name", "N/A")), styles["BodySmall"]),
        ],
    ]

    table = Table(data, colWidths=[1.35 * inch, 2.05 * inch, 1.45 * inch, 1.65 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _build_profile_table(student_data, styles):
    rows = [[Paragraph("Field", styles["BodyBold"]), Paragraph("Value", styles["BodyBold"])]]
    for key, value in student_data.items():
        rows.append([
            Paragraph(_format_label(key), styles["BodySmall"]),
            Paragraph(_pretty_value(value), styles["BodySmall"]),
        ])

    table = Table(rows, colWidths=[2.35 * inch, 4.7 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _build_prediction_table(prediction_result, styles):
    rows = [[Paragraph("Metric", styles["BodyBold"]), Paragraph("Result", styles["BodyBold"])]]
    rows.append([Paragraph("Prediction", styles["BodySmall"]), Paragraph(_pretty_value(prediction_result.get("prediction", "N/A")), styles["BodySmall"])])
    rows.append([Paragraph("Probability", styles["BodySmall"]), Paragraph(_pretty_value(prediction_result.get("probabilityLabel", "N/A")), styles["BodySmall"])])
    rows.append([Paragraph("Confidence", styles["BodySmall"]), Paragraph(_pretty_value(prediction_result.get("confidenceLabel", "N/A")), styles["BodySmall"])])

    table = Table(rows, colWidths=[2.1 * inch, 4.95 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10b981")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _build_model_table(model_predictions, styles):
    rows = [[Paragraph("Model", styles["BodyBold"]), Paragraph("Prediction", styles["BodyBold"]), Paragraph("Probability", styles["BodyBold"])]]
    for model_name, model_pred in model_predictions.items():
        rows.append([
            Paragraph(_format_label(model_name), styles["BodySmall"]),
            Paragraph(_pretty_value(model_pred.get("prediction", "N/A")), styles["BodySmall"]),
            Paragraph(_format_probability(model_pred.get("probability")), styles["BodySmall"]),
        ])

    table = Table(rows, colWidths=[2.5 * inch, 1.9 * inch, 2.65 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8b5cf6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _build_skill_gap_section(skill_gaps, styles):
    improvement = [gap for gap in skill_gaps if gap.get("needsImprovement")]
    if not improvement:
        return Paragraph("Your profile is competitive. No major skill gaps were identified.", styles["BodySmall"])

    rows = [[Paragraph("Area", styles["BodyBold"]), Paragraph("Your Value", styles["BodyBold"]), Paragraph("Placed Avg.", styles["BodyBold"]), Paragraph("Gap", styles["BodyBold"])]]
    for gap in improvement:
        rows.append([
            Paragraph(_pretty_value(gap.get("label", "N/A")), styles["BodySmall"]),
            Paragraph(_pretty_value(gap.get("studentValue", "N/A")), styles["BodySmall"]),
            Paragraph(_pretty_value(gap.get("averagePlaced", "N/A")), styles["BodySmall"]),
            Paragraph(_pretty_value(gap.get("gap", "N/A")), styles["BodySmall"]),
        ])

    table = Table(rows, colWidths=[2.35 * inch, 1.55 * inch, 1.55 * inch, 1.45 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f59e0b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _build_performance_table(metrics, styles):
    lr_metrics = metrics.get("logisticRegression", {})
    rows = [
        [Paragraph("Metric", styles["BodyBold"]), Paragraph("Value", styles["BodyBold"])],
        [Paragraph("Accuracy", styles["BodySmall"]), Paragraph(lr_metrics.get("accuracyLabel", "N/A"), styles["BodySmall"])],
        [Paragraph("Precision", styles["BodySmall"]), Paragraph(lr_metrics.get("precisionLabel", "N/A"), styles["BodySmall"])],
        [Paragraph("Recall", styles["BodySmall"]), Paragraph(lr_metrics.get("recallLabel", "N/A"), styles["BodySmall"])],
        [Paragraph("F1 Score", styles["BodySmall"]), Paragraph(lr_metrics.get("f1ScoreLabel", "N/A"), styles["BodySmall"])],
    ]
    table = Table(rows, colWidths=[2.5 * inch, 4.55 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _build_confusion_matrix_table(metrics, styles):
    lr_metrics = metrics.get("logisticRegression", {})
    cm = lr_metrics.get("confusionMatrix", {})
    
    data = [
        [Paragraph("Metric", styles["BodyBold"]), Paragraph("Count", styles["BodyBold"])],
        [Paragraph("True Positive (TP)", styles["BodySmall"]), Paragraph(str(cm.get("truePositive", 0)), styles["BodySmall"])],
        [Paragraph("False Positive (FP)", styles["BodySmall"]), Paragraph(str(cm.get("falsePositive", 0)), styles["BodySmall"])],
        [Paragraph("True Negative (TN)", styles["BodySmall"]), Paragraph(str(cm.get("trueNegative", 0)), styles["BodySmall"])],
        [Paragraph("False Negative (FN)", styles["BodySmall"]), Paragraph(str(cm.get("falseNegative", 0)), styles["BodySmall"])],
    ]
    
    table = Table(data, colWidths=[2.5 * inch, 4.55 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#64748b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _format_label(value):
    text = str(value).replace("_", " ")
    text = text.replace("eextracurriculars", "Extracurricular Activities")
    return " ".join(word.capitalize() for word in text.split())


def _pretty_value(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "N/A"
    return str(value)


def _format_probability(value):
    if isinstance(value, (int, float)):
        return f"{value * 100:.2f}%"
    return _pretty_value(value)


def export_as_text(student_data, prediction_result, skill_gaps):
    """Preserve a text fallback for debugging."""
    lines = [
        "STUDENT PLACEMENT PREDICTION REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Student Profile:",
    ]
    for key, value in student_data.items():
        lines.append(f"- {_format_label(key)}: {_pretty_value(value)}")
    lines.extend([
        "",
        "Prediction Result:",
        f"- Overall Prediction: {_pretty_value(prediction_result.get('prediction', 'N/A'))}",
        f"- Placement Probability: {_pretty_value(prediction_result.get('probabilityLabel', 'N/A'))}",
        f"- Confidence Level: {_pretty_value(prediction_result.get('confidenceLabel', 'N/A'))}",
        "",
    ])
    return "\n".join(lines)
