# NeonAlpha (Qlib + LEAN)

초보자용 전체 매뉴얼:
- [`MANUAL_BEGINNER_KR.md`](MANUAL_BEGINNER_KR.md)

## 프로젝트 목적
미국 주식 시장에서 아래 2가지 강점을 결합하기 위한 독립 프로젝트입니다.

- `Qlib`: 리서치/팩터 신호 생성
- `LEAN`: 이벤트 기반 집행/백테스트/실거래 연동

운영 흐름은 다음 3단계입니다.

1. Qlib로 신호 생성 (`date,symbol,score`)
2. 신호 CSV 검증
3. LEAN에서 신호 기반 리밸런싱 실행

또한 `vnpy` 프로젝트에서 검증된 운영 아이디어를 함께 반영했습니다.

- **이벤트 기반 오케스트레이션**: `pipeline` 명령으로 생성→검증→모의실행을 이벤트 체인으로 처리
- **리스크 가드**: 최대 보유 종목 수, 최소 점수, 종목당 최대 비중, 일일 회전율 제한
- **페이퍼 실행 루프**: 실거래 전 로컬 모의 성능 점검

`pipeline`은 가능하면 `vnpy.event.EventEngine`을 사용하고, 독립 실행 환경에서는 내장 동기 이벤트 버스로 자동 fallback 됩니다.

---

## 디렉터리 구조
```text
neon_alpha/
├─ data/
│  └─ sample_signals.csv
│  └─ sample_prices.csv
├─ execution/
│  └─ lean/
│     └─ HybridQlibLeanAlgorithm.py
├─ src/
│  └─ neon_alpha/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ event_bus.py
│     ├─ generator.py
│     ├─ paper.py
│     ├─ risk.py
│     └─ signal_io.py
├─ .env.example
├─ pyproject.toml
├─ requirements.txt
├─ setup.sh
└─ run.sh
```

---

## 빠른 시작
### 1) 환경 준비
프로젝트 루트에서:
```bash
cd neon_alpha
bash setup.sh
```

옵션:
```bash
# Qlib까지 함께 설치
bash setup.sh --with-qlib

# LEAN CLI까지 함께 설치
bash setup.sh --with-lean

# 둘 다 설치
bash setup.sh --with-qlib --with-lean
```

### 2) 샘플 신호 생성
```bash
bash run.sh sample
```

출력:
- `neon_alpha/data/generated_signals.csv`

### 3) 신호 검증
```bash
bash run.sh validate --signal-csv neon_alpha/data/generated_signals.csv
```

### 4) 로컬 페이퍼(모의) 실행
```bash
bash run.sh paper \
  --signal-csv neon_alpha/data/generated_signals.csv \
  --price-csv neon_alpha/data/sample_prices.csv
```

### 5) 이벤트 기반 파이프라인 실행
```bash
bash run.sh pipeline --mode sample --price-csv neon_alpha/data/sample_prices.csv
```

---

## Qlib 신호 생성 실행
Qlib US 데이터가 준비된 상태에서:
```bash
bash run.sh qlib \
  --provider-uri ~/.qlib/qlib_data/us_data \
  --start 2022-01-01 \
  --end 2025-12-31 \
  --symbols AAPL MSFT NVDA AMZN GOOGL META SPY \
  --output neon_alpha/data/generated_signals.csv
```

기본 신호 로직:
- `momentum_20 = 20일 수익률`
- `reversal_5 = 5일 수익률`
- `score = momentum_20 - reversal_5`

---

## LEAN 백테스트 실행
사전 조건:
- `lean` CLI 설치/로그인 완료
- 대상 LEAN 프로젝트 디렉터리 준비

실행:
```bash
bash run.sh lean \
  --lean-project /path/to/your/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv \
  --long-count 3 \
  --max-positions 3 \
  --min-score -1.0 \
  --max-weight-per-symbol 0.4 \
  --max-daily-turnover 0.8
```

동작:
1. 알고리즘 파일을 LEAN 프로젝트 `main.py`로 복사
2. 신호 파일을 LEAN 프로젝트 `data/signals.csv`로 복사
3. `lean backtest` 실행

리스크 관련 LEAN 파라미터:
- `max_positions`
- `min_score`
- `max_weight_per_symbol`
- `max_daily_turnover`

---

## 신호 스키마
필수 컬럼:
- `date`: `YYYY-MM-DD`
- `symbol`: 예) `AAPL`
- `score`: float

예시:
```csv
date,symbol,score
2025-01-02,AAPL,0.92
2025-01-02,MSFT,0.77
```

---

## 참고
- 실거래 전 워크포워드 검증, 수수료/슬리피지 반영, 리스크 한도 적용은 필수입니다.
- 본 프로젝트는 실행 인프라 템플릿이며, 수익은 전략 우위(알파)에 의해 결정됩니다.
