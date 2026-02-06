# NeonAlpha 문서 인덱스

## 1. 문서 목적
이 디렉터리는 NeonAlpha의 운영 문서를 한 곳에 모아,  
`리서치(Qlib) -> 검증 -> 집행(LEAN) -> 실전 운영` 흐름을 빠르게 재현하기 위한 기준점이다.

## 2. 권장 읽기 순서
1. [`MANUAL_BEGINNER_KR.md`](MANUAL_BEGINNER_KR.md)  
초보자 기준으로 전체 구조를 한 번에 이해한다.
2. [`QLIB_RESEARCH_GUIDE_KR.md`](QLIB_RESEARCH_GUIDE_KR.md)  
Qlib에서 실데이터 기반 신호를 만들고 검증하는 절차를 확정한다.
3. [`LEAN_EXECUTION_GUIDE_KR.md`](LEAN_EXECUTION_GUIDE_KR.md)  
신호를 LEAN 백테스트/라이브 집행으로 연결하는 운영 기준을 확정한다.
4. [`REAL_TRADING_GUIDE_KR.md`](REAL_TRADING_GUIDE_KR.md)  
브로커 계좌, 입출금, 세금, 실거래 운영 런북을 점검한다.

## 3. 파트별 역할 정의
- `Qlib`: 리서치/팩터 신호 생성
- `LEAN`: 이벤트 기반 집행/백테스트/실거래 연동

## 4. 공통 핵심 기능(모든 파트에서 확인)
### 이벤트 기반 오케스트레이션
- `pipeline` 명령이 `생성 -> 검증 -> 모의실행`을 이벤트 체인으로 처리한다.
- 구현 위치: `src/neon_alpha/cli.py`, `src/neon_alpha/event_bus.py`

### 리스크 가드
- 최대 보유 종목 수(`max_positions`)
- 최소 점수(`min_score`)
- 종목당 최대 비중(`max_weight_per_symbol`)
- 일일 회전율 제한(`max_daily_turnover`)
- 구현 위치: `src/neon_alpha/risk.py`, `execution/lean/HybridQlibLeanAlgorithm.py`

### 페이퍼 실행 루프
- 실거래 전 로컬 모의 성능을 반복 점검한다.
- 구현 위치: `src/neon_alpha/paper.py`, `bash run.sh paper`

## 5. 빠른 명령 요약
```bash
# 1) Qlib 신호 생성
bash run.sh qlib --provider-uri ~/.qlib/qlib_data/us_data --start 2022-01-01 --end 2025-12-31

# 2) 신호 검증
bash run.sh validate --signal-csv neon_alpha/data/generated_signals.csv

# 3) 로컬 페이퍼 시뮬레이션
bash run.sh paper --signal-csv neon_alpha/data/generated_signals.csv --price-csv neon_alpha/data/sample_prices.csv

# 4) 이벤트 체인으로 한번에 실행
bash run.sh pipeline --mode qlib --provider-uri ~/.qlib/qlib_data/us_data --price-csv neon_alpha/data/sample_prices.csv

# 5) LEAN 백테스트/라이브
bash run.sh lean --lean-project /path/to/lean-project --signal-csv neon_alpha/data/generated_signals.csv
bash run.sh live --lean-project /path/to/lean-project --signal-csv neon_alpha/data/generated_signals.csv
```
