import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from config import PORT, PUBLIC_DIR
from model_service import MODEL_BUNDLE, build_overview_payload, format_percent, predict_placement, get_skill_gaps
from pdf_export import generate_prediction_report


class PlacementHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/overview":
            self.send_json(200, build_overview_payload())
            return

        if parsed.path == "/":
            self.serve_file(PUBLIC_DIR / "index.html")
            return

        file_path = (PUBLIC_DIR / parsed.path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(PUBLIC_DIR.resolve())):
            self.send_json(403, {"error": "Forbidden"})
            return
        self.serve_file(file_path)

    def do_POST(self):
        parsed = urlparse(self.path)
        
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body) if raw_body else {}
            
            if parsed.path == "/api/predict":
                result = predict_placement(payload)
                self.send_json(200, result)
            elif parsed.path == "/api/skill-gaps":
                result = get_skill_gaps(payload)
                self.send_json(200, result)
            elif parsed.path == "/api/models":
                result = {
                    "models": [
                        {"name": "Logistic Regression", "id": "logisticRegression"},
                        {"name": "Random Forest", "id": "randomForest"},
                        {"name": "SVM", "id": "svm"},
                    ]
                }
                self.send_json(200, result)
            elif parsed.path == "/api/export":
                # Get prediction and skill gaps
                prediction = predict_placement(payload)
                skill_gaps_data = get_skill_gaps(payload)
                
                # Generate report
                report_pdf = generate_prediction_report(
                    payload, 
                    prediction, 
                    skill_gaps_data["skillGaps"],
                    build_overview_payload()
                )
                
                # Send as downloadable file
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", "attachment; filename=placement_report.pdf")
                self.send_header("Content-Length", str(len(report_pdf)))
                self.end_headers()
                self.wfile.write(report_pdf)
            else:
                self.send_json(404, {"error": "Not found"})
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON body"})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})

    def serve_file(self, file_path):
        if not file_path.exists() or not file_path.is_file():
            self.send_json(404, {"error": "File not found"})
            return

        content_type = self.get_content_type(file_path.suffix.lower())
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def get_content_type(self, suffix):
        mapping = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }
        return mapping.get(suffix, "text/plain; charset=utf-8")

    def log_message(self, format_string, *args):
        return


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer(("0.0.0.0", PORT), PlacementHandler)
        print(f"Placement predictor is running on http://localhost:{PORT}")
        # Display metrics for main model (Logistic Regression)
        lr_metrics = MODEL_BUNDLE['metrics'].get('logisticRegression', {})
        print(
            "Accuracy: "
            f"{format_percent(lr_metrics.get('accuracy', 0))} | "
            f"F1: {format_percent(lr_metrics.get('f1Score', 0))}"
        )
        print("Starting server...")
        server.serve_forever()
    except Exception as e:
        print(f"Error starting server: {e}")
