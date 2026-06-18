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
`$SKILL_DIR` = 이 SKILL.md가 있는 디렉토리. hwpx 출력은 이 스킬의
`scripts/section_from_report.py`만으로 완결된다 (외부 스킬 의존 없음).

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

**부서명 — 반드시 먼저 묻기 (기본값 없음)**
주제가 명시되어 있어도 부서명이 없으면 검색을 시작하기 전에 사용자에게 물어본다:
> "어느 팀/부서 이름으로 보고서를 작성할까요?"
사용자가 답변할 때까지 Phase 2로 넘어가지 않는다.

**날짜 — 실행 시점 자동 취득 (하드코딩 금지)**
보고서를 작성하는 시점의 실제 날짜를 Python으로 직접 읽어야 한다:
```python
# Windows: python / macOS·Linux: python3
python -c "from datetime import date; print(date.today().strftime('%y.%m.%d'))"
```
출력된 값(예: `26.06.18`)을 `date` 필드에 그대로 사용한다. 대화 맥락에서 날짜를 추측하거나 이전 보고서의 날짜를 재사용하지 않는다.

**그 외 입력**
- `기간`: 기본 8일 (명시 없으면 묻지 않고 기본값 사용)
- `topic_slug`: 파일명용 slug 자동 생성 (주제에서 파생)

### Phase 2: 검색 (뉴스·논문·특허)
WebSearch를 병렬로 3회 수행해 뉴스/논문/특허 결과를 모으고, URL·제목 유사도로 중복을 제거한다.
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

**작성 후 검증 게이트:** Phase 4로 넘어가기 전 다음을 확인한다:
- `sources` 배열이 비어 있는 block이 없어야 한다. 있으면 근거 출처를 보강하거나 해당 block을 삭제한다.
- 각 block의 주장이 연결된 출처의 제목·날짜·주제와 맥락상 일치해야 한다.

### Phase 4: 검증 (원문 대조) — 커버리지 70% 이상 목표

각 출처의 URL에 대해 **다음 순서로 원문을 획득**한다(성공 즉시 중단):

1. `WebFetch(url)` — 직접 접근해 본문 발췌
2. 실패(페이월·차단) 시: Phase 2에서 이미 수집한 스니펫·초록을 `originalExcerpt` 초안으로 사용
3. 스니펫도 없으면: `WebSearch("제목" 핵심어)` → 검색 결과 스니펫에서 발췌
4. 3단계 모두 실패 시에만 `"unchecked"` 유지, `fetchNote` 필드에 실패 이유 기록

원문 획득 후 `verifyStatus` 설정:
- block 주장을 원문이 뒷받침 → `"match"`
- 원문과 내용이 어긋남 → `"mismatch"` + block 본문을 원문 기준으로 즉시 교정
- 획득 불가 → `"unchecked"` + `fetchNote`

> 검증은 **사실 단언이 아니라 대조 보조**다. 불확실하면 `mismatch`/`unchecked`로 두고
> 사용자에게 확인을 맡긴다. 원문에 없는 내용을 채워 넣지 않는다.

**커버리지 목표:** `match + mismatch` 비율이 전체 출처의 **70% 이상**이어야 한다.
미달 시 실패한 출처를 재시도하거나 동일 내용의 접근 가능한 대체 URL을 추가한다.

### Phase 4b: 고유명사·숫자 검증 (entity & figure check) — 핵심

각 block에서 추출·대조할 entity 종류 (`kind`):
- `org` 회사·기관명 / `person` 인물명 / `date` 날짜·연도
- `money` 금액 / `coverage` 보장금액 / `stat` 통계·비율·물리량
- `count` 개수(~개국, ~개사, ~명) / `pct` 퍼센트·증감률

**필수 전처리:** entity 대조 전 `originalExcerpt`가 비어 있는 출처는 Phase 4 획득 전략을 재시도해 채운다.
채워지지 않으면 해당 출처를 참조하는 모든 entity는 `"unverified"` 처리(값을 지어내지 않는다).

대조 기준:
- `match`: 원문에 동치로 존재. 단위 표기만 다른 경우 포함(`$65 billion` ↔ `650억 달러`)
- `mismatch`: 원문의 값과 다름 → `sourceValue`에 원문 실제 값 기록 + block 본문 즉시 교정(예: "30여 개국" → "29개국")
- `unverified`: 원문 접근불가 또는 원문에서 근거 미발견(값을 지어내지 않는다)

**화폐 규칙:** `money`/`coverage`는 출처 원래 화폐 단위로만 비교·기록. 보고서에 환산값이 있으면 삭제 또는 교정.

결과를 각 block의 `entities[]`에 기록. 편집 화면에서 entity를 색으로 표시(녹색 일치/빨강 불일치/노랑 확인필요).

### Phase 4c: 출처 간 교차 검증 (cross-source consistency)

동일 entity(같은 기업·수치·날짜 등)가 여러 출처에서 언급될 경우:
1. 같은 entity를 참조하는 출처들의 값을 묶어 비교한다.
2. **일치**: 신뢰도 상승 → 관련 block의 `verifyStatus`를 `"match"`로 격상 가능.
3. **상충**: block 본문에 "(출처마다 상이)" 주석 추가, `verifyStatus`는 `"mismatch"` 유지.

### Phase 4d: 커버리지 요약 (검증 완료 보고)

Phases 4~4c 완료 후 다음을 계산해 사용자에게 표시한다:

| 항목 | 목표 |
|------|------|
| 출처 검증률 (match+mismatch / 전체) | **70% 이상** |
| 블록 검증률 (출처 모두 match인 블록 / 전체) | **60% 이상** |
| Entity 검증률 (match+mismatch / 전체) | **70% 이상** |
| 미확인 출처 목록 + `fetchNote` | 사용자에게 전달 |

블록 검증률이 60% 미만이면 Phase 5 전에 사용자에게 경고하고, 추가 보강(출처 보완·재검색) 여부를 묻는다.

완성된 `report.json`을 `_workspace/report.json`에 저장한다.

### Phase 5: 편집 + HWPX 다운로드 (로컬 웹앱)
로컬 편집 서버를 실행한다:
```bash
python3 "$SKILL_DIR/app.py" --report "$SKILL_DIR/_workspace/report.json" --port 8080
```
사용자에게 안내: **브라우저에서 http://127.0.0.1:8080/ 열기.**

편집 화면 기능:
- 상단 **커버리지 바**: 전체 블록 대비 검증 완료 비율(%) 실시간 표시. 70% 미만이면 빨간색 경고.
- **필터 버튼(전체 / ✓일치 / ✗불일치 / ·미확인)**: 상태별로 블록을 걸러 미확인 항목을 집중 처리.
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
