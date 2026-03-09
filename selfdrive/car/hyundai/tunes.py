#!/usr/bin/env python3
# =============================================================================
# 파일명  : tunes.py
# 대상차량: 제네시스 DH (2014~2016, 하네스: hyundai_j)
# 기준소스: openpilotkr/openpilot OPKR 브랜치
# 수정자  : g60100
# 버전    : v1.0.0
# 수정일  : 2025-03-09
#
# [수정 내역]
#   - LongTunes에 GENESIS_DH 전용 종방향 튜닝 추가
#   - LatTunes에 PID_DH (제네시스 DH 최적 PID) 추가
#   - 제네시스 DH 차체 특성(무거운 차체 1930kg, 구형 SCC) 반영
#   - 안전 최우선: 과도한 가속/제동 방지 로직 포함
#   - 모든 파라미터에 상세한 한국어 설명 주석 추가
# =============================================================================

from enum import Enum
from common.params import Params
from decimal import Decimal

# ─────────────────────────────────────────────────────────────────────────────
# 종방향(가속/감속) 튜닝 종류 열거형
# ─────────────────────────────────────────────────────────────────────────────
class LongTunes(Enum):
  OPKR       = 0   # OPKR 기본 종방향 튜닝 (모든 차종 공통)
  OTHER      = 1   # 기타 차종용
  GENESIS_DH = 2   # [신규 추가] 제네시스 DH 전용 최적화 튜닝

# ─────────────────────────────────────────────────────────────────────────────
# 횡방향(조향) 튜닝 종류 열거형
# ─────────────────────────────────────────────────────────────────────────────
class LatTunes(Enum):
  INDI   = 0    # INDI 제어 (Incremental Nonlinear Dynamic Inversion)
  LQR    = 1    # LQR 제어 (Linear Quadratic Regulator)
  PID    = 2    # PID 제어 - UI 설정값 사용
  PID_A  = 3
  PID_B  = 4
  PID_C  = 5
  PID_D  = 6
  PID_E  = 7
  PID_F  = 8
  PID_G  = 9
  PID_H  = 10
  PID_I  = 11
  PID_J  = 12
  PID_K  = 13
  PID_L  = 14
  PID_M  = 15
  TORQUE = 16   # Torque 제어 (최신 제어 방식)
  ATOM   = 17   # ATOM 복합 제어
  PID_DH = 18   # [신규 추가] 제네시스 DH 전용 최적 PID 튜닝


# =============================================================================
# 종방향(가속/감속) 튜닝 설정 함수
# =============================================================================
def set_long_tune(tune, name):
  """
  종방향 제어 PID 파라미터 설정
  - kp (비례항): 목표속도와 현재속도 차이에 즉각 반응, 클수록 빠른 응답
  - ki (적분항): 지속적 오차 누적 보정, 클수록 오차 수렴 빠름 (단, 오버슈트 위험)
  - kd (미분항): 속도 변화율 감쇠, 클수록 부드러운 정지/출발
  - kf (피드포워드): 목표가속도 직접 반영, 응답성 향상
  - BP (Breakpoint): 속도 구간 기준점 [m/s] (0=정지, 4≈15km/h, 9≈32km/h, ...)
  """

  # ─────────────────────────────────────────────────────────────────────────
  # OPKR 기본 종방향 튜닝 (모든 차종 공통 기본값)
  # ─────────────────────────────────────────────────────────────────────────
  if name == LongTunes.OPKR:
    tune.kpBP = [0., 4., 9., 17., 23., 31.]
    tune.kpV  = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]   # 비례항: 전 속도구간 균일
    tune.kiBP = [0., 4., 9., 17., 23., 31.]
    tune.kiV  = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]   # 적분항: 비활성화 (SCC 버튼 방식 사용)
    tune.deadzoneBP = [0., 4.]
    tune.deadzoneV  = [0.0, 0.0]                   # 불감대: 비활성화
    tune.kdBP = [0., 4., 9., 17., 23., 31.]
    tune.kdV  = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]   # 미분항: 비활성화
    tune.kfBP = [0., 4., 9., 17., 23., 31.]
    tune.kfV  = [1., 1., 1., 1., 1., 1.]           # 피드포워드: 전 구간 1.0

  # ─────────────────────────────────────────────────────────────────────────
  # [신규] 제네시스 DH 전용 종방향 튜닝
  #
  # DH 차량 특성:
  #   - 차체 중량: 1930kg (무거운 편 → 관성 큼 → kp를 약간 높임)
  #   - SCC 방식: 구형 버튼 스패밍 방식 (직접 제어 불가)
  #   - 엔진: 3.8L V6 람다2 (응답성 좋음, 과도한 kp 불필요)
  #   - 변속기: 8단 자동 (부드러운 변속을 위해 kd 적용)
  #
  # 안전 철학:
  #   - 급가속/급제동 방지: kp를 속도별로 점진적 감소
  #   - 고속에서 안정성: 고속(31m/s=112km/h) kp 낮춤
  #   - 저속 정밀 제어: 저속(4m/s=14km/h) kp 약간 높여 민감하게 반응
  # ─────────────────────────────────────────────────────────────────────────
  elif name == LongTunes.GENESIS_DH:
    # 속도 구간 기준점: [정지, 15km/h, 32km/h, 61km/h, 83km/h, 112km/h]
    tune.kpBP = [0.,  4.,   9.,   17.,  23.,  31.]
    tune.kpV  = [0.6, 0.55, 0.50, 0.45, 0.40, 0.35]
    # ↑ 비례항 설명:
    #   - 저속(0~15km/h): 0.6 - 정체 구간 민감한 반응
    #   - 중속(15~83km/h): 점진적 감소 - 부드러운 크루즈
    #   - 고속(83~112km/h): 0.35 - 고속 안정성, 과도한 가속 방지

    tune.kiBP = [0.,  4.,   9.,   17.,  23.,  31.]
    tune.kiV  = [0.0, 0.0,  0.0,  0.0,  0.0,  0.0]
    # ↑ 적분항: SCC 버튼 스패밍 방식이므로 0으로 고정
    #   (적분항 활성화 시 SCC 버튼 오작동 가능성)

    tune.deadzoneBP = [0., 4.]
    tune.deadzoneV  = [0.0, 0.05]
    # ↑ 불감대: 4m/s(14km/h) 이상에서 미세한 속도 오차 무시
    #   → 불필요한 SCC 버튼 신호 방지, 크루즈 안정성 향상

    tune.kdBP = [0.,  4.,   9.,   17.,  23.,  31.]
    tune.kdV  = [0.3, 0.25, 0.20, 0.15, 0.10, 0.05]
    # ↑ 미분항 설명:
    #   - 저속: 0.3 - 정차 시 부드러운 감속 (DH 무거운 차체 보정)
    #   - 고속: 0.05 - 고속에서 진동 방지
    #   → 전반적으로 가속/제동 시 '충격' 감소 효과

    tune.kfBP = [0.,  4.,   9.,   17.,  23.,  31.]
    tune.kfV  = [1.0, 1.0,  1.0,  1.0,  1.0,  1.0]
    # ↑ 피드포워드: 전 구간 1.0 유지 (SCC 명령 직접 반영)

  else:
    raise NotImplementedError('존재하지 않는 종방향 튜닝입니다.')


# =============================================================================
# 횡방향(조향) 튜닝 설정 함수
# =============================================================================
def set_lat_tune(tune, name, max_lat_accel=2.5, FRICTION=.1):
  """
  횡방향 제어 파라미터 설정
  - PID: 비례-적분-미분 제어 (가장 단순, 안정적)
  - INDI: 비선형 동적 역변환 제어 (빠른 응답, 튜닝 복잡)
  - LQR: 선형 이차 최적 제어 (수학적 최적화)
  - TORQUE: 토크 기반 제어 (최신, 고성능)
  - ATOM: 복합 제어 (PID+INDI+LQR+TORQUE 동시 지원)
  """
  params = Params()

  # ─────────────────────────────────────────────────────────────────────────
  # ATOM 복합 제어 (UI에서 선택한 방식으로 내부 전환)
  # ─────────────────────────────────────────────────────────────────────────
  if name == LatTunes.ATOM:
    tune.init('atom')

    # [TORQUE 제어 파라미터]
    TorqueKp           = float(Decimal(params.get("TorqueKp", encoding="utf8")) * Decimal('0.1'))
    TorqueKf           = float(Decimal(params.get("TorqueKf", encoding="utf8")) * Decimal('0.1'))
    TorqueKi           = float(Decimal(params.get("TorqueKi", encoding="utf8")) * Decimal('0.1'))
    TorqueFriction     = float(Decimal(params.get("TorqueFriction", encoding="utf8")) * Decimal('0.001'))
    TorqueUseAngle     = params.get_bool('TorqueUseAngle')
    max_lat_accel      = float(Decimal(params.get("TorqueMaxLatAccel", encoding="utf8")) * Decimal('0.1'))
    steer_ang_deadzone = float(Decimal(params.get("TorqueAngDeadZone", encoding="utf8")) * Decimal('0.1'))

    tune.atom.torque.useSteeringAngle        = TorqueUseAngle
    tune.atom.torque.kp                      = TorqueKp / max_lat_accel
    tune.atom.torque.kf                      = TorqueKf / max_lat_accel
    tune.atom.torque.ki                      = TorqueKi / max_lat_accel
    tune.atom.torque.friction                = TorqueFriction
    tune.atom.torque.steeringAngleDeadzoneDeg = steer_ang_deadzone

    # [LQR 제어 파라미터]
    Scale  = float(Decimal(params.get("Scale", encoding="utf8")) * Decimal('1.0'))
    LqrKi  = float(Decimal(params.get("LqrKi", encoding="utf8")) * Decimal('0.001'))
    DcGain = float(Decimal(params.get("DcGain", encoding="utf8")) * Decimal('0.00001'))

    tune.atom.lqr.scale  = Scale
    tune.atom.lqr.ki     = LqrKi
    tune.atom.lqr.dcGain = DcGain
    tune.atom.lqr.a = [0., 1., -0.22619643, 1.21822268]
    tune.atom.lqr.b = [-1.92006585e-04, 3.95603032e-05]
    tune.atom.lqr.c = [1., 0.]
    tune.atom.lqr.k = [-110.73572306, 451.22718255]
    tune.atom.lqr.l = [0.3233671, 0.3185757]

    # [INDI 제어 파라미터]
    InnerLoopGain        = float(Decimal(params.get("InnerLoopGain", encoding="utf8")) * Decimal('0.1'))
    OuterLoopGain        = float(Decimal(params.get("OuterLoopGain", encoding="utf8")) * Decimal('0.1'))
    TimeConstant         = float(Decimal(params.get("TimeConstant", encoding="utf8")) * Decimal('0.1'))
    ActuatorEffectiveness = float(Decimal(params.get("ActuatorEffectiveness", encoding="utf8")) * Decimal('0.1'))

    tune.atom.indi.innerLoopGainBP      = [0.]
    tune.atom.indi.innerLoopGainV       = [InnerLoopGain]
    tune.atom.indi.outerLoopGainBP      = [0.]
    tune.atom.indi.outerLoopGainV       = [OuterLoopGain]
    tune.atom.indi.timeConstantBP       = [0.]
    tune.atom.indi.timeConstantV        = [TimeConstant]
    tune.atom.indi.actuatorEffectivenessBP = [0.]
    tune.atom.indi.actuatorEffectivenessV  = [ActuatorEffectiveness]

    # [PID 제어 파라미터]
    PidKp = float(Decimal(params.get("PidKp", encoding="utf8")) * Decimal('0.01'))
    PidKi = float(Decimal(params.get("PidKi", encoding="utf8")) * Decimal('0.001'))
    PidKd = float(Decimal(params.get("PidKd", encoding="utf8")) * Decimal('0.01'))
    PidKf = float(Decimal(params.get("PidKf", encoding="utf8")) * Decimal('0.00001'))

    tune.atom.pid.kpBP = [0., 9.]
    tune.atom.pid.kpV  = [0.1, PidKp]
    tune.atom.pid.kiBP = [0., 9.]
    tune.atom.pid.kiV  = [0.01, PidKi]
    tune.atom.pid.kdBP = [0.]
    tune.atom.pid.kdV  = [PidKd]
    tune.atom.pid.kf   = PidKf

  # ─────────────────────────────────────────────────────────────────────────
  # TORQUE 제어 (UI 설정값 사용)
  # ─────────────────────────────────────────────────────────────────────────
  elif name == LatTunes.TORQUE:
    TorqueKp           = float(Decimal(params.get("TorqueKp", encoding="utf8")) * Decimal('0.1'))
    TorqueKf           = float(Decimal(params.get("TorqueKf", encoding="utf8")) * Decimal('0.1'))
    TorqueKi           = float(Decimal(params.get("TorqueKi", encoding="utf8")) * Decimal('0.1'))
    TorqueFriction     = float(Decimal(params.get("TorqueFriction", encoding="utf8")) * Decimal('0.001'))
    TorqueUseAngle     = params.get_bool('TorqueUseAngle')
    max_lat_accel      = float(Decimal(params.get("TorqueMaxLatAccel", encoding="utf8")) * Decimal('0.1'))
    steer_ang_deadzone = float(Decimal(params.get("TorqueAngDeadZone", encoding="utf8")) * Decimal('0.1'))
    tune.init('torque')
    tune.torque.useSteeringAngle         = TorqueUseAngle
    tune.torque.kp                       = TorqueKp / max_lat_accel
    tune.torque.kf                       = TorqueKf / max_lat_accel
    tune.torque.ki                       = TorqueKi / max_lat_accel
    tune.torque.friction                 = TorqueFriction
    tune.torque.steeringAngleDeadzoneDeg = steer_ang_deadzone

  # ─────────────────────────────────────────────────────────────────────────
  # LQR 제어 (UI 설정값 사용)
  # ─────────────────────────────────────────────────────────────────────────
  elif name == LatTunes.LQR:
    Scale  = float(Decimal(params.get("Scale", encoding="utf8")) * Decimal('1.0'))
    LqrKi  = float(Decimal(params.get("LqrKi", encoding="utf8")) * Decimal('0.001'))
    DcGain = float(Decimal(params.get("DcGain", encoding="utf8")) * Decimal('0.00001'))
    tune.init('lqr')
    tune.lqr.scale  = Scale
    tune.lqr.ki     = LqrKi
    tune.lqr.a      = [0., 1., -0.22619643, 1.21822268]
    tune.lqr.b      = [-1.92006585e-04, 3.95603032e-05]
    tune.lqr.c      = [1., 0.]
    tune.lqr.k      = [-110., 451.]
    tune.lqr.l      = [0.33, 0.318]
    tune.lqr.dcGain = DcGain

  # ─────────────────────────────────────────────────────────────────────────
  # INDI 제어 (UI 설정값 사용)
  # ─────────────────────────────────────────────────────────────────────────
  elif name == LatTunes.INDI:
    InnerLoopGain        = float(Decimal(params.get("InnerLoopGain", encoding="utf8")) * Decimal('0.1'))
    OuterLoopGain        = float(Decimal(params.get("OuterLoopGain", encoding="utf8")) * Decimal('0.1'))
    TimeConstant         = float(Decimal(params.get("TimeConstant", encoding="utf8")) * Decimal('0.1'))
    ActuatorEffectiveness = float(Decimal(params.get("ActuatorEffectiveness", encoding="utf8")) * Decimal('0.1'))
    tune.init('indi')
    tune.indi.innerLoopGainBP      = [0.]
    tune.indi.innerLoopGainV       = [InnerLoopGain]
    tune.indi.outerLoopGainBP      = [0.]
    tune.indi.outerLoopGainV       = [OuterLoopGain]
    tune.indi.timeConstantBP       = [0.]
    tune.indi.timeConstantV        = [TimeConstant]
    tune.indi.actuatorEffectivenessBP = [0.]
    tune.indi.actuatorEffectivenessV  = [ActuatorEffectiveness]

  # ─────────────────────────────────────────────────────────────────────────
  # PID 계열 제어
  # ─────────────────────────────────────────────────────────────────────────
  elif 'PID' in str(name):

    # -------------------------------------------------------------------
    # [신규] PID_DH: 제네시스 DH 전용 최적 PID 튜닝
    #
    # DH 특성 기반 설계:
    #   - 조향비(SteerRatio): 14.4 (다른 차 대비 무거운 핸들감)
    #   - 차체 중량: 1930kg → 관성 큼 → kp 0.35로 안정적 반응
    #   - 휠베이스: 3.01m (긴 편) → 저속 코너 진입 둔함 → ki 보정
    #   - MDPS: 구형 (과도한 토크 입력 시 오류 발생)
    #     → kp/ki 과도 상승 금지, kf로 반응성 보완
    #
    # 속도 구간별 설계:
    #   kpBP = [0, 9] → [저속(0~32km/h), 고속(32km/h~)]
    #   kpV  = [0.15, 0.35]
    #     - 저속: 0.15 (급격한 조향 방지, 주차장/교차로 안전)
    #     - 고속: 0.35 (차선 추적 정확도 향상)
    #   kiV  = [0.01, 0.035]
    #     - 저속: 0.01 (적분 최소화 → 휘청거림 방지)
    #     - 고속: 0.035 (직선 주행 중심 유지 보정)
    #   kdV  = [0.05] (미분항: MDPS 진동 감쇠)
    #   kf   = 0.00007 (피드포워드: DH 조향 지연 보상)
    # -------------------------------------------------------------------
    if name == LatTunes.PID_DH:
      tune.init('pid')
      tune.pid.kpBP = [0.,  9.]
      tune.pid.kpV  = [0.15, 0.35]
      # ↑ 비례항: 저속 0.15(안전), 고속 0.35(정확도)
      tune.pid.kiBP = [0.,   9.]
      tune.pid.kiV  = [0.01, 0.035]
      # ↑ 적분항: 저속 최소화(안전), 고속 적정값(직선 유지)
      tune.pid.kdBP = [0.]
      tune.pid.kdV  = [0.05]
      # ↑ 미분항: MDPS 진동 감쇠, DH 구형 MDPS 보호
      tune.pid.kf   = 0.00007
      # ↑ 피드포워드: DH 조향 액추에이터 지연(0.25s) 보상

    # -------------------------------------------------------------------
    # PID (UI 설정값 사용 - 사용자 커스텀)
    # -------------------------------------------------------------------
    elif name == LatTunes.PID:
      PidKp = float(Decimal(params.get("PidKp", encoding="utf8")) * Decimal('0.01'))
      PidKi = float(Decimal(params.get("PidKi", encoding="utf8")) * Decimal('0.001'))
      PidKd = float(Decimal(params.get("PidKd", encoding="utf8")) * Decimal('0.01'))
      PidKf = float(Decimal(params.get("PidKf", encoding="utf8")) * Decimal('0.00001'))
      tune.init('pid')
      tune.pid.kpBP = [0., 9.]
      tune.pid.kpV  = [0.1, PidKp]
      tune.pid.kiBP = [0., 9.]
      tune.pid.kiV  = [0.01, PidKi]
      tune.pid.kdBP = [0.]
      tune.pid.kdV  = [PidKd]
      tune.pid.kf   = PidKf

    elif name == LatTunes.PID_A:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.2]; tune.pid.kiV  = [0.05]; tune.pid.kf = 0.00003

    elif name == LatTunes.PID_C:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.6]; tune.pid.kiV  = [0.1];  tune.pid.kf = 0.00006

    elif name == LatTunes.PID_D:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.6]; tune.pid.kiV  = [0.1];  tune.pid.kf = 0.00007818594

    elif name == LatTunes.PID_F:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.723]; tune.pid.kiV = [0.0428]; tune.pid.kf = 0.00006

    elif name == LatTunes.PID_G:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.18]; tune.pid.kiV  = [0.015]; tune.pid.kf = 0.00012

    elif name == LatTunes.PID_H:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.17]; tune.pid.kiV  = [0.03];  tune.pid.kf = 0.00006

    elif name == LatTunes.PID_I:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.15]; tune.pid.kiV  = [0.05];  tune.pid.kf = 0.00004

    elif name == LatTunes.PID_J:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.19]; tune.pid.kiV  = [0.02];  tune.pid.kf = 0.00007818594

    elif name == LatTunes.PID_L:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.3];  tune.pid.kiV  = [0.05];  tune.pid.kf = 0.00006

    elif name == LatTunes.PID_M:
      tune.init('pid')
      tune.pid.kiBP = [0.0]; tune.pid.kpBP = [0.0]
      tune.pid.kpV  = [0.3];  tune.pid.kiV  = [0.05];  tune.pid.kf = 0.00007

    else:
      raise NotImplementedError('존재하지 않는 PID 튜닝입니다.')
  else:
    raise NotImplementedError('존재하지 않는 횡방향 튜닝입니다.')
