# 🚗 OpenPilot OPKR — 제네시스 DH 전용 최적화 패치

> **기준 소스**: [openpilotkr/openpilot OPKR 브랜치](https://github.com/openpilotkr/openpilot/tree/OPKR)  
> **대상 차량**: 제네시스 DH (2014~2016년식) · 하네스: Hyundai J  
> **관리자**: g60100  
> **최신 버전**: `v2.0.0` (2025-03-09)  
> **Discord**: [OPKR 공식](https://discord.gg/pppFp2pVW3)

---

## ⚡ 핵심 철학

```
┌──────────────────────────────────────────────────────┐
│  ① 안전 최우선  → 운전자 개입 즉시 우선, MDPS 보호   │
│  ② 성능 최적화  → DH 물리 특성 기반 정밀 튜닝        │
│  ③ 편의 기능    → 저속 조향, 자동 재출발, 스마트 갭  │
└──────────────────────────────────────────────────────┘
```

---

## 📋 버전 히스토리

### ✅ v2.0.0 (2025-03-09) — 전체 최적화 완성판

**수정 파일**: `tunes.py` · `interface.py` · `carcontroller.py` · `values.py`

#### 🔴 안전 기능 (Safety) — v2.0 신규/강화

| 항목 | 원본 OPKR | v1.0.0 | **v2.0.0** | 효과 |
|------|-----------|--------|-----------|------|
| 저속 토크 스케일링 | 없음 | 5단계 | **5단계 정밀화** | 0~30km/h 점진적 보호 |
| 고속 조향각 제한 | 없음 | 5단계 | **5단계 유지** | 100~150km/h 단계 제한 |
| MDPS 오류 임계값 | UI값(기본100) | 60프레임 | **60프레임 유지** | 조기 감지, MDPS 손상 방지 |
| MDPS 토크 차단 | 즉시 차단 | 20프레임 점진 | **20프레임 유지** | 급차단 휘청임 방지 |
| 차선이탈 경고 | 항상 약(1) | 속도 기반(1↔2) | **60km/h↑ 강경고(2)** | 고속 위험 즉시 경고 |
| SmoothSteer maxAngle | UI값 | 80도 | **80도 DH 전용** | MDPS 오류 각도 방지 |
| 긴급 제동 감지 | 기존 유지 | 기존 유지 | **레이더 기반 강화** | 위험 상황 조기 감지 |
| CarInfo min_enable | 15mph | 15mph | **15mph + 2014년식 추가** | 2014년식 지원 확대 |

#### 🟡 성능 기능 (Performance) — v2.0 신규/강화

| 항목 | 원본 OPKR | v1.0.0 | **v2.0.0** | 효과 |
|------|-----------|--------|-----------|------|
| 종방향 튜닝 | OPKR 공통 | GENESIS_DH 전용 | **GENESIS_DH v2 (kd 추가)** | 무거운 차체(2005kg) 맞춤 |
| 횡방향 튜닝 | PID 공통 | PID_DH | **PID_DH v2 (kd 정밀화)** | 조향비 14.4, 휠베이스 3.01m |
| centerToFront | 0.4 (40%) | 0.38 (38%) | **0.38 유지 + 정확한 타이어 강성** | DH 무게중심 정밀 반영 |
| steerActuatorDelay | 0.25s | 0.30s | **0.30s 유지** | DH 구형 MDPS 지연 보상 |
| steerLimitTimer | 0.8s | 1.0s | **1.0s 유지** | 고속 커브 토크 유지 향상 |
| stopAccel | -2.0 m/s² | -2.5 m/s² | **-2.5 m/s² 유지** | 무거운 차체 정밀 정지 |
| stoppingDecelRate | 1.0 | 1.2 | **1.2 유지** | 부드러운 감속 정지 |
| stoppingControl | False | True | **True 유지** | 레이더 기반 정밀 정지 |
| 종방향 딜레이 | 1.0/1.0 | 1.2/1.5 | **1.2/1.5 유지** | DH 구형 SCC 응답 지연 반영 |
| CarControllerParams | 공통 | 공통 | **DH 권장값 주석 + 상세 설명** | 안전 설정 가이드 제공 |
| 핑거프린트 | 5개 패턴 | 없음 | **5개 패턴 + CAN ID 주석** | 차량 오인식 방지 |

#### 🟢 편의 기능 (Convenience) — v2.0 신규/강화

| 항목 | 원본 OPKR | v1.0.0 | **v2.0.0** | 효과 |
|------|-----------|--------|-----------|------|
| minSteerSpeed | 15.42 m/s (55km/h) | 3.3 m/s (12km/h) | **3.3 m/s 유지** | 시내 조향 지원 |
| 재출발 버튼 횟수 | UI 설정값 | 최소 25회 | **최소 25회 유지** | DH SCC 재출발 성공률 향상 |
| 재출발 감지 간격 | 0.1s | 0.08s | **0.08s 유지** | 빠른 재출발 응답 |
| CAN ID 문서화 | 없음 | 없음 | **★ 전체 DH CAN ID 주석** | 향후 커스터마이징 용이 |
| CarInfo 설명 | 최소 정보 | 최소 정보 | **★ DH 차량 특성 상세 주석** | 유지보수 가이드 역할 |

---

### ✅ v1.0.0 (2025-03-09) — 최초 릴리즈

**수정 파일**: `tunes.py` · `interface.py` · `carcontroller.py`

#### 🔴 안전 기능
- 저속 토크 스케일링: 0~30km/h 5단계 점진적 토크 감소
- 고속 조향각 제한: 100~150km/h 속도별 각도 제한
- MDPS 오류 임계값: 100 → 60프레임 조기 감지
- 차선이탈 경고: 고속(60km/h↑) 강경고(2) 적용

#### 🟡 성능 기능  
- LongTunes.GENESIS_DH: DH 전용 종방향 튜닝 (kpV, kdV 최적화)
- LatTunes.PID_DH: DH 전용 PID 튜닝 (kpV, kiV, kdV, kf 최적화)
- 물리 파라미터: centerToFront 0.38, steerActuatorDelay 0.30s

#### 🟢 편의 기능
- minSteerSpeed: 15.42 → 3.3 m/s (저속 조향 지원)
- 재출발 강화: 최소 25회 버튼 신호

---

## ⚙️ 권장 UI 설정값 — 제네시스 DH

> **중요**: 아래 값이 안전과 성능의 균형을 맞춘 DH 최적값입니다.  
> 처음에는 아래 값으로 시작하고, 충분한 테스트 후 개인 취향에 맞게 미세 조정하세요.

### 📍 Tuning Menu (조향 튜닝)

```
┌─────────────────────────────────────────────────────────┐
│  SteerRatio:              14.40  ← DH 기본 조향비        │
│  SteerActuatorDelay:       0.30  ← DH 구형 MDPS 지연     │
│  SteerLimitTimer:          1.00  ← 고속 커브 토크 유지   │
│  TireStiffnessFactor:      0.90  ← DH 구형 타이어 특성   │
│                                                         │
│  ★ SteerMax 설정 ★                                      │
│  SteerMaxDefault:         250    ← DH MDPS 안전 상한     │
│  SteerMaxMax:             350    ← 가변 SteerMax 상한    │
│  SteerDeltaUpDefault:       3    ← 천천히 증가 (안전)    │
│  SteerDeltaUpMax:           5    ← 가변 Delta Up 상한   │
│  SteerDeltaDownDefault:     7    ← 빠르게 감소 (안전)   │
│  SteerDeltaDownMax:        10    ← 가변 Delta Down 상한 │
│                                                         │
│  LatControl Method:       PID    ← PID_DH 자동 적용     │
│    PidKp: 35  (= 0.35 × 100)                            │
│    PidKi: 35  (= 0.035 × 1000)                          │
│    PidKd:  5  (= 0.05 × 100)                            │
│    PidKf:  7  (= 0.00007 × 100000)                      │
└─────────────────────────────────────────────────────────┘
```

### 📍 Driving Menu (주행 설정)

```
┌─────────────────────────────────────────────────────────┐
│  Use Auto Resume at Stop:  ON     ← 정차 후 자동 재출발  │
│  RES count at standstill:  25     ← DH SCC 재출발 횟수   │
│  LaneChange Speed:         60     ← 차선변경 최소 속도   │
│  LaneChange Delay:         Nudge  ← 방향지시 후 대기     │
│  Max Steering Angle:       80     ← DH MDPS 보호 각도    │
│  Stop Steer Assist on Turn: ON    ← 방향지시 시 조향 중단│
│  Use Cruise Button Spamming: ON   ← SCC 속도 제어 방식   │
│  Cruise Start Mode:        Dist+Curv ← 거리+곡률 혼합   │
└─────────────────────────────────────────────────────────┘
```

### 📍 Long Control Menu (종방향 제어, 레이더 하네스 있을 경우)

```
┌─────────────────────────────────────────────────────────┐
│  Use DynamicTR:            ON     ← 동적 추종 거리 사용  │
│  CruiseGap 1:             1.0     ← 시내 (짧은 거리)     │
│  CruiseGap 2:             1.5     ← 도심 (보통 거리)     │
│  CruiseGap 3:             2.0     ← 일반도로 (긴 거리)   │
│  CruiseGap 4:             2.5     ← 고속도로 (매우 긴)   │
│  Adjust Stopping Distance:  0     ← 기본값 (코드 최적화) │
│  Use Early Stop:           ON     ← 조기 정지 신호 감지  │
└─────────────────────────────────────────────────────────┘
```

### 📍 Developer Menu (개발자/고급 설정)

```
┌─────────────────────────────────────────────────────────┐
│  Avoid LKAS Fault:         ON     ← LKAS 오류 방지 활성 │
│  AvoidLKASFaultMaxAngle:   80     ← DH 전용 80도 제한   │
│  AvoidLKASFaultMaxFrame:   60     ← DH 전용 조기 감지   │
│  Steer Wind Down:          ON     ← 점진적 토크 해제    │
│  UseRadarTrack:            ON     ← 레이더 트랙 사용    │
│  Variable SteerMax:        ON     ← 가변 SteerMax 활성  │
│  Variable SteerDelta:      ON     ← 가변 Delta 활성     │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 수정 파라미터 완전 정리

### 📄 tunes.py

#### LongTunes.GENESIS_DH — 종방향(가속/감속) 튜닝

```python
# ── 비례항 (kpV): 속도 올라갈수록 반응 완화 ──────────────────────
kpBP = [0.,  4.,   9.,   17.,  23.,  31.]   # [정지, 15, 32, 61, 83, 112 km/h]
kpV  = [0.6, 0.55, 0.50, 0.45, 0.40, 0.35]
#       ↑정체  ↑시내  ↑도심  ↑국도  ↑고속  ↑초고속

# ── 미분항 (kdV): 정지 시 부드러운 감속 ─────────────────────────
kdBP = [0.,  4.,   9.,   17.,  23.,  31.]
kdV  = [0.3, 0.25, 0.20, 0.15, 0.10, 0.05]
#       ↑강  ↑    ↑    ↑    ↑    ↑약 (DH 무거운 차체 보정)

# ── 불감대 (deadzoneV): 미세 오차 무시 ──────────────────────────
deadzoneBP = [0., 4.]
deadzoneV  = [0.0, 0.05]   # 14km/h 이상: ±0.05 오차 무시

# ── 적분항/피드포워드: SCC 버튼 방식 최적 ───────────────────────
kiV  = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]   # ki 비활성화
kfV  = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]   # kf 전 구간 1.0
```

#### LatTunes.PID_DH — 횡방향(조향) PID 튜닝

```python
# ── 비례항 (kpV): 저속 안전 / 고속 정확도 ───────────────────────
kpBP = [0.,  9.]       # [저속(0~32km/h), 고속(32km/h~)]
kpV  = [0.15, 0.35]    # 저속 약한 반응 → 고속 강한 추적

# ── 적분항 (kiV): 오차 누적 보정 ─────────────────────────────────
kiBP = [0.,   9.]
kiV  = [0.01, 0.035]   # 저속 최소 → 고속 직선 중심 유지

# ── 미분항 (kdV): MDPS 진동 감쇠 ─────────────────────────────────
kdBP = [0.]
kdV  = [0.05]          # DH 구형 MDPS 진동 완화

# ── 피드포워드 (kf): 조향 지연 보상 ─────────────────────────────
kf   = 0.00007         # steerActuatorDelay 0.30s 보상
```

### 📄 interface.py (GENESIS_DH 전용 섹션)

```python
# ── 차량 물리 파라미터 ────────────────────────────────────────────
ret.mass             = 1930. + 75.   # = 2005 kg (차체 + 표준 화물)
ret.wheelbase        = 3.01          # m (긴 편 → 고속 안정)
ret.centerToFront    = 3.01 * 0.38   # 전방 38% 배분 (DH 무게중심)

# ── 조향 안전 파라미터 ────────────────────────────────────────────
ret.minSteerSpeed         = 16.7 * 0.2    # ≈ 3.3 m/s ≈ 12 km/h
ret.steerActuatorDelay    = 0.30          # DH MDPS 지연 보상
ret.steerLimitTimer       = 1.0           # 커브 토크 유지 시간

# ── SmoothSteer DH 전용 설정 ─────────────────────────────────────
ret.smoothSteer.method             = 1      # 각도 기반 감소
ret.smoothSteer.maxSteeringAngle   = 80.0   # 80도 제한
ret.smoothSteer.maxDriverAngleWait = 0.003  # 빠른 개입 감지
ret.smoothSteer.maxSteerAngleWait  = 0.002  # 부드러운 각도 복귀
ret.smoothSteer.driverAngleWait    = 0.001  # 재개 시 충격 방지

# ── 종방향(정지/출발) 파라미터 ───────────────────────────────────
ret.stoppingControl   = True    # 레이더 기반 정밀 정지
ret.vEgoStopping      = 0.5     # 정지 판단 속도 (m/s)
ret.vEgoStarting      = 0.5     # 출발 판단 속도 (m/s)
ret.stopAccel         = -2.5    # 정지 시 제동력 (m/s²)
ret.stoppingDecelRate = 1.2     # 감속률 (m/s³)
ret.longitudinalActuatorDelayLowerBound = 1.2
ret.longitudinalActuatorDelayUpperBound = 1.5
```

### 📄 carcontroller.py (DH 전용 안전 함수)

#### 저속 토크 스케일 (30km/h 이하 안전)

```
속도(km/h) │  0    5    12   20   30+
토크 비율   │  0%   15%  40%  65%  100%
           │
           │  완전  주차장 교차로 시내  정상
           │  차단  안전   안전   저속  작동
```

#### 고속 조향각 제한 (100km/h 이상 안전)

```
속도(km/h)  │   0~100   110   130   150+
최대 조향각  │   80도    60도   45도   20도
            │
            │   일반    고속   고속도  최고속
            │   주행    진입   로주행  안전
```

#### MDPS 오류 처리 (DH 전용)

```
MDPS 오류 누적 → 60프레임(0.6초) 도달
→ cut_steer = True
→ 처음 20프레임: 95%→5% 점진적 토크 감소
→ 이후: 완전 차단 (기존 급차단 대비 부드러운 해제)
```

---

## 📊 속도별 동작 요약표

| 속도 범위 | 조향 작동 | 토크 비율 | 최대 조향각 | 차선이탈 경고 |
|----------|-----------|-----------|------------|-------------|
| 0~12 km/h | 제한 작동 | 0~40% | 80도 | 약(1) |
| 12~30 km/h | 점진 증가 | 40~100% | 80도 | 약(1) |
| 30~60 km/h | 정상 작동 | 100% | 80도 | 약(1) |
| 60~100 km/h | 정상 작동 | 100% | 80도 | **강(2)** |
| 100~110 km/h | 정상 작동 | 100% | **60도** | **강(2)** |
| 110~130 km/h | 정상 작동 | 100% | **45도** | **강(2)** |
| 130~150+ km/h | 정상 작동 | 100% | **20~30도** | **강(2)** |

---

## 📁 파일 구조

```
OpenPilot-OPKR-GENESIS-DH/
├── README.md                        ← ★ 이 파일 (버전 관리 통합)
│
├── selfdrive/car/hyundai/
│   ├── tunes.py        v2.0.0      ← DH 전용 PID/Long 튜닝
│   ├── interface.py    v2.0.0      ← DH 물리 파라미터 + 안전 로직
│   ├── carcontroller.py v2.0.0     ← 저속/고속 안전 + MDPS 보호
│   └── values.py       v2.0.0      ← 핑거프린트 + CAN ID 문서화
│
└── _orig/                           ← 원본 백업 (수정 전)
    ├── tunes_orig.py
    ├── interface_orig.py
    ├── carcontroller_orig.py
    └── values_orig.py
```

---

## 🚀 설치 방법

### ① 파일 직접 교체 (권장)

```bash
# EON/Comma 기기에 SSH 접속
cd /data/openpilot/selfdrive/car/hyundai

# 기존 파일 백업 (필수!)
cp tunes.py tunes.py.bak.$(date +%Y%m%d)
cp interface.py interface.py.bak.$(date +%Y%m%d)
cp carcontroller.py carcontroller.py.bak.$(date +%Y%m%d)
cp values.py values.py.bak.$(date +%Y%m%d)

# 수정 파일 다운로드
BASE="https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai"
curl -o tunes.py         $BASE/tunes.py
curl -o interface.py     $BASE/interface.py
curl -o carcontroller.py $BASE/carcontroller.py
curl -o values.py        $BASE/values.py

# 재부팅 (필수)
sudo reboot
```

### ② Git으로 설치

```bash
cd /data
git clone https://github.com/g60100/OpenPilot-OPKR-GENESIS-DH.git
cd OpenPilot-OPKR-GENESIS-DH

# 백업 및 복사
OPKR_PATH="/data/openpilot/selfdrive/car/hyundai"
for f in tunes.py interface.py carcontroller.py values.py; do
  cp $OPKR_PATH/$f $OPKR_PATH/$f.bak.$(date +%Y%m%d)
  cp selfdrive/car/hyundai/$f $OPKR_PATH/$f
done

sudo reboot
```

---

## ⚠️ 주의사항 및 안전 지침

> **⚡ 이 코드는 연구/개발 목적이며, 실제 도로 주행 시 모든 책임은 사용자에게 있습니다.**

1. **반드시 백업 후 적용** — 원본 파일을 날짜별 `.bak`으로 저장
2. **처음 적용 시 빈 주차장에서 테스트** — 저속 조향 동작 확인 필수
3. **고속도로 테스트 전 시내에서 충분히 테스트** — 안전 확인 순서 준수
4. **MDPS 오류 발생 시** — AvoidLKASFaultMaxAngle을 80 → 70도로 낮추기
5. **재출발 실패 시** — RES count를 25 → 30으로 높이기
6. **차선 유지 불안정 시** — SteerRatio를 14.4 ± 0.5 범위에서 조정
7. **항상 전방 주시, 언제든지 수동 조작 가능 상태 유지**

---

## 🆘 트러블슈팅

| 증상 | 원인 추정 | 해결 방법 |
|------|----------|----------|
| MDPS 오류(ToiUnavail) 빈발 | 조향각 과도 | AvoidLKASFaultMaxAngle: 80→70 |
| 정차 후 재출발 안됨 | SCC 버튼 미인식 | RES count: 25→30 |
| 차선 유지 불안정 (저속) | PID kp 과다 | SteerRatio: 14.4→15.0 시도 |
| 차선 유지 불안정 (고속) | steerActuatorDelay | 0.30→0.35로 높이기 |
| 저속 조향 급격함 | 토크 스케일 문제 | minSteerSpeed 다시 높이기 (16.7*0.3) |
| 고속 커브 흔들림 | kpV 과다 | PidKp: 35→30으로 낮추기 |
| 핑거프린트 미인식 | 차량 변종 | values.py에 패턴 추가 필요 |
| 정지거리 너무 김 | stopAccel | interface.py stopAccel: -2.5→-3.0 |

---

## 📞 문의 및 기여

- **OPKR 공식 Discord**: https://discord.gg/pppFp2pVW3
- **이슈 제보**: GitHub Issues 탭 활용
- **제네시스 DH 사용자**: Discord > Hyundai 채널 > DH 태그

---

*⚡ 항상 전방을 주시하고 언제든지 수동 조작이 가능한 상태를 유지하십시오.*  
*이 소프트웨어를 사용함으로써 발생하는 모든 결과에 대한 책임은 사용자에게 있습니다.*
