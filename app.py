#!/usr/bin/env python3
"""report-builder-hwpx 로컬 편집 웹앱.

브라우저에서 보고서 목차·본문을 편집하고, 각 문장이 어느 출처(URL)의
원문을 사용했는지 나란히 대조한 뒤, 'HWP' 버튼으로 .hwpx를 내려받는다.

실행:
  python app.py --report _workspace/report.json --port 5000
  (--report 미지정 시 sample/report.json 사용)

엔드포인트:
  GET  /              편집 화면
  GET  /api/report    현재 report.json 반환
  POST /api/save      편집 내용 저장 (report.json 덮어쓰기)
  POST /api/export    편집 내용으로 .hwpx 생성 후 파일 다운로드
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file, Response

SKILL_DIR = Path(__file__).resolve().parent
SECTION_SCRIPT = SKILL_DIR / "scripts" / "section_from_report.py"

app = Flask(__name__, static_folder=None)

# 런타임 상태 (--report 로 주입)
STATE = {"report_path": SKILL_DIR / "sample" / "report.json"}


def load_report() -> dict:
    return json.loads(Path(STATE["report_path"]).read_text(encoding="utf-8"))


def save_report(data: dict) -> None:
    Path(STATE["report_path"]).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@app.get("/")
def index() -> Response:
    html = (SKILL_DIR / "templates" / "editor.html").read_text(encoding="utf-8")
    return Response(html, mimetype="text/html")


@app.get("/api/report")
def api_report():
    return jsonify(load_report())


@app.post("/api/save")
def api_save():
    data = request.get_json(force=True)
    save_report(data)
    return jsonify({"ok": True})


@app.post("/api/export")
def api_export():
    data = request.get_json(force=True)
    # 편집 내용을 먼저 저장
    save_report(data)

    out_dir = SKILL_DIR / "output"
    out_dir.mkdir(exist_ok=True)
    raw_title = data.get("title") or data.get("topic") or "report"
    title_slug = re.sub(r'[\s\\/:*?"<>|]+', '_', raw_title).strip('_')
    versions = []
    for f in out_dir.glob("*_v*.0.hwpx"):
        if f.stem.startswith(title_slug + "_v"):
            m = re.search(r'_v(\d+)\.0$', f.stem)
            if m:
                versions.append(int(m.group(1)))
    next_ver = max(versions, default=0) + 1
    out_path = out_dir / f"{title_slug}_v{next_ver}.0.hwpx"

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(data, tf, ensure_ascii=False)
        report_tmp = tf.name

    cmd = [
        sys.executable, str(SECTION_SCRIPT),
        "--report", report_tmp,
        "--output", str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    Path(report_tmp).unlink(missing_ok=True)
    if result.returncode != 0:
        return jsonify({"ok": False, "error": result.stderr or result.stdout}), 500

    return send_file(
        out_path, as_attachment=True, download_name=out_path.name,
        mimetype="application/hwp+zip",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", help="report.json 경로")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    if args.report:
        STATE["report_path"] = Path(args.report).resolve()
    print(f"[report-builder-hwpx] report: {STATE['report_path']}")
    print(f"[report-builder-hwpx] open  : http://127.0.0.1:{args.port}/")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
