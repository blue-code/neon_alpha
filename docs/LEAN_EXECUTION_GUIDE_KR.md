# LEAN 집행/백테스트/실거래 연동 상세 가이드

## 1. 문서 목적
이 문서는 `LEAN: 이벤트 기반 집행/백테스트/실거래 연동` 파트를 실무 기준으로 정리한다.  
목표는 Qlib 신호를 LEAN 환경에서 재현 가능하게 집행하고, 백테스트와 라이브 운영 절차를 고정하는 것이다.

## 2. LEAN 파트의 책임 범위
LEAN 파트에서 확정해야 하는 것:
- 신호 파일을 주문 로직에 정확히 연결
- 백테스트와 라이브 환경의 파라미터 동기화
- 리스크 가드가 집행 레벨에서 강제되는지 확인

LEAN 파트에서 하지 않는 것:
- 신호 공식 자체 연구(이는 Qlib 파트 책임)
- 브로커 계좌 개설/KYC/세금 신고

## 3. 현재 알고리즘 동작(코드 기준)
관련 파일:
- `execution/lean/HybridQlibLeanAlgorithm.py`

핵심 로직:
1. `signal_csv`에서 일자별 점수 로드
2. `min_score` 이상만 필터
3. 상위 종목을 `max_positions`만큼 선택
4. 종목당 비중은 `max_weight_per_symbol` 상한 적용
5. 일일 회전율이 `max_daily_turnover` 초과면 기존 보유 유지
6. 미국장 시작 후 5분에 1회 리밸런싱

## 4. 백테스트 표준 절차
실행:
```bash
bash run.sh lean \
  --lean-project /path/to/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv \
  --long-count 3 \
  --max-positions 3 \
  --min-score -1.0 \
  --max-weight-per-symbol 0.4 \
  --max-daily-turnover 0.8
```

`run.sh lean` 동작:
1. LEAN 프로젝트 `main.py` 갱신
2. LEAN 프로젝트 `data/signals.csv` 갱신
3. `lean backtest` 실행

백테스트 점검 항목:
- 주문 체결 누락 여부
- 보유 종목 수가 `max_positions`를 넘지 않는지
- 회전율 제한이 실제로 작동하는지

## 5. 라이브 배포 표준 절차
실행(대화형):
```bash
bash run.sh live \
  --lean-project /path/to/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv \
  --long-count 3 \
  --max-positions 3 \
  --min-score -1.0 \
  --max-weight-per-symbol 0.4 \
  --max-daily-turnover 0.8
```

실행(브로커 옵션 전달):
```bash
bash run.sh live \
  --lean-project /path/to/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv \
  --max-positions 3 \
  --max-weight-per-symbol 0.4 \
  -- \
  --brokerage Alpaca \
  --data-provider-live Alpaca \
  --alpaca-environment live \
  --alpaca-api-key "$ALPACA_API_KEY" \
  --alpaca-api-secret "$ALPACA_API_SECRET"
```

`run.sh live` 동작:
1. LEAN 프로젝트 `main.py`/`data/signals.csv` 갱신
2. 리스크 파라미터를 `lean live deploy --parameter ...`로 전달
3. 라이브 엔진 배포

## 6. 이벤트 기반 오케스트레이션 (LEAN 연동 관점)
요청 항목 반영: `pipeline` 체인은 LEAN 이전 단계의 사전 게이트로 사용한다.

권장 운용:
1. `pipeline`으로 `생성 -> 검증 -> 모의실행` 수행
2. 결과 합격 시 `lean` 백테스트 실행
3. 백테스트 합격 시 `live` 배포

표준 명령 흐름:
```bash
bash run.sh pipeline --mode qlib --provider-uri ~/.qlib/qlib_data/us_data --price-csv neon_alpha/data/sample_prices.csv
bash run.sh lean --lean-project /path/to/lean-project --signal-csv neon_alpha/data/generated_signals.csv
bash run.sh live --lean-project /path/to/lean-project --signal-csv neon_alpha/data/generated_signals.csv
```

## 7. 리스크 가드 (집행 강제 규칙)
요청 항목 반영: 아래 4개는 LEAN 집행 단계에서 실제 주문에 직접 영향을 준다.

- `max_positions`: 보유 종목 수 상한 강제
- `min_score`: 점수 컷오프 미달 종목 제외
- `max_weight_per_symbol`: 단일 종목 쏠림 제한
- `max_daily_turnover`: 과도한 리밸런싱 억제

검증 방법:
1. 극단값 테스트(예: `max_positions=1`, `max_weight_per_symbol=0.2`)
2. 백테스트 주문 로그와 포트폴리오 비중 확인
3. 의도와 다른 체결이 있으면 파라미터/알고리즘 로직 재검토

## 8. 페이퍼 실행 루프 (실거래 전 필수)
요청 항목 반영: 실거래 진입 전 `paper` 루프를 운영 기준으로 고정한다.

운영 규칙(권장):
1. 최소 4주 이상 페이퍼 운영
2. 주문 실패율, 재시도, 지연 로그 기록
3. 하루 손실 한도 초과 시 자동 중단 절차 검증
4. 페이퍼 결과가 안정적일 때만 라이브 소액 진입

참고:
- 로컬 `bash run.sh paper`는 전략 반응성 점검용
- 브로커 Paper 계좌는 주문 체결 흐름 점검용
- 둘 다 통과해야 라이브 전환

## 9. 장애 대응 최소 런북
중단 기준 예시:
- 일손실 한도 초과
- 주문 실패율 급증
- 데이터 지연/연결 단절 지속

중단 절차:
1. `lean live stop <project>`
2. 브로커에서 미체결 취소/필요 시 수동 청산
3. 원인 분석 전 재배포 금지
4. API 키 교체 필요 여부 점검

## 10. LEAN 파트 완료 체크리스트
- [ ] `lean` 백테스트 3회 이상 재현 성공
- [ ] 리스크 가드 4개 파라미터 동작 확인
- [ ] `pipeline -> lean -> live` 순서 문서화 완료
- [ ] Paper 계좌 운영 로그 4주 이상 확보
- [ ] 라이브 배포/중단 리허설 완료
