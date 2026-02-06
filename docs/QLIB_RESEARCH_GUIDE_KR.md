# Qlib 리서치/신호 생성 상세 가이드

## 1. 문서 목적
이 문서는 `Qlib: 리서치/팩터 신호 생성` 파트를 실무 수준으로 고정하기 위한 가이드다.  
목표는 `실데이터 기반 신호 생성 -> 신호 검증 -> 모의 성능 점검`을 반복 재현하는 것이다.

## 2. Qlib 파트의 책임 범위
Qlib 파트에서 확정해야 하는 것:
- 어떤 데이터로 신호를 만들지
- 어떤 점수 공식을 사용할지
- 신호 품질을 어떤 기준으로 합격/불합격 처리할지

Qlib 파트에서 하지 않는 것:
- 브로커 주문 집행
- 라이브 계좌 자금/권한 관리
- 거래소 연결 안정성 관리

## 3. 현재 코드 기준 신호 생성 구조
관련 파일:
- `src/neon_alpha/generator.py`
- `src/neon_alpha/signal_io.py`

현재 기본 로직:
1. Qlib에서 `close` 시계열 조회
2. 종목별 `momentum_20` 계산(20일 수익률)
3. 종목별 `reversal_5` 계산(5일 수익률)
4. `score = momentum_20 - reversal_5`
5. `date,symbol,score` CSV 출력

## 4. 실데이터 확보 방법
## 4-1. Qlib Provider 데이터
예시 경로:
- `~/.qlib/qlib_data/us_data`

실행 예시:
```bash
bash run.sh qlib \
  --provider-uri ~/.qlib/qlib_data/us_data \
  --start 2022-01-01 \
  --end 2025-12-31 \
  --symbols AAPL MSFT NVDA AMZN GOOGL META SPY \
  --output data/generated_signals.csv
```

## 4-2. 데이터 품질 점검 포인트
- 시간대 기준(미국 ET) 일관성
- 분할/배당 반영 정책(조정주가 여부)
- 결측치/휴장일 처리 기준
- 종목 코드 정규화(대문자 통일)

## 5. 신호 검증(무결성 게이트)
관련 파일:
- `src/neon_alpha/cli.py` (`validate`)

검증 항목:
- 행 수 0 여부
- `(date,symbol)` 중복 여부
- 날짜/종목 수 집계 정상 여부

실행:
```bash
bash run.sh validate --signal-csv data/generated_signals.csv
```

합격 기준 예시:
- `rows > 0`
- `duplicates = 0`
- 분석 대상 기간/종목이 의도와 일치

## 6. 이벤트 기반 오케스트레이션 (pipeline)
요청 항목 반영: `pipeline` 이벤트 체인을 Qlib 파트에서도 표준 절차로 사용한다.
`pipeline`은 가능하면 `vnpy.event.EventEngine`을 사용하고, 독립 실행 환경에서는 내장 동기 이벤트 버스로 자동 fallback 된다.

관련 파일:
- `src/neon_alpha/cli.py`
- `src/neon_alpha/event_bus.py`

이벤트 흐름:
1. `eSignalRequested`
2. `eSignalGenerated`
3. `eSignalValidated`
4. `ePipelineDone`

실행 예시:
```bash
bash run.sh pipeline \
  --mode qlib \
  --provider-uri ~/.qlib/qlib_data/us_data \
  --start 2022-01-01 \
  --end 2025-12-31 \
  --symbols AAPL MSFT NVDA AMZN GOOGL META SPY \
  --price-csv data/sample_prices.csv
```

의미:
- Qlib 신호 생성, 검증, 모의실행을 수동 단계 분리 없이 체인으로 고정
- 실패 지점을 이벤트 단계 단위로 분리해 디버깅 가능

## 7. 리스크 가드 (Qlib 연구 단계 적용)
요청 항목 반영: 리스크 가드는 집행 단계 전, 연구 단계에서 먼저 조정한다.

핵심 파라미터:
- `max_positions`: 최대 보유 종목 수
- `min_score`: 최소 점수 필터
- `max_weight_per_symbol`: 종목당 최대 비중
- `max_daily_turnover`: 일일 회전율 제한

연구 단계 적용 방법:
1. 같은 신호에 대해 파라미터만 바꿔 `paper` 반복
2. `cagr`, `max_drawdown`, `trades` 변화 비교
3. 과최적화(특정 구간만 잘 맞는 현상) 여부 점검

## 8. 페이퍼 실행 루프 (Qlib 검증 루프)
요청 항목 반영: 실거래 전 로컬 모의 성능 점검을 Qlib 합격 기준에 포함한다.

관련 파일:
- `src/neon_alpha/paper.py`

실행 예시:
```bash
bash run.sh paper \
  --signal-csv data/generated_signals.csv \
  --price-csv data/sample_prices.csv \
  --max-positions 3 \
  --min-score -1.0 \
  --max-weight-per-symbol 0.4 \
  --max-daily-turnover 0.8
```

반복 운영 규칙(권장):
1. 신호 생성
2. 검증
3. 페이퍼 실행
4. 지표 기록
5. 파라미터/신호식 수정
6. 다시 1로 반복

## 9. 성능 평가 기준(최소)
- `total_return`: 참고 지표
- `cagr`: 성장성 지표
- `max_drawdown`: 필수 리스크 지표
- `trades`: 과도한 매매 여부 확인

실무 주의:
- `total_return` 단독 합격 금지
- `max_drawdown`과 동시 판단 필수
- `trades` 과다 전략은 수수료/슬리피지 취약

## 10. LEAN 인계 산출물 규칙
- 기본 인계 파일: `data/generated_signals.csv`
- 필수 스키마: `date,symbol,score`
- 인계 직전 필수 명령:
```bash
bash run.sh validate --signal-csv data/generated_signals.csv
```
- 인계 조건: `rows > 0`, `duplicates = 0`

## 11. Qlib 파트 완료 체크리스트
- [ ] 실데이터 경로/품질 확인 완료
- [ ] 신호 CSV 검증 통과(`rows > 0`, `duplicates = 0`)
- [ ] `pipeline` 체인 3회 이상 정상 실행
- [ ] 리스크 가드 파라미터 스윕 완료
- [ ] 페이퍼 루프 결과표(수익/낙폭/거래수) 확보
- [ ] LEAN 전달용 최종 신호 파일 확정

다음 문서:
- [`LEAN_EXECUTION_GUIDE_KR.md`](LEAN_EXECUTION_GUIDE_KR.md)
