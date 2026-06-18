# report-builder-hwpx

뉴스·논문·특허를 검색해 **목차·본문 보고서**를 작성하고, 각 문장이 어느 URL의 원문을
근거로 했는지 **추적·검증**한 뒤, 브라우저에서 직접 **편집**하고 'HWP' 버튼으로
사용자 양식의 **`.hwpx`로 내려받는** Claude Code 스킬.

## 파이프라인

1. **검색** — 뉴스/논문/특허 병렬 검색 (실제 URL만)
2. **작성** — 목차 + 본문, 문장별 출처(provenance) 연결
3. **검증**
   - 원문 대조: 각 문장 ↔ 출처 원문 발췌 비교
   - 고유명사·숫자 검증: 회사·인물·날짜·금액·통계 수치만 정밀 대조 (금액은 원문 화폐단위 유지)
4. **편집** — 로컬 웹앱(`app.py`)에서 목차·본문 수정, 출처·검증 상태 확인
5. **다운로드** — 'HWP' 버튼 → 양식(`templates/forms/form_default.hwpx`) 스타일로 `.hwpx` 생성

## 구성

```
SKILL.md                          워크플로우 정의
app.py                            로컬 편집 웹앱 (Flask)
templates/editor.html             편집 화면 (출처 각주 + 고유명사·숫자 검증 색표시)
templates/forms/form_default.hwpx 출력 양식 (□ 섹션 / ㅇ 본문 / □ 출처 + 하이퍼링크)
scripts/section_from_report.py    report.json -> .hwpx (양식 문단 복제)
sample/report.json                예시 데이터
requirements.txt                  flask, lxml, requests
```

## 사용

```bash
python3 -m pip install --user -r requirements.txt
python3 app.py --report _workspace/report.json --port 5057
# 브라우저에서 http://127.0.0.1:5057/ 열기
```

## 원칙

- 가짜 출처·URL·인용을 만들지 않는다. 실제 검색으로 확인된 것만 사용한다.
- 모든 본문 주장에 근거 출처를 연결한다(출처 없는 단언 금지).
- 검증은 사용자의 최종 판단을 돕는 대조이며, 단정적 사실 확인이 아니다.
- 금액은 출처의 원래 화폐단위 그대로 표기한다(환산 금지).
