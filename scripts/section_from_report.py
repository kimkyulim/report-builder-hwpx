#!/usr/bin/env python3
"""report.json -> HWPX (사용자 양식 기반).

report.json(목차+섹션+본문 블록+출처)을 사용자의 실제 보고서 양식
(templates/forms/form_default.hwpx)의 문단 스타일을 그대로 복제하여
section0.xml로 변환한 뒤, 같은 양식 zip에 끼워 넣어 .hwpx로 포장한다.

양식 매핑 (form_default.hwpx에서 확인됨):
  - 문서 제목   : paraPr=20 charPr=15  (secPr 포함 — 첫 문단)
  - 부제(부서·날짜): paraPr=20 charPr=14
  - 섹션 제목 □ : paraPr=21 charPr=13
  - 본문 ㅇ     : paraPr=23 charPr=24
  - 출처 제목 □ : paraPr=21 charPr=19  ("□ 출처")
  - 출처 ㅇ+링크: paraPr=23 (하이퍼링크 필드 포함)

출처는 본문에 인라인하지 않고, 양식과 동일하게 맨 끝 "□ 출처" 섹션으로
모아서(중복 제거) 출력한다. (provenance는 report.json의 block.sources가 유지)

Usage:
  python section_from_report.py --report report.json --output out.hwpx
  python section_from_report.py --report report.json --template my_form.hwpx --output out.hwpx
"""
import argparse
import copy
import json
import os
import zipfile
from pathlib import Path

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS = {"hp": HP}
P = f"{{{HP}}}p"
RUN = f"{{{HP}}}run"
T = f"{{{HP}}}t"
LINESEG = f"{{{HP}}}linesegarray"

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_TEMPLATE = SKILL_DIR / "templates" / "forms" / "form_default.hwpx"

# 하이퍼링크 필드 ID 시퀀스 (문서 내 유일해야 함)
_FIELD_ID = [3100000000]


def next_field_id():
    _FIELD_ID[0] += 1
    return _FIELD_ID[0]


def find_para(paras, para_pr, first_char_pr=None, want_link=None):
    """paraPrIDRef / 첫 run charPrIDRef / 링크포함여부로 문단 템플릿을 찾는다."""
    for p in paras:
        if p.get("paraPrIDRef") != para_pr:
            continue
        runs = p.findall(RUN)
        if first_char_pr is not None:
            if not runs or runs[0].get("charPrIDRef") != first_char_pr:
                continue
        if want_link is not None:
            has_link = p.find(f".//{{{HP}}}fieldBegin") is not None
            if has_link != want_link:
                continue
        return p
    return None


def strip_lineseg(p):
    """줄 배치 캐시 제거 — 한글이 열 때 재계산하도록 (레이아웃 깨짐 방지)."""
    for ls in p.findall(LINESEG):
        p.remove(ls)
    return p


def set_simple_text(p, text):
    """단순 텍스트 문단: 첫 run만 남기고 그 안 첫 <hp:t>를 text로 교체."""
    strip_lineseg(p)
    runs = p.findall(RUN)
    for r in runs[1:]:
        p.remove(r)
    run = runs[0]
    for el in list(run):
        if el.tag != T:
            run.remove(el)
    ts = run.findall(T)
    for extra in ts[1:]:
        run.remove(extra)
    if ts:
        ts[0].text = text
    else:
        etree.SubElement(run, T).text = text
    return p


def set_first_t(p, text):
    """secPr 등 ctrl을 보존하며 첫 <hp:t>만 교체 (제목 문단 전용)."""
    strip_lineseg(p)
    ts = p.findall(f".//{T}")
    if ts:
        ts[0].text = text
        for extra in ts[1:]:
            extra.text = ""
    return p


def make_source_para(link_tmpl, citation, url, bullet=None):
    """출처 링크 문단 생성. 실제 양식의 링크 문단을 복제해 인용문/URL만 교체.
    구조: [bullet] [인용텍스트 + fieldBegin] [Link] [fieldEnd + )]
    bullet 지정 시 머리기호 run(" ㅇ ")을 교체 — 각주식 들여쓰기에 사용."""
    p = strip_lineseg(copy.deepcopy(link_tmpl))
    runs = p.findall(RUN)
    # runs[0] = 머리기호(" ㅇ "), runs[1] = 인용 텍스트 + fieldBegin
    if bullet is not None and runs:
        bt = runs[0].find(T)
        if bt is not None:
            bt.text = bullet
    if len(runs) >= 2:
        t = runs[1].find(T)
        if t is not None:
            t.text = f"{citation} ("
    # 하이퍼링크 파라미터 교체 + 유일 ID 부여
    fid = next_field_id()
    fb = p.find(f".//{{{HP}}}fieldBegin")
    if fb is not None:
        fb.set("id", str(fid))
        for sp in fb.findall(f".//{{{HP}}}stringParam"):
            if sp.get("name") == "Command":
                sp.text = url + ";1;0;0;"
            elif sp.get("name") == "Path":
                sp.text = url
    fe = p.find(f".//{{{HP}}}fieldEnd")
    if fe is not None:
        fe.set("beginIDRef", str(fid))
    return p


def build_section(report, template_hwpx):
    with zipfile.ZipFile(template_hwpx) as z:
        section_bytes = z.read("Contents/section0.xml")
    root = etree.fromstring(section_bytes)
    paras = root.findall(P)

    # 양식에서 스타일 운반체 문단 확보
    title_tmpl = paras[0]                                  # secPr 포함
    subline_tmpl = find_para(paras, "20", "14")
    if subline_tmpl is None:
        subline_tmpl = paras[1]
    heading_tmpl = find_para(paras, "21", "13")
    srchead_tmpl = find_para(paras, "21", "19")
    body_tmpl = find_para(paras, "23", "24", want_link=False)
    link_tmpl = find_para(paras, "23", want_link=True)

    if any(t is None for t in (heading_tmpl, body_tmpl, srchead_tmpl, link_tmpl)):
        raise SystemExit("양식에서 필요한 문단 스타일을 찾지 못했습니다 (양식 구조 확인 필요).")

    new = []
    # 제목 (secPr 보존)
    new.append(set_first_t(copy.deepcopy(title_tmpl), report.get("title", "")))
    # 부제: (부서, `날짜)
    date = report.get("date", "")
    dept = report.get("department", "")
    new.append(set_simple_text(copy.deepcopy(subline_tmpl), f"({dept}, `{date})"))

    src_index = {s["id"]: s for s in report.get("sources", [])}
    used_source_ids = []

    def citation_of(s):
        return f'{s.get("source","")}, "{s.get("title","")}" ({s.get("date","")})'

    for section in report.get("sections", []):
        new.append(set_simple_text(copy.deepcopy(heading_tmpl),
                                   "□ " + section.get("heading", "").lstrip("0123456789. ")))
        for block in section.get("blocks", []):
            new.append(set_simple_text(copy.deepcopy(body_tmpl),
                                       " ㅇ " + block.get("text", "")))
            # 각주식: 이 문장이 근거로 쓴 출처를 바로 밑에 들여써서 표시(하이퍼링크)
            for sid in block.get("sources", []):
                s = src_index.get(sid)
                if not s:
                    continue
                new.append(make_source_para(
                    link_tmpl, citation_of(s), s.get("url", ""), bullet="    - "))
                if sid not in used_source_ids:
                    used_source_ids.append(sid)

    # 출처 섹션 (양식과 동일: □ 출처 + ㅇ ... (Link))
    if used_source_ids:
        new.append(set_simple_text(copy.deepcopy(srchead_tmpl), "□ 출처"))
        for sid in used_source_ids:
            s = src_index[sid]
            new.append(make_source_para(link_tmpl, citation_of(s), s.get("url", "")))

    # 기존 문단 제거 후 교체
    for p in paras:
        root.remove(p)
    for p in new:
        root.append(p)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def pack(template_hwpx, output_path, new_section_bytes):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    tmp = str(output_path) + ".tmp"
    with zipfile.ZipFile(template_hwpx, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "Contents/section0.xml":
                data = new_section_bytes
            if info.filename == "mimetype":
                zout.writestr(info, data, compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr(info, data)
    os.replace(tmp, output_path)


def main():
    ap = argparse.ArgumentParser(description="report.json -> HWPX (양식 기반)")
    ap.add_argument("--report", required=True)
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    section_bytes = build_section(report, args.template)
    pack(args.template, args.output, section_bytes)
    print(f"HWPX written: {args.output}")


if __name__ == "__main__":
    main()
