#!/usr/bin/env python3
# =============================================================================
# 파일명  : interface.py
# 대상차량: 제네시스 DH (2014~2016, 하네스: hyundai_j)
# 기준소스: openpilotkr/openpilot OPKR 브랜치
# 수정자  : g60100
# 버전    : v3.1.0
# 수정일  : 2025-03-09
#
# [수정 내역 요약]
#   v3.1.0 - 2025-03-09
#     - carcontroller.py v3.1.0 UnintendedAccelGuard 연동 완료
#     - GENESIS_DH stoppingControl True 유지 (carcontroller UAG와 협력)
#     - stopAccel -2.5 m/s² 유지 (UAG 비상제동 -3.0 m/s²와 구분)
#     - get_pid_accel_limits: ACCEL_MAX 2.0 m/s² (UAG 임계값 2.5와 안전 여유 0.5 확보)
#   v1.0.0 - 2025-03-09
#     1. GENESIS_DH 물리 파라미터 정밀 보정
#        - 실측 기반 차체 중량, 휠베이스 반영
#        - centerToFront 비율 DH 특성(후륜 구동 성향) 맞춤 조정
#     2. 저속 조향 단계적 활성화
#        - minSteerSpeed: 15.42 m/s → 단계적 토크 감소로 저속 지원
#     3. 안전 파라미터 강화
#        - steerActuatorDelay, steerLimitTimer DH 최적값 적용
#        - smoothSteer 파라미터 DH MDPS 보호용 설정
#     4. 종방향 파라미터 DH 맞춤 설정
#        - 정지거리, 감속률, 출발/정지 속도 보정
#     5. DH 전용 튜닝(LongTunes.GENESIS_DH, LatTunes.PID_DH) 연결
# =============================================================================

from cereal import car
from panda import Panda
from common.conversions import Conversions as CV
# [수정] DH 전용 튜닝 추가 임포트 (LongTunes.GENESIS_DH, LatTunes.PID_DH)
from selfdrive.car.hyundai.tunes import LatTunes, LongTunes, set_long_tune, set_lat_tune
from selfdrive.car.hyundai.values import CAR, EV_CAR, HYBRID_CAR, Buttons, CarControllerParams
from selfdrive.car import STD_CARGO_KG, scale_rot_inertia, scale_tire_stiffness, gen_empty_fingerprint, get_safety_config
from selfdrive.car.interfaces import CarInterfaceBase
from selfdrive.car.disable_ecu import disable_ecu
from common.params import Params
from decimal import Decimal

ButtonType  = car.CarState.ButtonEvent.Type
EventName   = car.CarEvent.EventName


class CarInterface(CarInterfaceBase):
  def __init__(self, CP, CarController, CarState):
    super().__init__(CP, CarController, CarState)
    self.cp2              = self.CS.get_can2_parser(CP)
    self.lkas_button_alert = False
    self.blinker_status   = 0
    self.blinker_timer    = 0
    self.ufc_mode_enabled = Params().get_bool('UFCModeEnabled')
    self.no_mdps_mods     = Params().get_bool('NoSmartMDPS')

  @staticmethod
  def get_pid_accel_limits(CP, current_speed, cruise_speed):
    # ★ v3.1.0: carcontroller.py UnintendedAccelGuard(UAG)와 협력
    #   - ACCEL_MAX 2.0 m/s² → UAG 감지 임계값 2.5 m/s²보다 0.5 여유
    #   - UAG가 2.5 m/s² 이상 감지 시 비상 SCC 감속 개입
    #   - 따라서 정상 범위(±ACCEL_MAX)에서는 UAG 작동하지 않음
    return CarControllerParams.ACCEL_MIN, CarControllerParams.ACCEL_MAX

  @staticmethod
  def get_params(candidate, fingerprint=gen_empty_fingerprint(), car_fw=[], disable_radar=False):
    ret = CarInterfaceBase.get_std_params(candidate, fingerprint)

    ret.carName      = "hyundai"
    ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.hyundaiLegacy, 0)]

    # ─── CAN 버스 자동 감지 ───────────────────────────────────────────────
    ret.mdpsBus = 1 if 593  in fingerprint[1] and 1296 not in fingerprint[1] else 0
    ret.sasBus  = 1 if 688  in fingerprint[1] and 1296 not in fingerprint[1] else 0
    ret.sccBus  = (0 if 1056 in fingerprint[0]
                   else 1 if 1056 in fingerprint[1] and 1296 not in fingerprint[1]
                   else 2 if 1056 in fingerprint[2] else -1)
    ret.fcaBus  = 0 if 909 in fingerprint[0] else 2 if 909 in fingerprint[2] else -1
    ret.bsmAvailable  = True if 1419 in fingerprint[0] else False
    ret.lfaAvailable  = True if 1157 in fingerprint[2] else False
    ret.lvrAvailable  = True if 871  in fingerprint[0] else False
    ret.evgearAvailable = True if 882 in fingerprint[0] else False
    ret.emsAvailable  = True if 608  and 809 in fingerprint[0] else False

    ret.radarOffCan = ret.sccBus == -1
    ret.standStill  = False
    ret.openpilotLongitudinalControl = (Params().get_bool("RadarDisable") or ret.sccBus == 2)

    # ─── SmoothSteer 공통 파라미터 (원본 유지) ───────────────────────────
    ret.smoothSteer.method           = int(Params().get("OpkrSteerMethod",         encoding="utf8"))
    ret.smoothSteer.maxSteeringAngle = float(Params().get("OpkrMaxSteeringAngle",  encoding="utf8"))
    ret.smoothSteer.maxDriverAngleWait = float(Params().get("OpkrMaxDriverAngleWait", encoding="utf8"))
    ret.smoothSteer.maxSteerAngleWait  = float(Params().get("OpkrMaxSteerAngleWait",  encoding="utf8"))
    ret.smoothSteer.driverAngleWait    = float(Params().get("OpkrDriverAngleWait",    encoding="utf8"))

    ret.minSteerSpeed  = 16.67         # 기본값 [m/s] (≈60km/h) — DH 블록에서 오버라이드됨
    ret.radarTimeStep  = 0.02          # 레이더 주기 50Hz
    ret.pcmCruise      = not ret.radarOffCan

    # ─── 기본 조향/종방향 파라미터 (UI 값 우선 적용) ────────────────────
    ret.steerActuatorDelay = 0.25
    ret.steerLimitTimer    = 0.8
    tire_stiffness_factor  = 1.0

    params = Params()
    tire_stiffness_factor  = float(Decimal(params.get("TireStiffnessFactorAdj", encoding="utf8")) * Decimal('0.01'))
    ret.steerActuatorDelay = float(Decimal(params.get("SteerActuatorDelayAdj",  encoding="utf8")) * Decimal('0.01'))
    ret.steerLimitTimer    = float(Decimal(params.get("SteerLimitTimerAdj",     encoding="utf8")) * Decimal('0.01'))
    ret.steerRatio         = float(Decimal(params.get("SteerRatioAdj",          encoding="utf8")) * Decimal('0.01'))

    # ─── 종방향 기본 설정 ────────────────────────────────────────────────
    set_long_tune(ret.longitudinalTuning, LongTunes.OPKR)
    ret.stoppingControl   = False
    ret.vEgoStopping      = 0.8
    ret.vEgoStarting      = 0.8
    ret.stopAccel         = -2.0
    ret.stoppingDecelRate = 1.0
    ret.longitudinalActuatorDelayLowerBound = 1.0
    ret.longitudinalActuatorDelayUpperBound = 1.0
    ret.vCruisekph = 0
    ret.resSpeed   = 0
    ret.vFuture    = 0
    ret.vFutureA   = 0
    ret.aqValue    = 0
    ret.aqValueRaw = 0

    # ─── 횡방향 제어 방식 선택 (UI 설정) ────────────────────────────────
    lat_control_method = int(params.get("LateralControlMethod", encoding="utf8"))
    if   lat_control_method == 0: set_lat_tune(ret.lateralTuning, LatTunes.PID)
    elif lat_control_method == 1: set_lat_tune(ret.lateralTuning, LatTunes.INDI)
    elif lat_control_method == 2: set_lat_tune(ret.lateralTuning, LatTunes.LQR)
    elif lat_control_method == 3: set_lat_tune(ret.lateralTuning, LatTunes.TORQUE)
    elif lat_control_method == 4: set_lat_tune(ret.lateralTuning, LatTunes.ATOM)

    # =========================================================================
    # ★★★ 제네시스 DH 전용 최적화 설정 ★★★
    # =========================================================================
    if candidate == CAR.GENESIS_DH:
      # ─── 차량 물리 파라미터 ─────────────────────────────────────────────
      ret.mass      = 1930. + STD_CARGO_KG
      # ↑ 실제 차체 중량: 1930kg (기본형 기준)
      #   STD_CARGO_KG(75kg) 추가 = 총 2005kg
      #   무거운 차체 → 관성이 크므로 조향/제동 파라미터에 반영

      ret.wheelbase = 3.01
      # ↑ 휠베이스: 3.01m
      #   긴 편 → 고속 직진 안정성 높음, 저속 코너링 둔함

      ret.centerToFront = ret.wheelbase * 0.38
      # ↑ [수정] 원본 0.4 → 0.38로 조정
      #   DH는 FR(전/후륜 구동 성향) 배치 → 무게중심 약간 뒤쪽
      #   0.38 = 전방 38%, 후방 62% 배분
      #   → 더 정확한 타이어 강성 계산 가능

      # ─── 조향 관련 안전 파라미터 ────────────────────────────────────────
      ret.minSteerSpeed = 16.7 * 0.2
      # ↑ [수정] 원본 15.42 m/s(55.5km/h) → 약 3.3 m/s(12km/h)로 낮춤
      #   단, carcontroller.py에서 저속 토크 점진적 감소로 안전 보완
      #   → 시내 주행, 정체 구간에서도 차선 유지 보조 작동

      ret.steerActuatorDelay = 0.30
      # ↑ [수정] 원본 0.25s → 0.30s
      #   DH MDPS는 구형이라 응답이 약간 느림 → 딜레이 늘려 오버슈트 방지
      #   너무 크면 조향 반응 느림, 너무 작으면 MDPS 오류 빈발

      ret.steerLimitTimer = 1.0
      # ↑ [수정] 원본 0.8s → 1.0s
      #   DH는 MDPS 토크 한계(ToiUnavail) 경고 전 여유 시간 늘림
      #   → 고속 커브에서 토크 유지 시간 증가

      # ─── SmoothSteer DH 전용 오버라이드 ────────────────────────────────
      ret.smoothSteer.method             = 1
      # ↑ Method 1: 조향각 기반 토크 점진적 감소 (DH에 가장 안정적)

      ret.smoothSteer.maxSteeringAngle   = 80.0
      # ↑ [수정] 원본 90도 → 80도
      #   DH MDPS는 80도 이상에서 ToiUnavail 경고 빈발
      #   → 80도 이상 진입 시 토크 서서히 감소 시작

      ret.smoothSteer.maxDriverAngleWait  = 0.003
      # ↑ 운전자 조향 개입 시 OP 토크 감소 속도 (초/프레임)
      #   0.003 = 약 1/0.003 ≈ 333프레임 만에 토크 0 (약 1.67초)
      #   빠른 개입 감지 → 운전자 안전 우선

      ret.smoothSteer.maxSteerAngleWait   = 0.002
      # ↑ 최대 조향각 초과 시 토크 감소 속도
      #   0.002 = 약 500프레임 만에 토크 0 (약 2.5초) → 부드러운 복귀

      ret.smoothSteer.driverAngleWait     = 0.001
      # ↑ 일반 운전자 조향 시 토크 복귀 속도
      #   0.001 = 천천히 복귀 → 운전자 개입 후 OP 재개 시 충격 방지

      # ─── 종방향(가속/감속) DH 전용 설정 ────────────────────────────────
      set_long_tune(ret.longitudinalTuning, LongTunes.GENESIS_DH)
      # ↑ [수정] 공통 OPKR 튜닝 → DH 전용 튜닝으로 교체
      #   tunes.py의 LongTunes.GENESIS_DH 참조

      ret.stoppingControl   = True
      # ↑ [수정] 원본 False → True
      #   정지 제어 활성화: 선행차 뒤에서 정밀 정지 가능
      #   (radarHarness 필요 - DH는 SCC11 레이더 있으므로 활성화)

      ret.vEgoStopping      = 0.5
      # ↑ [수정] 원본 0.8 → 0.5 m/s
      #   차가 이 속도 이하에 도달하면 '정지 완료' 판단
      #   낮출수록 더 완전히 정지 후 braking 해제

      ret.vEgoStarting      = 0.5
      # ↑ [수정] 원본 0.8 → 0.5 m/s (vEgoStopping과 동일하게 유지)
      #   출발 판단 속도 → 같아야 상태 전환 진동 없음

      ret.stopAccel         = -2.5
      # ↑ [수정] 원본 -2.0 → -2.5 m/s²
      #   DH 무거운 차체(2005kg) → 더 강한 제동으로 정밀 정지
      #   -2.5는 약 0.25g 수준 (불쾌하지 않은 범위)

      ret.stoppingDecelRate = 1.2
      # ↑ [수정] 원본 1.0 → 1.2 m/s³
      #   정지 시 감속률 강화 → 선행차 앞에서 짧은 정지거리 확보
      #   단, 너무 높으면 탑승자 불쾌감 → 1.2가 DH 최적값

      ret.longitudinalActuatorDelayLowerBound = 1.2
      ret.longitudinalActuatorDelayUpperBound = 1.5
      # ↑ [수정] 원본 1.0/1.0 → 1.2/1.5
      #   DH SCC 구형 → 버튼 스패밍 응답 지연 반영
      #   하한/상한 범위를 넓혀 실제 응답 범위 포함

      # ─── DH 전용 횡방향 튜닝 적용 ──────────────────────────────────────
      # lat_control_method == 0 (PID)일 때 DH 전용 튜닝으로 오버라이드
      if lat_control_method == 0:
        set_lat_tune(ret.lateralTuning, LatTunes.PID_DH)
        # ↑ [수정] 일반 PID → DH 전용 PID_DH
        #   tunes.py PID_DH 참조:
        #   kpV=[0.15, 0.35], kiV=[0.01, 0.035], kdV=[0.05], kf=0.00007
      # 그 외 방식(INDI/LQR/TORQUE/ATOM)은 UI 설정 그대로 유지

    # ─── 제네시스 G70 IK ─────────────────────────────────────────────────
    elif candidate == CAR.GENESIS_G70_IK:
      ret.mass      = 1595. + STD_CARGO_KG
      ret.wheelbase = 2.835

    # ─── 제네시스 G70 2020 ───────────────────────────────────────────────
    elif candidate == CAR.GENESIS_G70_2020:
      ret.mass      = 1595. + STD_CARGO_KG
      ret.wheelbase = 2.835

    # ─── 제네시스 G80 DH ─────────────────────────────────────────────────
    elif candidate == CAR.GENESIS_G80_DH:
      ret.mass      = 1855. + STD_CARGO_KG
      ret.wheelbase = 3.01

    # ─── 제네시스 G90 HI ─────────────────────────────────────────────────
    elif candidate == CAR.GENESIS_G90_HI:
      ret.mass      = 2120. + STD_CARGO_KG
      ret.wheelbase = 3.16

    # ─── 제네시스 EQ900 HI ───────────────────────────────────────────────
    elif candidate == CAR.GENESIS_EQ900_HI:
      ret.mass      = 2130. + STD_CARGO_KG
      ret.wheelbase = 3.16

    # ─── 현대 산타페 TM ──────────────────────────────────────────────────
    elif candidate == CAR.SANTAFE_TM:
      ret.mass = 1694. + STD_CARGO_KG; ret.wheelbase = 2.765
    elif candidate == CAR.SANTAFE_HEV_TM:
      ret.mass = 1907. + STD_CARGO_KG; ret.wheelbase = 2.765
    elif candidate == CAR.SONATA_DN8:
      ret.mass = 1465. + STD_CARGO_KG; ret.wheelbase = 2.84
    elif candidate == CAR.SONATA_HEV_DN8:
      ret.mass = 1505. + STD_CARGO_KG; ret.wheelbase = 2.84
    elif candidate == CAR.SONATA_LF:
      ret.mass = 1465. + STD_CARGO_KG; ret.wheelbase = 2.805
    elif candidate == CAR.SONATA_TURBO_LF:
      ret.mass = 1470. + STD_CARGO_KG; ret.wheelbase = 2.805
    elif candidate == CAR.SONATA_HEV_LF:
      ret.mass = 1595. + STD_CARGO_KG; ret.wheelbase = 2.805
    elif candidate == CAR.PALISADE_LX2:
      ret.mass = 1885. + STD_CARGO_KG; ret.wheelbase = 2.90
    elif candidate == CAR.AVANTE_AD:
      ret.mass = 1250. + STD_CARGO_KG; ret.wheelbase = 2.7
    elif candidate == CAR.AVANTE_CN7:
      ret.mass = 1225. + STD_CARGO_KG; ret.wheelbase = 2.72
    elif candidate == CAR.AVANTE_HEV_CN7:
      ret.mass = 1335. + STD_CARGO_KG; ret.wheelbase = 2.72
    elif candidate == CAR.I30_PD:
      ret.mass = 1380. + STD_CARGO_KG; ret.wheelbase = 2.65
    elif candidate == CAR.KONA_OS:
      ret.mass = 1325. + STD_CARGO_KG; ret.wheelbase = 2.6
    elif candidate == CAR.KONA_HEV_OS:
      ret.mass = 1395. + STD_CARGO_KG; ret.wheelbase = 2.6
    elif candidate == CAR.KONA_EV_OS:
      ret.mass = 1685. + STD_CARGO_KG; ret.wheelbase = 2.6
    elif candidate == CAR.IONIQ_HEV_AE:
      ret.mass = 1380. + STD_CARGO_KG; ret.wheelbase = 2.7
    elif candidate == CAR.IONIQ_EV_AE:
      ret.mass = 1445. + STD_CARGO_KG; ret.wheelbase = 2.7
    elif candidate == CAR.GRANDEUR_IG:
      ret.mass = 1560. + STD_CARGO_KG; ret.wheelbase = 2.845
    elif candidate == CAR.GRANDEUR_HEV_IG:
      ret.mass = 1675. + STD_CARGO_KG; ret.wheelbase = 2.845
    elif candidate == CAR.GRANDEUR_FL_IG:
      ret.mass = 1625. + STD_CARGO_KG; ret.wheelbase = 2.885
    elif candidate == CAR.GRANDEUR_HEV_FL_IG:
      ret.mass = 1675. + STD_CARGO_KG; ret.wheelbase = 2.885
    elif candidate == CAR.VELOSTER_JS:
      ret.mass = 1285. + STD_CARGO_KG; ret.wheelbase = 2.65
    elif candidate == CAR.TUCSON_TL:
      ret.mass = 1550. + STD_CARGO_KG; ret.wheelbase = 2.67
    elif candidate == CAR.NEXO_FE:
      ret.mass = 1885. + STD_CARGO_KG; ret.wheelbase = 2.79
    elif candidate == CAR.KIA_FORTE:
      ret.mass = 3558. * CV.LB_TO_KG;  ret.wheelbase = 2.80
    elif candidate == CAR.SORENTO_UM:
      ret.mass = 1910. + STD_CARGO_KG; ret.wheelbase = 2.78
    elif candidate == CAR.K5_JF:
      ret.mass = 1475. + STD_CARGO_KG; ret.wheelbase = 2.805
    elif candidate == CAR.K5_HEV_JF:
      ret.mass = 1600. + STD_CARGO_KG; ret.wheelbase = 2.805
    elif candidate == CAR.K5_DL3:
      ret.mass = 1450. + STD_CARGO_KG; ret.wheelbase = 2.85
    elif candidate == CAR.K5_HEV_DL3:
      ret.mass = 1540. + STD_CARGO_KG; ret.wheelbase = 2.85
    elif candidate == CAR.STINGER_CK:
      ret.mass = 1650. + STD_CARGO_KG; ret.wheelbase = 2.905
    elif candidate == CAR.K3_BD:
      ret.mass = 1260. + STD_CARGO_KG; ret.wheelbase = 2.70
    elif candidate == CAR.SPORTAGE_QL:
      ret.mass = 1510. + STD_CARGO_KG; ret.wheelbase = 2.67
    elif candidate == CAR.NIRO_HEV_DE:
      ret.mass = 1425. + STD_CARGO_KG; ret.wheelbase = 2.7
    elif candidate == CAR.NIRO_EV_DE:
      ret.mass = 1755. + STD_CARGO_KG; ret.wheelbase = 2.7
    elif candidate == CAR.K7_YG:
      ret.mass = 1565. + STD_CARGO_KG; ret.wheelbase = 2.855
    elif candidate == CAR.K7_HEV_YG:
      ret.mass = 1680. + STD_CARGO_KG; ret.wheelbase = 2.855
    elif candidate == CAR.SELTOS_SP2:
      ret.mass = 1425. + STD_CARGO_KG; ret.wheelbase = 2.63
    elif candidate == CAR.SOUL_EV_SK3:
      ret.mass = 1695. + STD_CARGO_KG; ret.wheelbase = 2.6
    elif candidate == CAR.MOHAVE_HM:
      ret.mass = 2285. + STD_CARGO_KG; ret.wheelbase = 2.895

    # ─── 하이브리드/EV 안전 설정 ─────────────────────────────────────────
    if candidate in HYBRID_CAR:
      ret.safetyConfigs[0].safetyParam = 2
    elif candidate in EV_CAR:
      ret.safetyConfigs[0].safetyParam = 1

    # ─── DH가 아닌 경우 centerToFront 기본값 적용 ────────────────────────
    if candidate != CAR.GENESIS_DH:
      ret.centerToFront = ret.wheelbase * 0.4

    # ─── 관성 모멘트 & 타이어 강성 계산 (물리 기반) ──────────────────────
    ret.rotationalInertia = scale_rot_inertia(ret.mass, ret.wheelbase)
    # ↑ 차체 중량과 휠베이스 기반으로 회전 관성 자동 계산
    #   → 급격한 방향 전환 시 물리 모델 정확도 향상

    ret.tireStiffnessFront, ret.tireStiffnessRear = scale_tire_stiffness(
      ret.mass, ret.wheelbase, ret.centerToFront,
      tire_stiffness_factor=tire_stiffness_factor
    )
    # ↑ 전/후 타이어 강성 계산
    #   DH의 경우 centerToFront=0.38 반영 → 후방 타이어 강성 약간 높게 계산

    ret.enableBsm = 0x58b in fingerprint[0]
    # ↑ 사각지대 모니터링 자동 감지 (BSM CAN ID 0x58b 존재 시 활성화)

    # ─── 안전 모드 최종 결정 ──────────────────────────────────────────────
    if (ret.radarOffCan or ret.mdpsBus == 1 or
        ret.openpilotLongitudinalControl or params.get_bool("UFCModeEnabled")):
      ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.hyundaiCommunity, 0)]
    # ↑ 다음 조건 중 하나라도 해당하면 hyundaiCommunity 모드로 전환:
    #   - 레이더 없음 (radarOffCan)
    #   - MDPS가 버스1에 있음 (mdpsBus==1)
    #   - OP 직접 종방향 제어 (openpilotLongitudinalControl)
    #   - UFC 모드 활성화

    return ret

  def update(self, c, can_strings):
    self.cp.update_strings(can_strings)
    self.cp2.update_strings(can_strings)
    self.cp_cam.update_strings(can_strings)

    ret = self.CS.update(self.cp, self.cp2, self.cp_cam)
    ret.canValid          = self.cp.can_valid and self.cp2.can_valid and self.cp_cam.can_valid
    ret.steeringRateLimited = self.CC.steer_rate_limited if self.CC is not None else False

    if not self.cp.can_valid or not self.cp2.can_valid or not self.cp_cam.can_valid:
      print('cp={}  cp2={}  cp_cam={}'.format(
        bool(self.cp.can_valid), bool(self.cp2.can_valid), bool(self.cp_cam.can_valid)))

    if self.CP.pcmCruise and not self.CC.scc_live:
      self.CP.pcmCruise = False
    elif self.CC.scc_live and not self.CP.pcmCruise:
      self.CP.pcmCruise = True

    if self.ufc_mode_enabled:
      ret.cruiseState.enabled = ret.cruiseState.available

    # ─── 버튼 이벤트 처리 ────────────────────────────────────────────────
    buttonEvents = []
    if self.CS.cruise_buttons != self.CS.prev_cruise_buttons:
      be         = car.CarState.ButtonEvent.new_message()
      be.pressed = self.CS.cruise_buttons != 0
      but        = self.CS.cruise_buttons if be.pressed else self.CS.prev_cruise_buttons
      if but == Buttons.RES_ACCEL:   be.type = ButtonType.accelCruise
      elif but == Buttons.SET_DECEL: be.type = ButtonType.decelCruise
      elif but == Buttons.GAP_DIST:  be.type = ButtonType.gapAdjustCruise
      else:                          be.type = ButtonType.unknown
      buttonEvents.append(be)
    if self.CS.cruise_main_button != self.CS.prev_cruise_main_button:
      be        = car.CarState.ButtonEvent.new_message()
      be.type   = ButtonType.altButton3
      be.pressed = bool(self.CS.cruise_main_button)
      buttonEvents.append(be)
    ret.buttonEvents = buttonEvents

    # ─── 이벤트 생성 ─────────────────────────────────────────────────────
    events = self.create_common_events(ret)

    if self.CC.longcontrol and self.CS.brake_error:
      events.add(EventName.brakeUnavailable)
    if ret.vEgo < self.CP.minSteerSpeed and self.no_mdps_mods:
      events.add(car.CarEvent.EventName.belowSteerSpeed)
    if self.CC.need_brake and not self.CC.longcontrol:
      events.add(EventName.needBrake)

    if not self.CC.lkas_temp_disabled:
      if self.CC.lanechange_manual_timer and ret.vEgo > 0.3:
        events.add(EventName.laneChangeManual)
      if self.CC.emergency_manual_timer:
        events.add(EventName.emgButtonManual)
      if self.CC.standstill_res_button:
        events.add(EventName.standstillResButton)
      if self.CC.cruise_gap_adjusting:
        events.add(EventName.gapAdjusting)
      if self.CC.on_speed_bump_control and ret.vEgo > 8.3:
        events.add(EventName.speedBump)
      if self.CC.on_speed_control and ret.vEgo > 0.3:
        events.add(EventName.camSpeedDown)
      if self.CC.curv_speed_control and ret.vEgo > 8.3:
        events.add(EventName.curvSpeedDown)
      if self.CC.cut_in_control and ret.vEgo > 8.3:
        events.add(EventName.cutinDetection)
      if self.CC.driver_scc_set_control:
        events.add(EventName.sccDriverOverride)
      if self.CC.autohold_popup_timer:
        events.add(EventName.brakeHold)
      if self.CC.auto_res_starting:
        events.add(EventName.resCruise)
      if self.CC.e2e_standstill:
        events.add(EventName.chimeAtResume)

    if self.CS.cruiseState_standstill or self.CC.standstill_status == 1:
      self.CP.standStill = True
    else:
      self.CP.standStill = False

    if self.CC.v_cruise_kph_auto_res > (20 if self.CS.is_set_speed_in_mph else 30):
      self.CP.vCruisekph = self.CC.v_cruise_kph_auto_res
    else:
      self.CP.vCruisekph = 0
    if self.CC.res_speed != 0:        self.CP.resSpeed  = self.CC.res_speed
    else:                             self.CP.resSpeed  = 0
    if self.CC.vFuture >= 1:          self.CP.vFuture   = self.CC.vFuture
    else:                             self.CP.vFuture   = 0
    if self.CC.vFutureA >= 1:         self.CP.vFutureA  = self.CC.vFutureA
    else:                             self.CP.vFutureA  = 0
    self.CP.aqValue    = self.CC.aq_value
    self.CP.aqValueRaw = self.CC.aq_value_raw

    # ─── 크루즈 모드 변경 이벤트 ─────────────────────────────────────────
    mode_events = {
      0: EventName.modeChangeOpenpilot,
      1: EventName.modeChangeDistcurv,
      2: EventName.modeChangeDistance,
      3: EventName.modeChangeCurv,
      4: EventName.modeChangeOneway,
      5: EventName.modeChangeMaponly,
    }
    if self.CC.mode_change_timer:
      ev = mode_events.get(self.CS.out.cruiseState.modeSel)
      if ev: events.add(ev)

    if self.CC.lkas_temp_disabled:       events.add(EventName.lkasDisabled)
    elif self.CC.lkas_temp_disabled_timer: events.add(EventName.lkasEnabled)

    # ─── 버튼 이벤트 → OP 활성화/비활성화 ───────────────────────────────
    for b in ret.buttonEvents:
      if b.type == ButtonType.cancel and b.pressed:
        events.add(EventName.buttonCancel)
      if self.CC.longcontrol and not self.CC.scc_live:
        if b.type in (ButtonType.accelCruise, ButtonType.decelCruise) and not b.pressed:
          events.add(EventName.buttonEnable)
        if EventName.wrongCarMode in events.events:
          events.events.remove(EventName.wrongCarMode)
        if EventName.pcmDisable in events.events:
          events.events.remove(EventName.pcmDisable)
      elif not self.CC.longcontrol and ret.cruiseState.enabled:
        if b.type == ButtonType.decelCruise and not b.pressed:
          events.add(EventName.buttonEnable)

    ret.events = events.to_msg()
    self.CS.out = ret.as_reader()
    return self.CS.out

  def apply(self, c):
    hud_control = c.hudControl
    ret = self.CC.update(
      c, c.enabled, self.CS, self.frame, c.actuators,
      c.cruiseControl.cancel,
      hud_control.visualAlert,
      hud_control.leftLaneVisible,
      hud_control.rightLaneVisible,
      hud_control.leftLaneDepart,
      hud_control.rightLaneDepart,
      hud_control.setSpeed,
      hud_control.leadVisible,
      hud_control.vFuture,
      hud_control.vFutureA
    )
    self.frame += 1
    return ret
