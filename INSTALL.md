# 🚗 제네시스 DH — OpenPilot OPKR 완전 설치 가이드 (A~Z)

> **대상 차량**: 제네시스 DH (2014~2016년식)  
> **대상 기기**: Comma 2 (LeEco Le Pro 3) 또는 Comma 3  
> **소프트웨어**: OPKR 브랜치 + g60100 DH 전용 패치  
> **난이도**: ★★★☆☆ (처음이라도 이 가이드 따라하면 OK)

---

## ⚠️ 시작 전 필수 확인

```
이 소프트웨어는 실험적입니다.
운전 중 항상 전방 주시, 핸들에 손을 올려야 합니다.
모든 법적 책임은 사용자 본인에게 있습니다.
```

---

## 📦 준비물 체크리스트

| 항목 | 내용 | 필수 여부 |
|------|------|----------|
| **Comma 2 또는 Comma 3** | 메인 하드웨어 | ✅ 필수 |
| **hyundai_j 하네스** | 제네시스 DH 전용 (comma.ai 구매) | ✅ 필수 |
| **OBD-C 케이블** | Comma 기기 ↔ 하네스 연결 | ✅ 필수 (동봉) |
| **Wi-Fi 환경** | 초기 설정 및 소프트웨어 설치 | ✅ 필수 |
| **PC 또는 노트북** | SSH 접속 및 파일 복사용 | 🔷 권장 |
| **USB-C 케이블** | PC ↔ Comma 연결 (ADB 사용 시) | 🔷 선택 |
| **Android 태블릿/폰** | BEV 보조 디스플레이 (선택 사항) | ⚪ 선택 |

---

## 🅐 STEP 1 — 차량 준비 (하네스 장착 위치 확인)

### 제네시스 DH 하네스 장착 위치

```
[룸미러 뒤 ADAS 카메라 커버 안쪽]
  ├── 기존 ADAS 커넥터 분리
  ├── hyundai_j 하네스 중간에 삽입
  └── OBD-C 케이블 → 센터콘솔 OBD2 포트까지 배선
```

**OBD2 포트 위치**: 운전석 하단 퓨즈박스 근처 (16핀 사다리꼴 커넥터)

> **주의**: DH는 OBD 포트와 ADAS 카메라 커버 사이 거리가 길어서  
> 케이블을 A필러 → 대시보드 밑 → OBD 포트로 숨겨 배선하세요.

---

## 🅑 STEP 2 — 하네스 물리적 장착

```
1. 룸미러 아래 ADAS 카메라 커버 탈거
   - 손톱으로 아래에서 위로 살짝 당기면 탈거됨
   - 제네시스 DH는 걸쇠 2개 (좌/우)

2. 기존 카메라 커넥터(흰색/회색) 분리
   - 락을 누르면서 당기면 분리됨

3. hyundai_j 하네스 연결
   [차량 측] ─── [하네스 중간] ─── [카메라 측]
   기존커넥터       삽입              원래자리

4. 하네스의 OBD-C 케이블을 
   A필러 몰딩 안쪽으로 숨겨서 OBD2 포트까지 배선

5. OBD2 포트에 하네스 플러그 삽입
   (딸깍 소리 날 때까지)

6. 카메라 커버 복원
```

---

## 🅒 STEP 3 — Comma 기기 마운트 장착

```
1. 마운트 흡착판을 앞유리 룸미러 뒤쪽에 부착
   - 카메라가 도로 정면을 향해야 함
   - 수평 유지 필수 (기울면 캘리브레이션 실패)

2. Comma 기기를 마운트에 딸깍 소리 나게 장착

3. OBD-C 케이블을 Comma 기기에 연결
   - Comma 2: USB-C 포트 (아래쪽)
   - Comma 3: USB-C 포트

4. 케이블을 룸미러 커버 안으로 정리
```

---

## 🅓 STEP 4 — 첫 전원 켜기

```
1. 차량 시동 ON (또는 ACC ON)
   → Comma 기기 자동 부팅 시작

2. 약 60~90초 기다리면 초기 설정 화면 등장
   - "SELECT YOUR CAR" 화면 또는
   - Comma 계정 로그인 화면

3. 정상 부팅 확인:
   ✅ 화면에 도로 카메라 영상 보임
   ✅ 상단에 Wi-Fi/셀 신호 표시
```

---

## 🅔 STEP 5 — Wi-Fi 연결

```
Comma 기기 화면에서:

설정(⚙️) → Network → Wi-Fi
→ 집/스마트폰 핫스팟 Wi-Fi 선택
→ 비밀번호 입력

※ 소프트웨어 다운로드에 Wi-Fi 필수
※ 5GHz Wi-Fi 권장 (속도 빠름)
```

---

## 🅕 STEP 6 — 기존 OpenPilot 제거 (재설치 시)

이미 다른 버전이 설치되어 있다면 먼저 제거:

```
방법 A) UI에서 제거:
설정(⚙️) → Software → Uninstall → 확인

방법 B) SSH로 제거:
ssh comma@192.168.x.x  (기기 IP 확인 후)
cd /data
mv openpilot openpilot_bak  # 백업
reboot
```

---

## 🅖 STEP 7 — OPKR 소프트웨어 설치 (URL 방식 — 가장 쉬운 방법)

```
Comma 기기 초기 설정 화면 또는
설정 → Software → Install Custom Software 에서:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPKR 안정 버전 URL 입력:
https://opkr.o-r.kr/fork/opkr
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

(테스트 버전: https://opkr.o-r.kr/fork/test)

→ Enter/확인 누르면 자동 다운로드 & 설치 시작
→ 약 5~10분 소요
→ 완료 후 자동 재부팅
```

---

## 🅗 STEP 8 — SSH로 DH 전용 패치 파일 적용

OPKR 기본 설치 후, 제네시스 DH 최적화 파일을 덮어씌웁니다.

### 8-1. Comma 기기 IP 주소 확인

```
Comma 화면 상단에 IP 주소 표시됨
예: 192.168.1.105
또는:
설정 → Network → IP Address 확인
```

### 8-2. PC에서 SSH 접속

```bash
# Windows: PowerShell 또는 PuTTY
# Mac/Linux: 터미널

ssh comma@192.168.1.105
# 비밀번호: (없음, 그냥 Enter)
# 또는 비밀번호: comma
```

### 8-3. DH 전용 파일 다운로드 및 적용

```bash
# Comma 기기 SSH 접속 후:

# 1) 현재 파일 백업
cd /data/openpilot/selfdrive/car/hyundai
cp carcontroller.py carcontroller.py.orig
cp interface.py     interface.py.orig
cp tunes.py         tunes.py.orig
cp values.py        values.py.orig

# 2) g60100 DH 전용 파일 다운로드
cd /data/openpilot/selfdrive/car/hyundai

curl -O https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai/carcontroller.py
curl -O https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai/interface.py
curl -O https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai/tunes.py
curl -O https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai/values.py

# 3) 적용 확인
ls -la *.py
echo "✅ DH 전용 파일 적용 완료"

# 4) 재부팅
sudo reboot
```

### 8-4. SSH 접속이 안 될 때 (SSH 키 문제)

```bash
# Comma 2에서 구버전 SSH 키 사용:
설정 → Developer → Use Legacy SSH Key → ON → 재부팅 후 재시도

# 또는 SSH 포트 명시:
ssh -p 8022 comma@192.168.1.105
```

---

## 🅘 STEP 9 — UI 권장 설정값 입력

재부팅 후 Comma 화면에서 아래 값들을 설정합니다.

### 조향(Steer) 설정 — Tuning Menu

```
SteerMaxAdj          → 250   ← DH MDPS 안전 상한 (350 초과 절대 금지!)
SteerMaxBaseAdj      → 200   ← 일반 주행 기본 토크
SteerDeltaUpAdj      →   3   ← 토크 증가 속도 (느릴수록 안전)
SteerDeltaDownAdj    →   7   ← 토크 감소 속도 (UpAdj × 2 이상!)
SteerActuatorDelay   →  30   ← (→ 0.30초) DH 구형 MDPS 응답 지연 보상
SteerLimitTimer      → 100   ← (→ 1.00초) MDPS 과부하 방지 타이머
SteerRatio           → 1440  ← (→ 14.40) DH 조향비
TireStiffnessFactor  → 100   ← 기본값 유지
```

### 횡방향 제어 방식 — Tuning Menu

```
LateralControlMethod → 0 (PID)
← 선택 시 DH 전용 PID_DH 자동 적용됨
  kpV=[0.15, 0.35], kf=0.00007
```

### 종방향(Long) 설정 — Tuning Menu

```
RadarDisable → OFF   ← DH는 SCC 레이더 사용
CruiseStartMode → 1  ← Dist+Curv 권장
```

### 안전 관련 — Driving Menu

```
Use Auto Resume at Stop → ON    ← 정체 구간 자동 재출발
Change Cruise Gap at Stop → ON  ← 출발 시 갭 1단계로 빠른 출발
LaneChange Speed → 60 km/h      ← 차선변경 최소 속도
```

---

## 🅙 STEP 10 — 차량 핑거프린트 확인 (차량 인식)

```
차량 시동 ON → OpenPilot 화면에서:

정상: 화면 상단에 "Genesis (DH)" 표시
      또는 "GENESIS DH" 인식

미인식 시:
설정 → Developer → CAR Force Recognition
→ "GENESIS (DH)" 선택 → 재부팅
```

### 핑거프린트 패턴 (5가지)

```
DH는 연식/옵션에 따라 CAN 패턴이 다릅니다:
- 패턴 1: 2014 기본형
- 패턴 2: 스마트크루즈 옵션 (CAN 1281, 1379 추가)
- 패턴 3: 풀옵션 (CAN 912, 1268, 1437 추가)
- 패턴 4: 2015 마이너체인지
- 패턴 5: 2016 최신형 (CAN 1371)

→ 자동 인식 안 되면 Force Recognition 사용
```

---

## 🅚 STEP 11 — 캘리브레이션

```
최초 설치 또는 마운트 위치 변경 후 필수!

1. 직선 도로에서 30~100km/h로 주행
2. 화면에 "CALIBRATING" 표시 → 정상
3. 약 500m~2km 직선 주행하면 완료
4. 완료 후 "CALIBRATION COMPLETE" 표시

⚠️ 캘리브레이션 중에는 OP 개입 안 됨 (정상)
⚠️ 마운트가 수평이어야 정확한 캘리브레이션 가능
```

---

## 🅛 STEP 12 — 드라이버 모니터링(DMS) 설정

```
Comma 2는 전면 카메라로 운전자 얼굴 인식:

설정 → Toggles → Enable Driver Monitoring → ON

눈 감김 감도 조정 (얼굴 인식 안 될 때):
설정 → UI Menu → Normal EYE Threshold → 값 낮춤
설정 → UI Menu → Blink Threshold → 값 낮춤

안경 착용자: E2E EYE Threshold도 조정
```

---

## 🅜 STEP 13 — 첫 주행 전 최종 점검

```
✅ 화면에 "Genesis (DH)" 차종 인식 확인
✅ 캘리브레이션 완료 확인
✅ 전방 카메라 영상 정상 (도로가 보임)
✅ 레이더 신호 확인 (선행차 감지 시 점 표시)
✅ 조향각 0.0도 확인 (직선 도로에서)
   → 아니면: Str Angle Adjust 값 조정
✅ Wi-Fi 연결 상태 확인 (로그 업로드용)
```

---

## 🅝 STEP 14 — OpenPilot 첫 작동 방법

```
조건:
- 차속 24 km/h 이상 (OP 활성화 최소 속도)
- 차선 인식 상태
- SCC(스마트크루즈) 켜진 상태

작동 순서:
1. SCC 버튼 누름 → SCC 대기 상태
2. SET 버튼으로 속도 설정
3. OP가 자동으로 횡방향(조향) 제어 시작
4. 화면 상단 핸들 아이콘이 파란색 → 정상 작동 중

해제:
- 브레이크 밟기
- 핸들 강하게 돌리기 (토크 초과)
- CANCEL 버튼
```

---

## 🅞 STEP 15 — UAG 급발진 방지 기능 동작 확인

```
v3.1.0 핵심 안전 기능:

정상 주행 시: 화면에 아무 표시 없음

이상 가속 감지 시 (2.5 m/s² 초과):
단계 1 (0.3초): ⚠️ 경고음 발생
단계 2 (0.5초): "가속 이상 감지" 음성 경고 + SCC 감속
단계 3 (1.0초): 비상 감속 (-3.0 m/s²) + 로그 자동 저장

로그 저장 위치:
/data/media/0/openpilot_logs/uag_날짜시간.json
```

---

## 🅟 STEP 16 — 정기 업데이트 방법

### 방법 A) UI에서 업데이트 (권장)

```
설정 → Software → Check for Updates
→ 새 버전 있으면 "UPDATE" 버튼 표시
→ 클릭하면 자동 다운로드 & 재부팅
```

### 방법 B) SSH로 수동 업데이트

```bash
ssh comma@192.168.x.x
cd /data/openpilot
git pull
sudo reboot
```

### DH 전용 패치 재적용 (OPKR 업데이트 후)

```bash
# OPKR이 업데이트되면 DH 파일이 덮어씌워질 수 있음
# 재적용 필요 시:

cd /data/openpilot/selfdrive/car/hyundai
curl -O https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai/carcontroller.py
curl -O https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai/interface.py
curl -O https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai/tunes.py
curl -O https://raw.githubusercontent.com/g60100/OpenPilot-OPKR-GENESIS-DH/main/selfdrive/car/hyundai/values.py
sudo reboot
```

---

## 🅠 STEP 17 — Wi-Fi 핫스팟으로 태블릿 BEV 연결 (선택)

Comma 기기의 데이터를 Android 태블릿으로 스트리밍하는 고급 기능입니다.

```bash
# Comma 기기에서:
설정 → Network → HotSpot on Boot → ON → 재부팅

# 태블릿에서:
Wi-Fi → "comma_XXXXXXXX" 연결
비밀번호: commaai

# PC/태블릿 브라우저에서:
http://192.168.43.1:8080/bev.html
```

> 상세 내용은 **tablet_wifi.html** 대시보드 참조

---

## 🅡 자주 묻는 질문 (FAQ)

### Q1. 차량이 인식되지 않아요 (핑거프린트 실패)

```
A. 시동을 완전히 끄고 30초 후 재시동
B. 설정 → Developer → CAR Force Recognition → GENESIS (DH) 선택
C. SSH로: cd /data/openpilot && python3 selfdrive/debug/can_logger.py
   → CAN 데이터가 들어오는지 확인
```

### Q2. 조향이 한쪽으로 쏠려요

```
A. 설정 → Tuning → Str Angle Adjust
B. 직선 도로에서 조향각 확인 (0.0이 되어야 함)
C. 값을 ±0.5 단위로 조금씩 조정
```

### Q3. MDPS 오류(ToiUnavail)가 자주 발생해요

```
A. SteerMaxAdj 값 낮추기: 250 → 220
B. SteerDeltaUpAdj 값 낮추기: 3 → 2
C. carcontroller.py의 MDPS 60프레임 보호 기능 작동 중인지 확인
```

### Q4. 저속(30km/h 이하)에서 조향이 안 돼요

```
A. 정상입니다 — DH는 12km/h 이상부터 단계적으로 조향 활성화
B. 완전히 활성화: 24km/h 이상
C. 설정 → Developer → SmartMDPS → ON 으로 더 낮출 수 있음
```

### Q5. Comma 2에서 AI 속도가 느려요

```
A. 정상입니다 — Comma 2는 15~20fps (Comma 3은 25~30fps)
B. 설정 → Developer → Use Smart Prebuilt → ON
   → 부팅 속도 향상 (컴파일 스킵)
```

### Q6. 급가속/급제동이 불편해요

```
A. tunes.py의 GENESIS_DH kpV 값 낮추기 (0.60→0.50, 0.35→0.30)
B. 또는 UI에서 CruiseGap을 1단계 늘리기
C. vEgoStopping, stopAccel 값 조정 (SSH 필요)
```

### Q7. 업데이트 후 DH 기능이 사라졌어요

```
A. OPKR 업데이트로 DH 파일이 덮어씌워진 것
B. STEP 8 의 curl 명령어로 재적용
C. 향후: git pull 후 자동 재적용 스크립트 개발 예정
```

---

## 🅢 문제 발생 시 로그 확인

```bash
# SSH 접속 후:

# OpenPilot 실시간 로그
tmux a -t main

# 특정 프로세스 로그
cat /tmp/logmessage | tail -50

# UAG 급발진 로그
ls /data/media/0/openpilot_logs/
cat /data/media/0/openpilot_logs/uag_*.json

# CAN 통신 디버그
cd /data/openpilot
python3 selfdrive/debug/can_logger.py

# 핑거프린트 디버그
python3 selfdrive/debug/get_fingerprint.py
```

---

## 🅣 원복(롤백) 방법

```bash
# SSH 접속 후:

# 방법 1: 이전 버전으로 롤백
설정 → Software → Cancel Git Pull

# 방법 2: 원본 파일로 복원 (백업한 경우)
cd /data/openpilot/selfdrive/car/hyundai
cp carcontroller.py.orig carcontroller.py
cp interface.py.orig     interface.py
cp tunes.py.orig         tunes.py
cp values.py.orig        values.py
sudo reboot

# 방법 3: 완전 초기화
설정 → Software → Parameter Init  ← 설정값만 초기화
설정 → Software → Git Reset        ← 코드 원본으로
```

---

## 🅤 하드웨어 관리

```
Comma 기기 보호:
- 주차 후 직사광선 노출 금지 (과열 원인)
- 강한 햇빛에는 마운트에서 분리해 보관
- 설정 → UI Menu → EON Detach Alert Sound → Korean
  → 시동 끄면 "기기를 분리해 주세요" 음성 알림

배터리 관리 (Comma 2):
- 설정 → UI Menu → Enable Battery Charging Control → ON
- Min: 30%, Max: 80% 권장 (배터리 수명 보호)

발열 관리:
- 여름철 대시보드 위 직사광선 → 30분 내 과열 경고 가능
- 외기온도 35도 이상 시 주의
```

---

## 🅥 커뮤니티 & 지원

| 채널 | 링크 | 용도 |
|------|------|------|
| **OPKR Discord** | https://discord.gg/pppFp2pVW3 | OPKR 공식 지원 |
| **Comma Discord** | https://discord.comma.ai | 영문 글로벌 커뮤니티 |
| **네이버 카페** | 오픈파일럿 한국 카페 검색 | 한국어 지원 |
| **이 저장소 Issues** | https://github.com/g60100/OpenPilot-OPKR-GENESIS-DH/issues | DH 전용 이슈 |

---

## 🅦 전체 설치 순서 요약 (Quick Reference)

```
A) 준비물 확인 (하네스, Comma 기기, OBD-C)
B) 차량 ADAS 커버 탈거
C) hyundai_j 하네스 ADAS 커넥터에 삽입
D) OBD-C 케이블 A필러로 배선
E) OBD2 포트에 연결
F) Comma 기기 마운트 유리에 부착 (룸미러 뒤)
G) OBD-C → Comma 기기 연결
H) 차량 시동 → Comma 자동 부팅
I) Wi-Fi 연결
J) URL 입력: https://opkr.o-r.kr/fork/opkr
K) 설치 완료 후 자동 재부팅 대기
L) SSH 접속: ssh comma@[IP주소]
M) DH 전용 파일 4개 curl로 다운로드
N) sudo reboot
O) UI에서 SteerMax 250, DeltaUp 3, DeltaDown 7 설정
P) LateralControlMethod → 0 (PID) 선택
Q) CAR Force Recognition → GENESIS (DH)
R) 직선 도로 캘리브레이션 주행 (약 1~2km)
S) 드라이버 모니터링 설정
T) 24km/h 이상에서 SCC 켜고 첫 작동 테스트
U) 조향 쏠림 있으면 Str Angle Adjust 보정
V) 급가속/급제동 느낌 있으면 tunes.py kp 미세 조정
W) 업데이트: 설정 → Software → Check for Updates
X) 문제 발생 시 tmux 로그 확인
Y) 원복 필요 시 Cancel Git Pull 또는 .orig 파일 복원
Z) 정기 드라이브 로그 백업 및 커뮤니티 피드백 공유
```

---

## 📋 DH 전용 파일 버전 정보

| 파일 | 버전 | 핵심 기능 |
|------|------|-----------|
| `carcontroller.py` | v3.1.0 | UAG 급발진방지, 음성경고, 자동로그, MDPS 60프레임 보호 |
| `interface.py` | v3.1.0 | DH 물리파라미터(1930kg, 3.01m), 저속 조향 12km/h |
| `tunes.py` | v3.1.0 | GENESIS_DH kp 0.60~0.35, PID_DH kf=0.00007 |
| `values.py` | v3.1.0 | CarControllerParams, 5개 핑거프린트 패턴 |

---

*최종 수정: 2025-03-09 | 작성: g60100*  
*이 가이드는 실제 제네시스 DH 주행 경험을 바탕으로 작성되었습니다.*
