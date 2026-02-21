#!/usr/bin/env python3
"""跨市场映射系统 Web 版（无第三方依赖）"""

from __future__ import annotations

import html
from datetime import datetime
import os
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from mapping_system import compute_result


def page_template(content: str) -> str:
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>跨市场映射系统 1.0</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 32px auto; line-height: 1.5; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-top: 16px; }}
    .score {{ font-size: 24px; font-weight: bold; }}
    .ok {{ color: #0a7a2f; }}
    .no {{ color: #b3261e; }}
    input[type=date] {{ padding: 6px; }}
    button {{ padding: 8px 14px; cursor: pointer; }}
    ul {{ padding-left: 20px; }}
  </style>
</head>
<body>
  <h1>🔥 跨市场映射系统 1.0（网页版）</h1>
  <form method=\"post\">
    <label>评估日期：</label>
    <input type=\"date\" name=\"date\" required />
    <button type=\"submit\">计算评分</button>
  </form>
  {content}
</body>
</html>
"""


def render_result(date: str) -> str:
    result = compute_result(
        target_date=date,
        tsla_csv="data/tsla_daily.csv",
        ashare_csv="data/ashare_daily.csv",
        events_json="data/events.json",
        pools_json="config/pools.json",
    )

    action_class = "ok" if int(result["total"]) >= 6 and result["state"] != "回撤" else "no"
    picks_html = "".join(
        f"<li>{p.ticker} {html.escape(p.name)} ({html.escape(p.pool)}) 涨幅{p.pct_change:.2f}% 量比{p.volume_ratio:.2f}</li>"
        for p in result["picks"]
    )
    if not picks_html:
        picks_html = "<li>暂无满足确认条件的标的</li>"

    return f"""
<div class=\"card\">
  <div><strong>日期：</strong>{result['date']}</div>
  <div><strong>TSLA 情绪：</strong>{result['state']}</div>
  <div><strong>分项：</strong>美股动能 {result['us_score']}/4，事件强度 {result['event_score']}/3，A股确认 {result['a_score']}/3</div>
  <div class=\"score\">总分：{result['total']}/10</div>
  <div class=\"{action_class}\"><strong>执行建议：</strong>{result['action']}</div>
  <div><strong>情绪说明：</strong>{'；'.join(result['state_notes'])}</div>
  <div><strong>A股说明：</strong>{'；'.join(result['a_notes'])}</div>
  <div><strong>重点观察：</strong><ul>{picks_html}</ul></div>
</div>
"""


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    if method == "GET":
        body = page_template("<p>请输入日期并计算。</p>").encode("utf-8")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]

    if method == "POST":
        try:
            size = int(environ.get("CONTENT_LENGTH", "0") or "0")
            payload = environ["wsgi.input"].read(size).decode("utf-8")
            form = parse_qs(payload)
            date = form.get("date", [""])[0]
            datetime.strptime(date, "%Y-%m-%d")
            content = render_result(date)
            body = page_template(content).encode("utf-8")
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))])
            return [body]
        except Exception as exc:
            error = f"<div class='card no'><strong>错误：</strong>{html.escape(str(exc))}</div>"
            body = page_template(error).encode("utf-8")
            start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))])
            return [body]

    start_response("405 Method Not Allowed", [("Content-Type", "text/plain; charset=utf-8")])
    return ["Method Not Allowed".encode("utf-8")]


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))
    print(f"Web 服务启动: http://{host}:{port}")
    with make_server(host, port, app) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
