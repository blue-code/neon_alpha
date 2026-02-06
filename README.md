# NeonAlpha (Qlib + LEAN)

문서:
- [`docs/DOCS_INDEX_KR.md`](docs/DOCS_INDEX_KR.md) - 문서 인덱스
- [`docs/MANUAL_BEGINNER_KR.md`](docs/MANUAL_BEGINNER_KR.md) - 초보자 입문 매뉴얼
- [`docs/REAL_TRADING_GUIDE_KR.md`](docs/REAL_TRADING_GUIDE_KR.md) - 실전 투자 운영 가이드(계좌/자금/브로커/데이터)
- [`docs/QLIB_RESEARCH_GUIDE_KR.md`](docs/QLIB_RESEARCH_GUIDE_KR.md) - Qlib 리서치/신호 생성 상세
- [`docs/LEAN_EXECUTION_GUIDE_KR.md`](docs/LEAN_EXECUTION_GUIDE_KR.md) - LEAN 집행/백테스트/실거래 상세

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

## 실제 테스트에서 돈으로 이어지는 운영 프로세스
핵심은 "코드 실행"이 아니라 "게이트를 통과한 전략만 소액 실전으로 올리는 운영 체계"입니다.

### 1) 연구/검증 게이트 (Qlib + pipeline + paper)
1. Qlib로 신호를 생성합니다 (`date,symbol,score`).
2. `validate`로 신호 무결성(빈 파일, 중복)을 확인합니다.
3. `pipeline`으로 `생성 -> 검증 -> 모의실행`을 이벤트 체인으로 고정합니다.
4. `paper`로 수익률뿐 아니라 최대낙폭, 거래횟수를 함께 점검합니다.

이 단계에서 `리스크 가드` 파라미터를 먼저 고정합니다.
- `max_positions`
- `min_score`
- `max_weight_per_symbol`
- `max_daily_turnover`

### 2) 집행 게이트 (LEAN 백테스트 + 브로커 Paper)
1. 같은 신호/리스크 파라미터로 LEAN 백테스트를 실행합니다.
2. 브로커 Paper 계좌에서 주문/체결/장애 로그를 확인합니다.
3. 주문 실패율, 체결 지연, 슬리피지가 허용 범위인지 검토합니다.

### 3) 자금 전환 게이트 (소액 라이브 -> 점진 증액)
1. 소액 라이브로 시작합니다(생활비와 분리된 자금).
2. 손실 한도/최대낙폭/주문 실패율 기준을 넘으면 즉시 중단합니다.
3. 일정 기간 안정적으로 운영된 경우에만 단계적으로 자금을 증액합니다.

즉, 돈으로 이어지는 구조는  
`신호 품질 -> 리스크 통제 -> 집행 안정성 -> 소액 실전 검증 -> 점진 증액` 순서입니다.

### Mermaid: End-to-End 운영 플로우
```mermaid
flowchart TD
    A[Qlib 신호 생성\n(date,symbol,score)] --> B[신호 CSV 검증\nvalidate]
    B --> C[pipeline 실행\n생성->검증->모의실행]
    C --> D[로컬 paper 성능 점검\n수익률/최대낙폭/거래수]
    D --> E{연구 게이트 통과?}
    E -- 아니오 --> A
    E -- 예 --> F[LEAN 백테스트\n동일 신호/동일 리스크 파라미터]
    F --> G{집행 게이트 통과?}
    G -- 아니오 --> A
    G -- 예 --> H[브로커 Paper 계좌 리허설\n주문/체결/장애 로그 점검]
    H --> I{운영 안정성 통과?}
    I -- 아니오 --> A
    I -- 예 --> J[소액 Live 배포\nlean live deploy]
    J --> K{손실/장애 한도 준수?}
    K -- 아니오 --> L[즉시 중단\n원인 분석 후 롤백]
    L --> A
    K -- 예 --> M[주간 리뷰 후 점진 증액]
    M --> N[지속 운영\n리스크 가드 상시 적용]
```

---

## 디렉터리 구조
```text
neon_alpha/
├─ docs/
│  ├─ DOCS_INDEX_KR.md
│  ├─ MANUAL_BEGINNER_KR.md
│  ├─ REAL_TRADING_GUIDE_KR.md
│  ├─ QLIB_RESEARCH_GUIDE_KR.md
│  └─ LEAN_EXECUTION_GUIDE_KR.md
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

## LEAN 라이브 배포 실행
사전 조건:
- 브로커 실계좌/페이퍼 계좌 준비
- API 키 발급 완료
- LEAN CLI 로그인 완료

실행(대화형):
```bash
bash run.sh live \
  --lean-project /path/to/your/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv
```

실행(비대화형 예시 - Alpaca):
```bash
bash run.sh live \
  --lean-project /path/to/your/lean-project \
  --signal-csv neon_alpha/data/generated_signals.csv \
  -- \
  --brokerage Alpaca \
  --data-provider-live Alpaca \
  --alpaca-environment live \
  --alpaca-api-key "$ALPACA_API_KEY" \
  --alpaca-api-secret "$ALPACA_API_SECRET"
```

동작:
1. 알고리즘 파일을 LEAN 프로젝트 `main.py`로 복사
2. 신호 파일을 LEAN 프로젝트 `data/signals.csv`로 복사
3. `lean live deploy` 실행

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
