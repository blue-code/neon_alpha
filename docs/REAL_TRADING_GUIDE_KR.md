# NeonAlpha 실전투자 운영 가이드 (미국 주식)

중요: 이 문서는 기술 운영 가이드입니다. 투자 손실 책임은 본인에게 있습니다.

연계 문서:
- [`DOCS_INDEX_KR.md`](DOCS_INDEX_KR.md)
- [`QLIB_RESEARCH_GUIDE_KR.md`](QLIB_RESEARCH_GUIDE_KR.md)
- [`LEAN_EXECUTION_GUIDE_KR.md`](LEAN_EXECUTION_GUIDE_KR.md)

---

## 1. 먼저 정확히: 이 프로젝트로 가능한 것 / 불가능한 것
### 가능한 것
- Qlib 기반 신호(`date,symbol,score`) 생성
- 신호 무결성 검증(중복/빈 데이터 체크)
- 로컬 페이퍼 시뮬레이션으로 리스크 점검
- LEAN 백테스트 실행
- LEAN 라이브 배포 실행(`bash run.sh live`)로 실전 주문 엔진 기동

### 불가능한 것(프로그램 외부에서 준비 필요)
- 브로커 계좌 개설(KYC/신원 인증)
- 은행 계좌 연결/입출금 승인
- 세금 신고 자동 처리
- 규정 위반 책임 대행

핵심은 `NeonAlpha = 전략/신호/운영 자동화`,  
`실거래 인프라 = 브로커/은행/세금/규정` 입니다.

---

## 2. 프로그램 외적으로 반드시 준비할 것
## 2-1. 브로커 계좌(증권계좌)
- 미국 주식 API 주문이 가능한 브로커 계좌 필요
- 계좌 유형(현금/마진), 공매도/프리마켓 허용 여부 확인
- 2단계 인증(MFA) 필수 적용

## 2-2. 은행 계좌(입출금 통장)
- 본인 명의 계좌 필요(타인 명의 금지)
- ACH/국제송금(wire) 중 어떤 방식으로 입금할지 결정
- 입금 후 매수 가능 시점(정산 지연)을 브로커 정책으로 확인

## 2-3. 신원/세금 서류
- 미국 거주/납세자: 보통 `W-9` 제출 대상
- 비미국 거주자: 보통 `W-8BEN` 제출 대상
- 연말 거래 내역/손익 정리용 세금 문서 수령 체계 확보

## 2-4. 규정/리스크
- 미국 마진계좌의 데이트레이딩 규정(PDT) 이해
- 자동매매 중단 기준(일손실/최대낙폭/주문 실패율) 사전 문서화

---

## 3. 실데이터는 어떻게 구하나? (실무 기준)
실데이터는 목적별로 분리해서 확보해야 합니다.

## 3-1. 연구/신호 생성용 데이터(일봉 중심)
선택지 A: Qlib 데이터셋
- 장점: 프로젝트와 바로 연동
- 주의: Qlib 문서에서 Yahoo 기반 데이터 품질 한계를 명시함
- 권장 용도: 아이디어 검증, 신호 생성

선택지 B: 외부 고품질 데이터(유료)
- 예: Polygon, 브로커 데이터 API
- 권장 용도: 실제 체결 환경과 유사한 검증

## 3-2. 실시간 주문용 데이터(체결/호가)
실전 주문은 브로커/실시간 데이터 플랜 품질이 성과를 좌우합니다.

예시:
- Alpaca 기본 플랜: 무료 실시간은 IEX 중심
- Alpaca 상위 플랜: SIP(전 거래소 통합) 실시간 접근
- Polygon: 플랜별로 15분 지연/실시간 권한이 다름

## 3-3. 실데이터 체크리스트
- 신호 생성 데이터와 실시간 주문 데이터의 시간대(ET) 일치
- 분할/배당 반영 정책 일치(조정주가 여부)
- 거래소 커버리지(IEX only vs SIP) 일치
- 지연 데이터로 실전 진입하지 않았는지 점검

---

## 4. 계좌 연결과 자금 흐름(진짜 운영 관점)
## 4-1. 계좌 개설
1. 브로커에서 개인/법인 계좌 개설
2. KYC 서류 제출(신분증, 주소증빙 등)
3. 승인 후 API 키 발급

## 4-2. 자금 이체
1. 브로커 입금 안내 페이지에서 본인 계좌 등록
2. ACH 또는 wire로 입금
3. 매수 가능 잔고 반영 시점 확인 후만 실전 시작

## 4-3. API 연결
1. Paper 키와 Live 키를 분리 관리
2. 키를 코드에 하드코딩하지 않고 환경변수/시크릿으로 관리
3. 최소권한 원칙(가능하면 읽기/거래 권한 분리)

주의:
- QuantConnect 문서 기준, Apple Silicon(M1/M2/M3) 환경에서는 IB 로컬 라이브 배포 제약이 있습니다.

---

## 5. NeonAlpha로 실전 투자하는 실제 절차
아래 순서를 벗어나면 실수 확률이 크게 올라갑니다.

## 5-1. D-30 ~ D-1: 준비 구간
1. 최소 4주 이상 Paper Trading 운영
2. 장애 로그(주문 실패, 재시도, 데이터 누락) 누적
3. 손실 제한 규칙 확정:
- `max_positions`
- `max_weight_per_symbol`
- `max_daily_turnover`
- 계좌 단위 일손실/최대낙폭 중단선

## 5-2. D-1(장 마감 후): 신호 생성
```bash
bash run.sh qlib \
  --provider-uri ~/.qlib/qlib_data/us_data \
  --start 2022-01-01 \
  --end 2026-02-06 \
  --symbols AAPL MSFT NVDA AMZN GOOGL META SPY \
  --output neon_alpha/data/generated_signals.csv

bash run.sh validate --signal-csv neon_alpha/data/generated_signals.csv
```

## 5-3. D-0(장 시작 전): 라이브 배포
`run.sh live`는 아래를 자동 수행합니다.
1. 알고리즘 파일을 LEAN 프로젝트 `main.py`로 복사
2. 신호를 LEAN 프로젝트 `data/signals.csv`로 복사
3. `lean live deploy` 실행

예시 1: 대화형 배포(권장 시작 방식)
```bash
bash run.sh live \
  --lean-project /path/to/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv
```

예시 2: 비대화형 배포(Alpaca, 실계좌)
```bash
bash run.sh live \
  --lean-project /path/to/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv \
  -- \
  --brokerage Alpaca \
  --data-provider-live Alpaca \
  --alpaca-environment live \
  --alpaca-api-key "$ALPACA_API_KEY" \
  --alpaca-api-secret "$ALPACA_API_SECRET"
```

예시 3: 비대화형 배포(Paper Trading)
```bash
bash run.sh live \
  --lean-project /path/to/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv \
  -- \
  --brokerage "Paper Trading" \
  --data-provider-live Alpaca \
  --alpaca-environment paper \
  --alpaca-api-key "$ALPACA_PAPER_KEY" \
  --alpaca-api-secret "$ALPACA_PAPER_SECRET"
```

---

## 6. 실전 중 반드시 알아야 할 전략 동작
현재 알고리즘(`execution/lean/HybridQlibLeanAlgorithm.py`)의 핵심 동작:
- 미국장 기준 매일 장 시작 후 5분에 리밸런싱
- `score` 상위 종목만 보유
- `min_score` 미만 종목 제외
- 일일 회전율(`max_daily_turnover`) 초과 시 리밸런싱 억제

즉, 실전 주문 빈도는 "하루 1회 리밸런싱 전략"에 가깝습니다.

---

## 7. 운영 루틴(실전)
## 7-1. 장 시작 전(Pre-market)
- 당일 신호 파일 갱신 시각 확인
- 신호 검증(`validate`) 통과 여부 확인
- 브로커 계좌 잔고/매수가능금액 확인
- 실시간 데이터 권한(SIP/실시간 feed) 확인

## 7-2. 장중
- 주문 체결 실패/거부 사유 모니터링
- 네트워크 단절/재연결 로그 확인
- 손실 제한선 초과 시 즉시 중단(`lean live stop`)

## 7-3. 장 마감 후
- 주문 내역/포지션/잔고 스냅샷 저장
- 전략 기대치와 실제 체결 차이(슬리피지) 기록
- 다음 영업일 신호 생성 스케줄 확인

---

## 8. 사고(장애) 대응 런북
## 8-1. 즉시 중단 조건 예시
- 일손실 -2% 초과
- 주문 실패율 5% 초과
- 데이터 지연 60초 이상 지속

## 8-2. 중단 절차
1. `lean live stop <project>`로 엔진 중단
2. 브로커 앱/웹에서 미체결 주문 취소
3. 필요 시 수동 청산
4. API 키 폐기/재발급(의심 접근 시)
5. 원인 분석 전 재가동 금지

---

## 9. 세금/회계 최소 운영 기준
## 9-1. 미국 납세자(일반)
- 브로커에서 세금 보고용 거래 문서(예: 1099 계열) 수령
- 손익/수수료/배당을 연 단위로 정리

## 9-2. 비미국 납세자(일반)
- 계좌 개설 시 요구되는 비거주자 서류(W-8BEN 등) 정확히 제출
- 거주국 세법 기준으로 해외주식 손익 신고 의무 확인

실무 팁:
- 월별로 거래원장 CSV를 별도 보관
- 브로커 리포트와 자체 로그를 월 1회 대조

---

## 10. 브로커 선택 기준(실전용)
1. API 안정성(주문 오류율, 재연결 정책)
2. 실시간 데이터 품질(IEX vs SIP vs 거래소 직결)
3. 수수료/환전/출금 비용
4. 지역/국적별 계좌 개설 가능성
5. 장애 시 지원 속도(티켓/SLA)

---

## 11. 최종 체크리스트(실전 시작 전)
- [ ] 브로커 라이브 계좌 승인 완료
- [ ] 본인 명의 은행 계좌 연결 및 입금 완료
- [ ] Paper 최소 4주 이상 운영 로그 확보
- [ ] 손실 제한/중단 절차 문서화
- [ ] 실시간 데이터 플랜 확인(IEX/SIP 등)
- [ ] 라이브 배포 리허설 3회 이상 성공
- [ ] 세금 서류 및 연말 정산 흐름 확인

---

## 12. 공식 참고 링크
- Qlib 초기화/데이터 안내: https://qlib.readthedocs.io/en/v0.6.3/start/initialization.html
- Qlib 데이터 레이어: https://qlib.readthedocs.io/en/v0.9.7/component/data.html
- LEAN `live deploy` 옵션: https://www.quantconnect.com/docs/v2/lean-cli/api-reference/lean-live-deploy
- LEAN Alpaca 라이브 가이드: https://www.quantconnect.com/docs/v2/lean-cli/live-trading/brokerages/alpaca
- LEAN IB 라이브 가이드: https://www.quantconnect.com/docs/v2/lean-cli/live-trading/brokerages/interactive-brokers
- Alpaca 인증/도메인: https://docs.alpaca.markets/docs/authentication
- Alpaca Paper Trading: https://docs.alpaca.markets/docs/trading/paper-trading/
- Alpaca Market Data FAQ(IEX/SIP): https://docs.alpaca.markets/docs/market-data-faq
- Alpaca 실시간 데이터 스트림: https://docs.alpaca.markets/docs/real-time-stock-pricing-data
- Polygon 요금/실시간 여부: https://polygon.io/pricing
- IBKR 계좌 개설 서류: https://www.interactivebrokers.com/en/general/what-you-need-inv.php
- IBKR 입금 안내: https://www.interactivebrokers.com/en/support/fund-my-account.php
- IRS W-8BEN 안내: https://www.irs.gov/instructions/iw8ben
- IRS W-9 안내: https://www.irs.gov/instructions/iw9
- IRS 1099-B 안내: https://www.irs.gov/instructions/i1099b
- FINRA Day Trading/PDT: https://www.finra.org/investors/investing/investment-products/stocks/day-trading
