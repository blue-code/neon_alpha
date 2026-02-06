# NeonAlpha 퀀트 초보자 완전 매뉴얼 (고등학생 버전)

## 0. 이 문서는 누구를 위한가?
- 파이썬을 조금 아는 사람
- “퀀트가 뭔지”는 들어봤지만 직접 돌려본 적이 없는 사람
- 미국 주식 자동매매를 안전하게 연습해보고 싶은 사람

이 문서 목표는 단 1개입니다.  
`NeonAlpha`를 **직접 실행하고**, 결과를 **해석하고**, 다음에 무엇을 할지 **스스로 판단**할 수 있게 만드는 것.

---

## 1. 5분 요약
NeonAlpha는 두 도구를 합친 프로젝트입니다.

- `Qlib`: 데이터 분석, 점수(신호) 만들기 담당
- `LEAN`: 만든 신호대로 실제 매매 엔진처럼 실행 담당

흐름:
1. 종목별 점수 CSV 만들기
2. CSV가 정상인지 검증하기
3. 모의 실행으로 수익률/손실 위험 확인하기
4. LEAN 백테스트로 실행 엔진 점검하기

중요: 이 프로젝트는 “돈 자동복사기”가 아닙니다.  
좋은 신호를 설계하고 검증하는 사람의 실력이 핵심입니다.

---

## 2. 퀀트 개념을 아주 쉽게
### 2-1. 퀀트란?
수학/통계/코드로 투자 규칙을 만들고, 감정 대신 규칙대로 매매하는 방식입니다.

### 2-2. `signal`(신호)란?
종목 점수표라고 생각하면 쉽습니다.

- 점수 높음: “상대적으로 더 사고 싶다”
- 점수 낮음: “덜 사고 싶다/빼고 싶다”

예시:
```csv
date,symbol,score
2025-01-02,AAPL,0.92
2025-01-02,MSFT,0.77
```

### 2-3. 왜 리스크 제한이 필요할까?
전략이 좋아 보여도 한 번에 크게 잃을 수 있습니다.  
그래서 아래 제한을 둡니다.

- 최대 보유 종목 수
- 종목당 최대 비중
- 하루에 얼마나 포트폴리오를 바꿀지(회전율)

---

## 3. 실행 전 준비물
필수:
- macOS/Linux 터미널 (Windows는 WSL 권장)
- `python3` 설치

선택:
- `Qlib` 데이터 (실제 신호 생성용)
- `LEAN` CLI (백테스트 실행용)

---

## 4. 폴더 구조 이해
핵심만 알면 됩니다.

```text
neon_alpha/
├─ run.sh                      # 실행 명령 모음
├─ setup.sh                    # 환경 설치
├─ data/
│  ├─ sample_signals.csv       # 예시 신호
│  └─ sample_prices.csv        # 예시 가격
├─ src/neon_alpha/
│  ├─ cli.py                   # 명령어 진입점
│  ├─ signal_io.py             # 신호 읽기/쓰기
│  ├─ risk.py                  # 리스크 제한 규칙
│  ├─ paper.py                 # 로컬 모의 실행
│  └─ event_bus.py             # 이벤트 기반 파이프라인
└─ execution/lean/HybridQlibLeanAlgorithm.py
```

---

## 5. 처음 설치 (가장 중요)
프로젝트 루트(`/.../neon_alpha`)에서:

```bash
bash setup.sh
```

옵션:
```bash
# Qlib까지 설치
bash setup.sh --with-qlib

# LEAN CLI까지 설치
bash setup.sh --with-lean

# 둘 다
bash setup.sh --with-qlib --with-lean
```

설치가 끝나면 가상환경이 `neon_alpha/.venv`에 준비됩니다.

---

## 6. 실행 시나리오 A: 완전 초보 루트 (샘플 데이터)
### 6-1. 샘플 신호 만들기
```bash
bash run.sh sample
```

출력 파일:
- `neon_alpha/data/generated_signals.csv`

### 6-2. 신호 검증
```bash
bash run.sh validate --signal-csv neon_alpha/data/generated_signals.csv
```

정상이라면 마지막에 `OK`가 나옵니다.

### 6-3. 모의 실행(페이퍼)
```bash
bash run.sh paper \
  --signal-csv neon_alpha/data/generated_signals.csv \
  --price-csv neon_alpha/data/sample_prices.csv
```

출력 예시 지표:
- `total_return`: 전체 수익률
- `cagr`: 연환산 수익률 추정
- `max_drawdown`: 최대 낙폭(가장 중요)
- `trades`: 리밸런싱 발생 횟수

### 6-4. 이벤트 파이프라인 한 번에
```bash
bash run.sh pipeline --mode sample --price-csv neon_alpha/data/sample_prices.csv
```

이 명령은 아래를 자동으로 연결합니다.
1. 신호 생성
2. 신호 검증
3. 모의 실행

---

## 7. 실행 시나리오 B: 실제 Qlib 데이터로 신호 만들기
Qlib US 데이터가 준비된 경우:

```bash
bash run.sh qlib \
  --provider-uri ~/.qlib/qlib_data/us_data \
  --start 2022-01-01 \
  --end 2025-12-31 \
  --symbols AAPL MSFT NVDA AMZN GOOGL META SPY \
  --output neon_alpha/data/generated_signals.csv
```

그 다음은 동일:
```bash
bash run.sh validate --signal-csv neon_alpha/data/generated_signals.csv
bash run.sh paper --signal-csv neon_alpha/data/generated_signals.csv --price-csv neon_alpha/data/sample_prices.csv
```

---

## 8. LEAN 백테스트 실행
사전 조건:
- `lean` 설치/로그인 완료
- LEAN 프로젝트 경로 준비

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

내부 동작:
1. LEAN `main.py` 갱신
2. `data/signals.csv` 복사
3. `lean backtest` 실행

---

## 9. 리스크 파라미터를 쉽게 설명
### `--max-positions`
최대 몇 종목까지 들고 갈지  
예: 3이면 상위 점수 3개만 보유

### `--min-score`
이 점수보다 낮으면 매수 대상에서 제외

### `--max-weight-per-symbol`
한 종목 비중 상한  
예: 0.4면 40% 이상 안 넣음

### `--max-daily-turnover`
하루 리밸런싱 변화 제한  
값이 낮을수록 매매 빈도와 비용을 줄이는 방향

---

## 10. 결과를 볼 때 꼭 보는 3가지
1. `total_return`만 보지 말고 `max_drawdown` 같이 보기  
2. `trades`가 너무 많으면 수수료/슬리피지에 취약할 수 있음  
3. 샘플에서 좋게 나와도 실전 성과를 보장하지 않음

---

## 11. 자주 나는 오류와 해결
### 오류: `virtualenv not found`
원인: 아직 설치 안 함  
해결:
```bash
bash setup.sh
```

### 오류: `lean command not found`
원인: LEAN CLI 미설치  
해결:
```bash
bash setup.sh --with-lean
```

### 오류: `Qlib import failed`
원인: pyqlib 미설치 또는 데이터 없음  
해결:
```bash
bash setup.sh --with-qlib
```
그리고 `--provider-uri` 경로 확인

### 오류: `Signal CSV is empty`
원인: 신호 생성 실패/기간 문제  
해결: 기간, 심볼, 데이터 유무 재확인

---

## 12. 초보자 추천 학습 순서 (7일 플랜)
### Day 1
- `setup.sh`, `run.sh sample`, `run.sh validate`

### Day 2
- `paper` 지표 의미 이해 (`cagr`, `max_drawdown`)

### Day 3
- `risk.py` 파라미터 바꿔서 결과 변화 관찰

### Day 4
- `pipeline` 이벤트 흐름 로그 읽기

### Day 5
- Qlib 실제 데이터 붙여서 신호 생성

### Day 6
- LEAN 백테스트까지 연결

### Day 7
- 전략 변경 실험(점수 공식 바꾸기) + 성능 비교표 작성

---

## 13. 마지막 체크리스트
- [ ] 샘플 루트 실행 성공
- [ ] 신호 CSV 스키마 이해
- [ ] 리스크 파라미터 의미 이해
- [ ] 페이퍼 지표 해석 가능
- [ ] LEAN 백테스트 1회 이상 실행

여기까지 되면 “초보자” 단계는 이미 통과입니다.  
다음 단계는 **신호 품질 개선(알파 연구)**입니다.
