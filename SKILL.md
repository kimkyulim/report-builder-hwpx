---
name: report-builder-hwpx
description: "뉴스·논문·특허를 검색해 목차·본문이 있는 보고서를 작성하고, 각 문장이 어느 URL의 원문을 근거로 했는지 추적·검증한 뒤, 브라우저에서 직접 편집하고 'HWP' 버튼으로 사용자 양식의 .hwpx로 내려받는 스킬. 트리거: '보고서 작성', '동향 보고서 만들어줘', '검색해서 보고서', 'report-builder', '출처 검증 보고서', '{주제} 보고서 hwpx'."
---

# Report Builder HWPX — 검색·작성·출처검증·편집·HWPX 다운로드

임의 주제로 **뉴스·논문·특허를 검색** → **목차+본문 보고서 작성**(문장별 출처 추적) →
**원문 대조 검증** → **로컬 웹페이지에서 직접 편집** → **'HWP' 버튼으로 사용자 양식의 .hwpx 다운로드**
까지 한 번에 잇는 스킬.

출력 양식은 `templates/forms/form_default.hwpx`(사용자의 실제 보고서 양식)를 그대로 따른다:
`□ 섹션제목` / ` ㅇ 본문` / 맨 끝 `□ 출처` 섹션 + `(Link)` 하이퍼링크.

## 환경 점검 (세션 1회)

```bash
python3 -c "import lxml, flask, requests" 2>/dev/null
```
실패 시 1회 안내 후 자동 설치:
```bash
python3 -m pip install --user --quiet -r "$SKILL_DIR/requirements.txt"
```
`$SKILL_DIR` = 이 SKILL.md가 있는 디렉토리. hwpx 출력은 형제 스킬 `hwpx`의 양식 처리와
무관하게 이 스킬의 `scripts/section_from_report.py`만으로 완결된다.

## 데이터 모델 — report.json

스킬의 모든 단계는 하나의 `report.json`을 채워간다. 스키마(`sample/report.json` 참고):

```json
{
  "title": "문서 제목", "topic": "주제", "date": "YY.MM.DD", "department": "부서명",
  "toc": ["1. 개요", "2. ..."],
  "sections": [
    { "id": "s1", "heading": "1. 개요",
      "blocks": [ { "id": "b1", "text": "작성된 문장", "sources": ["src1"],
        "entities": [ { "text": "$65 billion", "kind": "org|person|date|money|coverage|stat",
                        "status": "match|mismatch|unverified", "sourceValue": "원문 실제 값(불일치 시)" } ] } ] }
  ],
  "sources": [
    { "id": "src1", "type": "news|paper|patent", "source": "주체/매체",
      "title": "원문 제목", "url": "https://...", "date": "YYYY-MM-DD",
      "originalExcerpt": "원문에서 추출한 근거 문장", "verifyStatus": "match|mismatch|unchecked" }
  ]
}
```

**핵심 규칙(출처 추적):** 본문 `block` 하나하나는 반드시 근거가 된 `sources`(출처 id 배열)를
가진다. 출처 없는 주장은 작성하지 않는다. 가짜 출처·URL을 만들지 않는다 — 실제 검색 결과만 사용.

## 워크플로우

### Phase 1: 입력
- `주제`(필수), `기간`(기본 8일), `부서명`을 사용자에게 확인. 누락 시 묻는다.
- `date` = 오늘(YY.MM.DD), `topic_slug` = 파일명용 slug 생성.

### Phase 2: 검색 (뉴스·논문·특허)
형제 스킬 `search-info-hwpx`의 검색 패턴을 재사용한다 — 3개 검색을 병렬로 수행해
뉴스/논문/특허 결과를 모으고, URL·제목 유사도로 중복을 제거한다.
각 결과를 `report.json`의 `sources[]` 항목으로 적재한다(`url`, `title`, `source`, `date`, `type`).
**이 단계에서 `originalExcerpt`는 비워두고, `verifyStatus`는 `"unchecked"`로 둔다.**

### Phase 3: 보고서 작성 (목차 + 본문, 출처 추적)
검색된 `sources`만을 근거로:
1. `toc`(목차)와 `sections[].heading`(섹션 제목)을 구성.
2. 각 섹션의 `blocks[]`를 작성하되, **모든 block에 근거 `sources` id를 연결**.
3. 음슴체/개조식 톤(예: "~확대하는 중", "~부상")으로 간결하게.
4. **화폐 규칙(필수): 금액은 출처의 원래 화폐단위 그대로 표기. 다른 화폐로 환산 금지**
   (달러는 `$`/달러, 유로는 `€`, 원은 `₩`/원, 위안·엔 등도 원문 단위 유지).
   예: 출처가 `$65 billion`이면 `$65 billion`(또는 `650억 달러`)으로 쓰되 `약 9조 원` 등으로 환산하지 않는다.

### Phase 4: 검증 (원문 대조) — 기본값
사용자가 선택한 검증 수준 = **원문 대조 표시**. 각 출처에 대해:
1. `url`을 가져와(WebFetch 또는 `requests`) 본문에서 해당 주장을 뒷받침하는
   **원문 근거 문장을 발췌**해 `source.originalExcerpt`에 채운다.
2. 작성된 block 내용과 원문 발췌를 비교해 `verifyStatus`를 설정:
   - 내용이 원문에 의해 뒷받침됨 → `"match"`
   - 원문과 어긋나거나 근거를 못 찾음 → `"mismatch"`
   - 확인 불가(접근 차단 등) → `"unchecked"` 유지
3. 판단은 사용자가 웹 편집 화면에서 최종 조정할 수 있다(아래 Phase 5).

> 검증은 **사실 단언이 아니라 대조 보조**다. 불확실하면 `mismatch`/`unchecked`로 두고
> 사용자에게 확인을 맡긴다. 원문에 없는 내용을 채워 넣지 않는다.

### Phase 4b: 고유명사·숫자 검증 (entity & figure check) — 핵심

Phase 4가 "문장↔출처"의 큰 그림을 대조한다면, 4b는 **사실의 핵(核)인 고유명사와 숫자만**
정밀 대조한다. 틀리면 가장 치명적인 항목이기 때문.

**전용 검증 에이전트**를 띄워 각 block에서 다음 종류(kind)만 추출·대조:
- `org` 회사·기관명 / `person` 인물명 / `date` 날짜·연도
- `money` 금액 / `coverage` 보장금액(보험 등) / `stat` 통계·비율·물리량

각 entity를 그 block의 출처 원문(`originalExcerpt`, 부족하면 `url`을 WebFetch)과 1:1 대조해
`status`를 정한다: `match`(원문에 동치로 존재) / `mismatch`(다름 → `sourceValue`에 원문 실제 값)
/ `unverified`(출처 접근불가·근거 못 찾음). **원문에 없는 값은 지어내지 않는다.**

**화폐 규칙(재확인): `money`/`coverage`는 출처의 원래 화폐단위 그대로 비교·기록.**
환산하지 않으므로 `650억 달러` ↔ `$65 billion`처럼 단위 표기만 다른 경우는 `match`로 본다.

결과를 각 block의 `entities[]`에 기록한다. `mismatch`가 나오면 **본문 문장을 원문이 뒷받침하는
선까지 교정**하고(예: "30여 개국" → 원문 "29개국"), `unverified`는 그대로 두어 사용자가
편집 화면에서 확인하도록 남긴다. 편집 화면은 entity를 색으로 표시(녹색 일치/빨강 불일치/노랑 확인필요).

> 빠른 보조 수단: 숫자·날짜·금액의 **문자열 일치**만 즉시 확인하려면 출처 발췌문에 해당 수치가
> 그대로 등장하는지 기계적으로 대조할 수 있다(고유명사·환산 동치 판정은 에이전트가 담당).

완성된 `report.json`을 `_workspace/report.json`에 저장한다.

### Phase 5: 편집 + HWPX 다운로드 (로컬 웹앱)
로컬 편집 서버를 실행한다:
```bash
python3 "$SKILL_DIR/app.py" --report "$SKILL_DIR/_workspace/report.json" --port 5057
```
사용자에게 안내: **브라우저에서 http://127.0.0.1:5057/ 열기.**

편집 화면 기능:
- 왼쪽: 목차·섹션 제목·본문을 직접 수정(클릭해서 인라인 편집).
- 오른쪽: 문장을 클릭하면 그 문장이 쓴 **출처·URL·원문 발췌**가 나란히 표시되고,
  **✓일치 / ✗불일치** 를 지정·수정 가능. 문장 옆 배지에 검증 상태 표시.
- **💾 저장**: 편집 내용을 `report.json`에 저장.
- **⬇ HWP**: 편집 내용으로 `.hwpx`를 생성해 즉시 다운로드.

내보내기는 내부적으로:
```bash
python3 "$SKILL_DIR/scripts/section_from_report.py" \
  --report _workspace/report.json --output output/{date}_{topic}.hwpx
```
양식(`templates/forms/form_default.hwpx`)의 문단 스타일을 복제해 채우므로 폰트·여백·
하이퍼링크가 사용자 양식과 동일하게 유지된다.

## 출력 위치
- 편집 상태: `_workspace/report.json`
- 완성 문서: `output/{YYMMDD}_{topic_slug}.hwpx` (앱이 자동 생성)

## 양식 교체
다른 보고서 양식을 쓰려면 `.hwpx`를 `templates/forms/form_default.hwpx`로 교체하거나
`section_from_report.py --template 경로`로 지정한다. 단, 양식의 문단 스타일 ID
(제목/부제/□섹션/ㅇ본문/□출처/링크)가 코드의 매핑과 맞아야 한다 — 다르면
`find_para()`의 paraPr/charPr 값을 양식에 맞게 조정한다.

## 파일 구성
```
report-builder-hwpx/
  SKILL.md
  app.py                       # 로컬 편집 웹앱 (Flask)
  templates/editor.html        # 편집 화면(목차·본문 편집 + 출처 대조 + HWP 버튼)
  templates/forms/form_default.hwpx   # 출력 양식(사용자 보고서 양식)
  scripts/section_from_report.py      # report.json -> .hwpx (양식 복제)
  sample/report.json           # 예시 데이터
  requirements.txt             # flask, lxml, requests
  _workspace/ , output/        # 런타임 산출물
```

## 원칙
- 가짜 출처·URL·인용을 만들지 않는다. 실제 검색으로 확인된 것만 보고서·출처에 넣는다.
- 모든 본문 주장에 근거 출처를 연결한다(출처 없는 단언 금지).
- 검증은 사용자의 최종 판단을 돕는 대조이며, 단정적 사실 확인이 아니다.
