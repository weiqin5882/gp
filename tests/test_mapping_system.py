import io
from urllib.parse import urlencode

from mapping_system import compute_result
from web_app import app


def call_app(method: str, payload: str = ""):
    body_bytes = payload.encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "CONTENT_LENGTH": str(len(body_bytes)),
        "wsgi.input": io.BytesIO(body_bytes),
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], body


def test_compute_result_score():
    result = compute_result(
        target_date="2026-02-20",
        tsla_csv="data/tsla_daily.csv",
        ashare_csv="data/ashare_daily.csv",
        events_json="data/events.json",
        pools_json="config/pools.json",
    )
    assert result["total"] == 9
    assert result["state"] == "趋势扩张"


def test_web_get_home():
    status, body = call_app("GET")
    assert status.startswith("200")
    assert "跨市场映射系统 1.0" in body


def test_web_post_result():
    payload = urlencode({"date": "2026-02-20"})
    status, body = call_app("POST", payload)
    assert status.startswith("200")
    assert "总分：9/10" in body
