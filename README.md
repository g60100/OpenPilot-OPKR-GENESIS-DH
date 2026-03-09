# OpenPilot OPKR — 제네시스 DH (2014~2016) 전용 포크

> **버전**: v3.1.0 | **수정자**: g60100 | **최종 수정**: 2025-03-09  
> **기준 소스**: [openpilotkr/openpilot](https://github.com/openpilotkr/openpilot) OPKR 브랜치

---

## 📖 설치 가이드

> **➡️ [INSTALL.md — A부터 Z까지 완전 설치 가이드 보기](./INSTALL.md)**

하네스 장착부터 첫 주행까지 모든 단계를 사진 설명 수준으로 기술한 전체 설치 문서입니다.

---

## 📌 개요

이 저장소는 **제네시스 DH (2014~2016년식, 하네스: hyundai_j)** 전용으로 최적화된 OpenPilot OPKR 포크입니다.

구형 SCC 버튼 스패밍 방식, 무거운 차체(1930 kg), 구형 MDPS 특성에 맞게 모든 파라미터를 실험적으로 조정하였습니다.

---

## ✨ 주요 특징

| 기능 | 상태 | 설명 |
|------|------|------|
| **UnintendedAccelGuard (UAG)** | ✅ 구현 | 급발진 방지: 비작동 가속 감지 + 3단계 에스컬레이션 |
| **저속 조향 활성화** | ✅ 구현 | 12 km/h부터 단계적 토크 활성화 (원본 55 km/h → 낮춤) |
| **고속 조향각 제한** | ✅ 구현 | 100 km/h 이상에서 안전 조향각 자동 제한 |
| **MDPS 오류 보호** | ✅ 구현 | 60프레임 연속 감지 → 점진적 토크 컷 |
| **정밀 정지 제어** | ✅ 구현 | vEgoStopping 0.5 m/s, stopAccel -2.5 m/s² |
| **DH 전용 종방향 튜닝** | ✅ 구현 | 속도별 kp 점진적 감소 (0.60→0.35) |
| **DH 전용 PID 조향 튜닝** | ✅ 구현 | kpV=[0.15, 0.35], kf=0.00007 |
| **폰/태블릿 Wi-Fi BEV 스트리밍** | 📋 계획 | Comma 2 → Android 기기 WebSocket 연결 |

---

## 🚀 빠른 시작

### 1. 요구 사항

- **차량**: 2014~2016 제네시스 DH (쿠페/세단)
- **하드웨어**: Comma 2 또는 Comma 3 (하네스: hyundai_j)
- **소프트웨어**: OPKR 기반 OpenPilot

### 2. 설치

```bash
# SSH로 Comma 기기 접속
ssh comma@192.168.43.1  # (Wi-Fi 핫스팟 연결 시)

# 저장소 클론
cd /data/openpilot
git clone https://github.com/YOUR_USERNAME/OpenPilot-OPKR-GENESIS-DH .

# 또는 기존 설치 위치에 파일 복사
cp selfdrive/car/hyundai/carcontroller.py /data/openpilot/selfdrive/car/hyundai/
cp selfdrive/car/hyundai/interface.py     /data/openpilot/selfdrive/car/hyundai/
cp selfdrive/car/hyundai/tunes.py         /data/openpilot/selfdrive/car/hyundai/
cp selfdrive/car/hyundai/values.py        /data/openpilot/selfdrive/car/hyundai/

# 재시작
sudo reboot
```

### 3. UI 권장 설정값

아래 값을 OpenPilot UI에서 직접 입력하세요:

| 파라미터 | 권장값 | 설명 |
|----------|--------|------|
| SteerMaxAdj | **250** | MDPS 안전 상한 (350 초과 금지!) |
| SteerMaxBaseAdj | **200** | 일반 주행 기본 토크 |
| SteerDeltaUpAdj | **3** | 토크 증가 속도 (느릴수록 안전) |
| SteerDeltaDownAdj | **7** | 토크 감소 속도 (UpAdj×2 이상 필수) |
| SteerActuatorDelayAdj | **30** (→ 0.30s) | DH 구형 MDPS 응답 지연 보상 |
| SteerLimitTimerAdj | **100** (→ 1.00s) | MDPS 과부하 방지 타이머 |
| LateralControlMethod | **0** (PID) | DH 전용 PID_DH 자동 선택됨 |

---

## 📁 수정 파일 목록

```
selfdrive/car/hyundai/
├── carcontroller.py   v3.1.0  ★ 핵심 — UAG, 음성경고, 자동로그
├── interface.py       v3.1.0  ★ DH 물리파라미터, UAG 연동
├── tunes.py           v3.1.0  ★ DH 전용 종/횡 튜닝 파라미터
└── values.py          v3.1.0  ★ DH CarControllerParams, 핑거프린트
```

---

## 🛡️ UnintendedAccelGuard (급발진 방지)

`carcontroller.py` v3.1.0에서 구현된 핵심 안전 기능입니다.

### 동작 원리

```
[정상 가속 범위: 0~2.0 m/s²]
        ↓ 2.5 m/s² 초과 감지
[1단계: 0.3s] → 경고음 + 로그 기록
        ↓ 0.5s 지속
[2단계: 0.5s] → SCC 감속 명령 + 음성 경고 "가속 이상 감지"
        ↓ 1.0s 지속
[3단계: 1.0s] → 비상 SCC 스팸 -3.0 m/s² + 자동 로그 저장
```

### 주요 파라미터

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `UAG_ACCEL_THRESHOLD` | 2.5 m/s² | 감지 임계값 (ACCEL_MAX 2.0보다 0.5 여유) |
| `UAG_WARN_TIME` | 0.3 s | 1단계: 경고만 발생 |
| `UAG_INTERVENTION_TIME` | 0.5 s | 2단계: SCC 감속 개입 |
| `UAG_EMERGENCY_TIME` | 1.0 s | 3단계: 비상 감속 |
| `UAG_EMERGENCY_DECEL` | -3.0 m/s² | 비상 감속 가속도 |

### 로그 저장 위치

```
/data/media/0/openpilot_logs/
└── uag_YYYYMMDD_HHMMSS.json  ← 급발진 감지 시 자동 생성
```

---

## 🎛️ 제네시스 DH 전용 튜닝

### 종방향 (가속/감속) — `LongTunes.GENESIS_DH`

| 속도 | kp | kd | 비고 |
|------|-----|-----|------|
| 0 km/h (정지) | 0.60 | 0.30 | 정체 구간 민감 반응 |
| 15 km/h | 0.55 | 0.25 | 시가지 서행 |
| 32 km/h | 0.50 | 0.20 | 국도 안정 |
| 61 km/h | 0.45 | 0.15 | 고속도로 진입 |
| 83 km/h | 0.40 | 0.10 | 고속 안정 |
| 112 km/h+ | 0.35 | 0.05 | 과가속 방지 |

### 횡방향 (조향) — `LatTunes.PID_DH`

| 파라미터 | 저속 (0~32 km/h) | 고속 (32+ km/h) |
|----------|-----------------|-----------------|
| kp | 0.15 | 0.35 |
| ki | 0.010 | 0.035 |
| kd | 0.05 (전 구간) | — |
| kf | 0.00007 (전 구간) | — |

> **참고**: LateralControlMethod=0 (PID) 선택 시 DH 전용 PID_DH가 자동 적용됩니다.

---

## 📱 폰/태블릿 Wi-Fi BEV 연결 (Comma 2 지원)

### Comma 2 하드웨어 스펙

| 항목 | Comma 2 (LeEco Le Pro 3) | Comma 3 |
|------|--------------------------|---------|
| CPU | Snapdragon 820 (2.15 GHz) | Snapdragon 845 |
| RAM | 4~6 GB | 4 GB |
| GPU | Adreno 530 | Adreno 630 |
| AI 추론 | ~15~20 fps | ~25~30 fps |
| Wi-Fi | 802.11ac (5 GHz) ✅ | 802.11ac (5 GHz) ✅ |
| 핫스팟 | ✅ 지원 | ✅ 지원 |

**→ Comma 2에서도 Wi-Fi 태블릿 BEV 연결 가능!**

### 연결 방법 (30~60분)

```bash
# 1. Comma 2에서 Wi-Fi 핫스팟 활성화
#    네트워크명: comma_XXXXXXXX  |  비밀번호: commaai

# 2. 태블릿/폰을 해당 Wi-Fi에 연결

# 3. Comma 2 SSH 접속 (다른 기기에서)
ssh comma@192.168.43.1

# 4. Python WebSocket 서버 설치
pip3 install websockets==10.4

# 5. BEV 스트리밍 서버 실행
python3 /data/openpilot/bev_ws_server.py &

# 6. 태블릿 브라우저에서 접속
# http://192.168.43.1:8080/bev.html
```

### bev_ws_server.py 구조

```python
# Comma cereal messaging → WebSocket 브릿지
import asyncio, websockets
from cereal import messaging

async def stream_bev(websocket, path):
    sm = messaging.SubMaster(['radarState', 'modelV2', 'carState'])
    while True:
        sm.update(0)
        # radarState에서 선행차/물체 좌표 추출
        # JSON으로 직렬화하여 WebSocket 전송
        await websocket.send(json.dumps(bev_data))
        await asyncio.sleep(0.033)  # 30 fps
```

---

## 📊 핑거프린트 패턴 (제네시스 DH)

총 5개 패턴으로 모든 연식/옵션 대응:

| 패턴 | 특징 | 대상 |
|------|------|------|
| 패턴 1 | 기본 세트 | 2014 기본형 |
| 패턴 2 | +CAN 1281, 1379 | 스마트크루즈 옵션 |
| 패턴 3 | +CAN 912, 1268, 1437 | 풀옵션 |
| 패턴 4 | +CAN 1425 | 2015 마이너체인지 |
| 패턴 5 | +CAN 1371 | 2016 최신 풀옵션 |

---

## ⚠️ 주의사항 및 면책

1. **이 포크는 실험적 소프트웨어입니다.** 실제 도로 사용 시 항상 운전자가 주도권을 유지하세요.
2. **MDPS 보호**: SteerMaxAdj를 350 이상으로 설정하지 마세요. MDPS 영구 손상 위험이 있습니다.
3. **UAG는 보조 안전장치**입니다. SCC/ACC 시스템 자체 오류나 전기적 문제는 별도로 처리됩니다.
4. **Comma 2 사용자**: AI 추론 속도가 Comma 3보다 낮아(15~20 fps) 응답이 약간 늦을 수 있습니다.
5. **법적 책임**: 이 소프트웨어 사용으로 발생하는 모든 문제에 대해 개발자는 책임을 지지 않습니다.

---

## 🔗 관련 대시보드

아래 HTML 파일들은 `/home/user/preview_dashboard/`에서 확인할 수 있습니다:

| 파일 | 내용 |
|------|------|
| `index.html` | Genesis DH v3.1.0 메인 대시보드 (6탭) |
| `expand.html` | 개발 로드맵 대시보드 (7탭) |
| `phone3d.html` | 폰 화면 3D 박스 구현 가능성 분석 (6탭+시뮬) |
| `tablet_wifi.html` | Comma 2 Wi-Fi 태블릿 연결 가이드 (7탭+시뮬) |

---

## 📈 버전 히스토리

| 버전 | 날짜 | 주요 변경 |
|------|------|-----------|
| v3.1.0 | 2025-03-09 | UAG 3단계 에스컬레이션, 음성경고, 자동로그, 고속 조향각 제한, MDPS 오류 보호, interface.py UAG 연동 |
| v2.0.0 | 2025-03-09 | CarControllerParams DH 최적화, 핑거프린트 검증, CAN ID 주석 |
| v1.0.0 | 2025-03-09 | 초기 DH 전용 포크 생성, 종/횡 튜닝 기초 파라미터 |

---

## 🤝 기여

버그 리포트, 파라미터 제안, 실주행 피드백은 GitHub Issues로 등록해 주세요.  
제네시스 DH 오너분들의 실데이터 공유를 환영합니다!

---

*이 프로젝트는 OpenPilot 커뮤니티의 집단 지성을 기반으로 합니다.*  
*Original OpenPilot: [commaai/openpilot](https://github.com/commaai/openpilot) | OPKR: [openpilotkr/openpilot](https://github.com/openpilotkr/openpilot)*
