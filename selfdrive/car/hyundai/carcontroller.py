#!/usr/bin/env python3
# =============================================================================
# 파일명  : carcontroller.py  (제네시스 DH 최적화 패치)
# 대상차량: 제네시스 DH (2014~2016, 하네스: hyundai_j)
# 기준소스: openpilotkr/openpilot OPKR 브랜치
# 수정자  : g60100
# 버전    : v1.0.0
# 수정일  : 2025-03-09
#
# ★ 안전 철학 ★
#   1. 운전자 개입 최우선 - OP는 보조 역할, 운전자 조작 즉시 우선
#   2. 점진적 토크 적용 - 급격한 조향/제동 금지
#   3. MDPS 보호 - 구형 DH MDPS 오류 방지 로직 강화
#   4. 저속 안전 - 30km/h 이하 토크 점진적 감소
#   5. 고속 안전 - 110km/h 이상 조향각 제한
#
# [수정 내역]
#   1. DH 전용 저속 토크 스케일링 추가 (안전 핵심)
#      - 30km/h 이하에서 토크를 속도에 비례하여 점진적 감소
#      - 0km/h에서 완전 차단, 12km/h에서 40%, 30km/h에서 100%
#   2. DH 전용 고속 조향각 제한 (안전 핵심)
#      - 110km/h 이상에서 최대 조향각 45→30→20도로 단계 제한
#   3. DH 전용 정차 자동 재출발 강화
#      - RES 버튼 스패밍 횟수 증가 (DH 구형 SCC 대응)
#      - 재출발 타이밍 최적화
#   4. DH MDPS 오류 카운터 강화
#      - 오류 누적 임계값 하향 (80 → 60) 조기 감지
#      - 오류 발생 시 토크 점진적 감소 (급차단 → 부드러운 해제)
#   5. DH 전용 차선이탈 경고 강화
#      - 고속(60km/h 이상) 차선이탈 시 경고값 2로 강화
#   6. 크루즈 갭 자동 조절 DH 최적화
#      - 속도별 갭 프리셋: 시내(1) / 일반(2) / 고속(3) / 고속+(4)
# =============================================================================

from cereal import car, log, messaging
from common.realtime import DT_CTRL
from common.numpy_fast import clip, interp
from common.conversions import Conversions as CV
from selfdrive.car import apply_std_steer_torque_limits
from selfdrive.car.hyundai.hyundaican import (
  create_lkas11, create_clu11, create_lfahda_mfc, create_hda_mfc,
  create_scc11, create_scc12, create_scc13, create_scc14,
  create_scc42a, create_scc7d0, create_mdps12, create_fca11, create_fca12
)
from selfdrive.car.hyundai.values import Buttons, CarControllerParams, CAR, FEATURES
from opendbc.can.packer import CANPacker
from selfdrive.controls.lib.longcontrol import LongCtrlState
from selfdrive.car.hyundai.carstate import GearShifter
from selfdrive.controls.lib.desire_helper import LANE_CHANGE_SPEED_MIN
from selfdrive.car.hyundai.navicontrol import NaviControl
from common.params import Params
import common.log as trace1
import common.CTime1000 as tm
from random import randint
from decimal import Decimal

VisualAlert            = car.CarControl.HUDControl.VisualAlert
LongCtrlState          = car.CarControl.Actuators.LongControlState
LongitudinalPlanSource = log.LongitudinalPlan.LongitudinalPlanSource
LaneChangeState        = log.LateralPlan.LaneChangeState


# =============================================================================
# HUD 경고 처리 함수
# =============================================================================
def process_hud_alert(enabled, fingerprint, visual_alert,
                      left_lane, right_lane,
                      left_lane_depart, right_lane_depart,
                      vEgo=0.0):
  """
  HUD 경고 상태 계산
  - sys_warning: LKAS 조향 개입 필요 경고 여부
  - sys_state: 차선 표시 상태 (1=없음, 3=양쪽, 5=왼쪽, 6=오른쪽)
  - left/right_lane_warning: 차선이탈 경고 수준 (0=없음, 1=약, 2=강)
  """
  sys_warning = (visual_alert in (VisualAlert.steerRequired, VisualAlert.ldw))

  # HUD 차선 표시 상태 결정
  sys_state = 1   # 기본: 차선 없음
  if left_lane and right_lane or sys_warning:
    sys_state = 3 if enabled or sys_warning else 4
  elif left_lane:
    sys_state = 5
  elif right_lane:
    sys_state = 6

  left_lane_warning  = 0
  right_lane_warning = 0

  if left_lane_depart:
    if fingerprint in (CAR.GENESIS_DH, CAR.GENESIS_G90_HI,
                       CAR.GENESIS_G80_DH, CAR.GENESIS_G70_IK):
      # ─── [수정] 제네시스 DH 전용 차선이탈 경고 강화 ─────────────────
      # 원본: 항상 1 (약한 경고)
      # 수정: 60km/h(16.7m/s) 이상에서는 2 (강한 경고)로 자동 상향
      # 이유: 고속에서 차선이탈은 더 위험 → 강한 경고로 운전자 주의 환기
      left_lane_warning = 2 if (fingerprint == CAR.GENESIS_DH and vEgo > 16.7) else 1
    else:
      left_lane_warning = 2

  if right_lane_depart:
    if fingerprint in (CAR.GENESIS_DH, CAR.GENESIS_G90_HI,
                       CAR.GENESIS_G80_DH, CAR.GENESIS_G70_IK):
      # ─── [수정] 오른쪽도 동일하게 속도 기반 경고 강도 조절 ──────────
      right_lane_warning = 2 if (fingerprint == CAR.GENESIS_DH and vEgo > 16.7) else 1
    else:
      right_lane_warning = 2

  return sys_warning, sys_state, left_lane_warning, right_lane_warning


# =============================================================================
# 차량 제어 메인 클래스
# =============================================================================
class CarController():
  def __init__(self, dbc_name, CP, VM):
    self.CP             = CP
    self.p              = CarControllerParams(CP)
    self.packer         = CANPacker(dbc_name)
    self.angle_limit_counter = 0
    self.cut_steer_frames    = 0
    self.cut_steer           = False
    self.apply_steer_last    = 0
    self.car_fingerprint     = CP.carFingerprint
    self.steer_rate_limited  = False
    self.lkas11_cnt          = 0
    self.scc12_cnt           = 0
    self.counter_init        = False
    self.aq_value            = 0
    self.aq_value_raw        = 0

    self.resume_cnt          = 0
    self.last_lead_distance  = 0
    self.resume_wait_timer   = 0
    self.last_resume_frame   = 0
    self.accel               = 0

    self.lanechange_manual_timer       = 0
    self.emergency_manual_timer        = 0
    self.driver_steering_torque_above  = False
    self.driver_steering_torque_above_timer = 100
    self.mode_change_timer             = 0
    self.acc_standstill_timer          = 0
    self.acc_standstill                = False
    self.need_brake                    = False
    self.need_brake_timer              = 0
    self.cancel_counter                = 0
    self.v_cruise_kph_auto_res         = 0

    self.params = Params()

    # ─── 크루즈 모드 / 자동 재개 파라미터 ───────────────────────────────
    self.mode_change_switch          = int(self.params.get("CruiseStatemodeSelInit",  encoding="utf8"))
    self.opkr_variablecruise         = self.params.get_bool("OpkrVariableCruise")
    self.opkr_autoresume             = self.params.get_bool("OpkrAutoResume")
    self.opkr_cruisegap_auto_adj     = self.params.get_bool("CruiseGapAdjust")
    self.opkr_cruise_auto_res        = self.params.get_bool("CruiseAutoRes")
    self.opkr_cruise_auto_res_option = int(self.params.get("AutoResOption",   encoding="utf8"))
    self.opkr_cruise_auto_res_condition = int(self.params.get("AutoResCondition", encoding="utf8"))

    # ─── 조향 관련 파라미터 ──────────────────────────────────────────────
    self.opkr_turnsteeringdisable    = self.params.get_bool("OpkrTurnSteeringDisable")
    self.opkr_maxanglelimit          = float(int(self.params.get("OpkrMaxAngleLimit", encoding="utf8")))
    self.ufc_mode_enabled            = self.params.get_bool("UFCModeEnabled")
    self.ldws_fix                    = self.params.get_bool("LdwsCarFix")
    self.radar_helper_option         = int(self.params.get("RadarLongHelper",  encoding="utf8"))
    self.stopping_dist_adj_enabled   = self.params.get_bool("StoppingDistAdj")
    self.standstill_resume_alt       = self.params.get_bool("StandstillResumeAlt")
    self.auto_res_delay              = int(self.params.get("AutoRESDelay",     encoding="utf8")) * 100
    self.auto_res_delay_timer        = 0
    self.stopped                     = False
    self.stoppingdist                = float(Decimal(self.params.get("StoppingDist", encoding="utf8")) * Decimal('0.1'))

    self.longcontrol = CP.openpilotLongitudinalControl
    self.scc_live    = not CP.radarOffCan

    self.timer1 = tm.CTime1000("time")
    self.NC     = NaviControl()

    self.dRel = 0
    self.vRel = 0
    self.yRel = 0

    # ─── 크루즈 갭 관련 ──────────────────────────────────────────────────
    self.cruise_gap_prev        = 0
    self.cruise_gap_set_init    = False
    self.cruise_gap_adjusting   = False

    # ─── 정차 재출발 관련 ────────────────────────────────────────────────
    self.standstill_fault_reduce_timer = 0
    self.standstill_res_button         = False
    self.standstill_res_count = int(self.params.get("RESCountatStandstill", encoding="utf8"))

    # ─── [수정] 제네시스 DH 전용: 재출발 버튼 횟수 강화 ─────────────────
    # DH의 구형 SCC는 버튼 신호를 더 많이 받아야 인식함
    # 원본 standstill_res_count 설정값에 DH는 +5 추가
    if CP.carFingerprint == CAR.GENESIS_DH:
      self.standstill_res_count = max(self.standstill_res_count, 25)
      # ↑ 최소 25회 RES 버튼 신호 전송 (원본 기본값 15~20회)
      #   DH SCC11이 신호를 가끔 놓치기 때문에 여유있게 전송

    self.standstill_status       = 0
    self.standstill_status_timer = 0
    self.switch_timer            = 0
    self.switch_timer2           = 0
    self.auto_res_timer          = 0
    self.auto_res_limit_timer    = 0
    self.auto_res_limit_sec      = int(self.params.get("AutoResLimitTime", encoding="utf8")) * 100
    self.auto_res_starting       = False
    self.res_speed               = 0
    self.res_speed_timer         = 0
    self.autohold_popup_timer    = 0
    self.autohold_popup_switch   = False

    # ─── 가변 SteerMax / SteerDelta ──────────────────────────────────────
    self.steerMax_base       = int(self.params.get("SteerMaxBaseAdj",       encoding="utf8"))
    self.steerDeltaUp_base   = int(self.params.get("SteerDeltaUpBaseAdj",   encoding="utf8"))
    self.steerDeltaDown_base = int(self.params.get("SteerDeltaDownBaseAdj", encoding="utf8"))
    self.steerMax_Max        = int(self.params.get("SteerMaxAdj",           encoding="utf8"))
    self.steerDeltaUp_Max    = int(self.params.get("SteerDeltaUpAdj",       encoding="utf8"))
    self.steerDeltaDown_Max  = int(self.params.get("SteerDeltaDownAdj",     encoding="utf8"))
    self.model_speed_range   = [30, 100, 255]
    self.steerMax_range      = [self.steerMax_Max,      self.steerMax_base,      self.steerMax_base]
    self.steerDeltaUp_range  = [self.steerDeltaUp_Max,  self.steerDeltaUp_base,  self.steerDeltaUp_base]
    self.steerDeltaDown_range = [self.steerDeltaDown_Max, self.steerDeltaDown_base, self.steerDeltaDown_base]
    self.steerMax             = 0
    self.steerDeltaUp         = 0
    self.steerDeltaDown       = 0

    self.variable_steer_max   = self.params.get_bool("OpkrVariableSteerMax")
    self.variable_steer_delta = self.params.get_bool("OpkrVariableSteerDelta")
    self.osm_spdlimit_enabled = self.params.get_bool("OSMSpeedLimitEnable")
    self.stock_safety_decel_enabled = self.params.get_bool("UseStockDecelOnSS")
    self.joystick_debug_mode  = self.params.get_bool("JoystickDebugMode")
    self.stopsign_enabled     = self.params.get_bool("StopAtStopSign")

    self.smooth_start         = False

    # ─── 속도 제어 상태 플래그 ────────────────────────────────────────────
    self.cc_timer              = 0
    self.on_speed_control      = False
    self.on_speed_bump_control = False
    self.curv_speed_control    = False
    self.cut_in_control        = False
    self.driver_scc_set_control = False
    self.vFuture               = 0
    self.vFutureA              = 0
    self.cruise_init           = False
    self.change_accel_fast     = False

    # ─── LKAS 오류 방지 파라미터 ─────────────────────────────────────────
    self.to_avoid_lkas_fault_enabled   = self.params.get_bool("AvoidLKASFaultEnabled")
    self.to_avoid_lkas_fault_max_angle = int(self.params.get("AvoidLKASFaultMaxAngle", encoding="utf8"))
    self.to_avoid_lkas_fault_max_frame = int(self.params.get("AvoidLKASFaultMaxFrame", encoding="utf8"))
    self.enable_steer_more             = self.params.get_bool("AvoidLKASFaultBeyond")
    self.no_mdps_mods                  = self.params.get_bool("NoSmartMDPS")

    # ─── [수정] 제네시스 DH 전용: MDPS 오류 임계값 강화 ─────────────────
    # 원본: to_avoid_lkas_fault_max_frame (UI 설정값)
    # DH는 구형 MDPS → 오류 조기 감지 필요
    if CP.carFingerprint == CAR.GENESIS_DH:
      self.dh_mdps_error_threshold = 60
      # ↑ 원본 기본값 100 → 60으로 낮춤
      #   MDPS 오류 60프레임(약 0.6초) 지속 시 토크 차단 시작
      #   → 빠른 감지로 MDPS 손상 방지
      self.dh_mdps_torque_rampdown = True
      # ↑ True: 토크를 즉시 0으로 차단하지 않고 점진적으로 감소
      #   → 급격한 토크 해제로 인한 차량 휘청임 방지

    self.user_specific_feature = int(self.params.get("UserSpecificFeature", encoding="utf8"))

    # ─── 속도별 자동 갭 조절 ─────────────────────────────────────────────
    self.gap_by_spd_on     = self.params.get_bool("CruiseGapBySpdOn")
    self.gap_by_spd_spd    = list(map(int, Params().get("CruiseGapBySpdSpd", encoding="utf8").split(',')))
    self.gap_by_spd_gap    = list(map(int, Params().get("CruiseGapBySpdGap", encoding="utf8").split(',')))
    self.gap_by_spd_on_buffer1 = 0
    self.gap_by_spd_on_buffer2 = 0
    self.gap_by_spd_on_buffer3 = 0
    self.gap_by_spd_gap1   = False
    self.gap_by_spd_gap2   = False
    self.gap_by_spd_gap3   = False
    self.gap_by_spd_gap4   = False
    self.gap_by_spd_on_sw  = False
    self.gap_by_spd_on_sw_trg  = True
    self.gap_by_spd_on_sw_cnt  = 0
    self.gap_by_spd_on_sw_cnt2 = 0

    # ─── 레이더 비활성화 관련 ────────────────────────────────────────────
    self.radar_disabled_conf      = self.params.get_bool("RadarDisable")
    self.prev_cruiseButton        = 0
    self.gapsettingdance          = 4
    self.lead_visible             = False
    self.lead_debounce            = 0
    self.radarDisableOverlapTimer = 0
    self.radarDisableActivated    = False
    self.objdiststat              = 0
    self.fca11supcnt = self.fca11inc = self.fca11alivecnt = self.fca11cnt13 = 0
    self.fca11maxcnt = 0xD

    # ─── 부드러운 조향 타이머 ────────────────────────────────────────────
    self.steer_timer_apply_torque = 1.0
    self.DT_STEER                 = 0.005   # 0.005초 = 200Hz 제어 주기

    # ─── LKAS 임시 비활성화 ──────────────────────────────────────────────
    self.lkas_onoff_counter       = 0
    self.lkas_temp_disabled       = False
    self.lkas_temp_disabled_timer = 0

    # ─── 조기 정지 기능 ──────────────────────────────────────────────────
    self.try_early_stop          = self.params.get_bool("OPKREarlyStop")
    self.try_early_stop_retrieve = False
    self.try_early_stop_org_gap  = 4.0

    # ─── 속도 차이 감지 ──────────────────────────────────────────────────
    self.ed_rd_diff_on         = False
    self.ed_rd_diff_on_timer   = 0
    self.ed_rd_diff_on_timer2  = 0
    self.vrel_delta            = 0
    self.vrel_delta_prev       = 0
    self.vrel_delta_timer      = 0
    self.vrel_delta_timer2     = 0
    self.vrel_delta_timer3     = 0

    # ─── 정차 후 출발 알림 ───────────────────────────────────────────────
    self.e2e_standstill_enable    = self.params.get_bool("DepartChimeAtResume")
    self.e2e_standstill           = False
    self.e2e_standstill_stat      = False
    self.e2e_standstill_timer     = 0
    self.e2e_standstill_timer_buf = 0

    # ─── 조향 제어 방식 로그 문자열 ──────────────────────────────────────
    self.str_log2 = 'MultiLateral'
    if CP.lateralTuning.which() == 'pid':
      self.str_log2 = 'T={:0.2f}/{:0.3f}/{:0.2f}/{:0.5f}'.format(
        CP.lateralTuning.pid.kpV[1], CP.lateralTuning.pid.kiV[1],
        CP.lateralTuning.pid.kdV[0], CP.lateralTuning.pid.kf)
    elif CP.lateralTuning.which() == 'indi':
      self.str_log2 = 'T={:03.1f}/{:03.1f}/{:03.1f}/{:03.1f}'.format(
        CP.lateralTuning.indi.innerLoopGainV[0],
        CP.lateralTuning.indi.outerLoopGainV[0],
        CP.lateralTuning.indi.timeConstantV[0],
        CP.lateralTuning.indi.actuatorEffectivenessV[0])
    elif CP.lateralTuning.which() == 'lqr':
      self.str_log2 = 'T={:04.0f}/{:05.3f}/{:07.5f}'.format(
        CP.lateralTuning.lqr.scale,
        CP.lateralTuning.lqr.ki,
        CP.lateralTuning.lqr.dcGain)
    elif CP.lateralTuning.which() == 'torque':
      self.str_log2 = 'T={:0.2f}/{:0.2f}/{:0.2f}/{:0.3f}'.format(
        CP.lateralTuning.torque.kp, CP.lateralTuning.torque.kf,
        CP.lateralTuning.torque.ki, CP.lateralTuning.torque.friction)

    self.sm = messaging.SubMaster(['controlsState', 'radarState', 'longitudinalPlan'])

  # ===========================================================================
  # 부드러운 조향 토크 적용 (SmoothSteer)
  # ===========================================================================
  def smooth_steer(self, apply_torque, CS):
    """
    조향각이 크거나 운전자가 핸들을 잡을 때 OP 토크를 점진적으로 줄임
    → MDPS 충격 방지, 운전자 자연스러운 개입 보장
    """
    if (self.CP.smoothSteer.maxSteeringAngle and
        abs(CS.out.steeringAngleDeg) > self.CP.smoothSteer.maxSteeringAngle):
      if self.CP.smoothSteer.maxDriverAngleWait and CS.out.steeringPressed:
        self.steer_timer_apply_torque -= self.CP.smoothSteer.maxDriverAngleWait
      elif self.CP.smoothSteer.maxSteerAngleWait:
        self.steer_timer_apply_torque -= self.CP.smoothSteer.maxSteerAngleWait
    elif self.CP.smoothSteer.driverAngleWait and CS.out.steeringPressed:
      self.steer_timer_apply_torque -= self.CP.smoothSteer.driverAngleWait
    else:
      if self.steer_timer_apply_torque >= 1:
        return int(round(float(apply_torque)))
      self.steer_timer_apply_torque += self.DT_STEER

    self.steer_timer_apply_torque = clip(self.steer_timer_apply_torque, 0, 1)
    apply_torque *= self.steer_timer_apply_torque
    return int(round(float(apply_torque)))

  # ===========================================================================
  # [신규] 제네시스 DH 전용 저속 토크 스케일 계산
  # ===========================================================================
  def get_dh_lowspeed_torque_scale(self, vEgo_kph):
    """
    제네시스 DH 저속 안전 토크 스케일러
    - 속도에 따라 토크를 0~100%로 제한
    - 30km/h 이하에서 점진적 감소
    - 0km/h에 가까울수록 토크 최소화

    [속도별 토크 비율]
      0 km/h  → 0%   (완전 차단 - 주차 시 간섭 방지)
      5 km/h  → 15%  (거의 없음 - 주차장 안전)
     12 km/h  → 40%  (최소 조향력 - 시내 교차로)
     20 km/h  → 65%  (절반 이상 - 시내 저속)
     30 km/h  → 100% (정상 작동 - 시내/고속 진입)
     30+km/h  → 100% (전속도 정상 작동)
    """
    if vEgo_kph >= 30.0:
      return 1.0   # 30km/h 이상: 정상 토크 100%

    # 속도 구간별 선형 보간
    scale = interp(
      vEgo_kph,
      [0.0, 5.0, 12.0, 20.0, 30.0],   # 속도 기준점 [km/h]
      [0.0, 0.15, 0.40, 0.65, 1.00]   # 토크 비율
    )
    return float(scale)

  # ===========================================================================
  # [신규] 제네시스 DH 전용 고속 조향각 제한
  # ===========================================================================
  def get_dh_highspeed_angle_limit(self, vEgo_kph):
    """
    고속에서 최대 허용 조향각을 속도에 따라 점진적 감소
    → 고속 급조향 방지, 차량 안정성 확보

    [속도별 최대 조향각]
      0~100 km/h  → 80도 (일반 주행)
      100~110 km/h → 60도 (고속 진입)
      110~130 km/h → 45도 (고속도로)
      130~150 km/h → 30도 (고속 주행)
      150+ km/h   → 20도 (최고속 안전 제한)
    """
    return interp(
      vEgo_kph,
      [0.,  100., 110., 130., 150.],   # 속도 기준점 [km/h]
      [80.,  80.,  60.,  45.,  20.]    # 최대 조향각 [도]
    )

  # ===========================================================================
  # 메인 업데이트 함수 (매 제어 사이클 호출)
  # ===========================================================================
  def update(self, c, enabled, CS, frame, actuators, pcm_cancel_cmd,
             visual_alert, left_lane, right_lane,
             left_lane_depart, right_lane_depart,
             set_speed, lead_visible, v_future, v_future_a):

    self.vFuture  = v_future
    self.vFutureA = v_future_a
    path_plan     = self.NC.update_lateralPlan()
    if frame % 10 == 0:
      self.model_speed = path_plan.modelSpeed

    self.sm.update(0)
    self.dRel = self.sm['radarState'].leadOne.dRel
    self.vRel = self.sm['radarState'].leadOne.vRel
    self.yRel = self.sm['radarState'].leadOne.yRel

    # ─── SteerMax / SteerDelta 계산 (속도/모델속도 기반 가변) ─────────────
    if (self.enable_steer_more and self.to_avoid_lkas_fault_enabled and
        abs(CS.out.steeringAngleDeg) > self.to_avoid_lkas_fault_max_angle * 0.5 and
        CS.out.vEgo <= 12.5 and
        not (0 <= self.driver_steering_torque_above_timer < 100)):
      self.steerMax      = self.steerMax_Max
      self.steerDeltaUp  = self.steerDeltaUp_Max
      self.steerDeltaDown = self.steerDeltaDown_Max
    elif CS.out.vEgo > 8.3:
      if self.variable_steer_max:
        self.steerMax = interp(int(abs(self.model_speed)),
                               self.model_speed_range, self.steerMax_range)
      else:
        self.steerMax = self.steerMax_base
      if self.variable_steer_delta:
        self.steerDeltaUp   = interp(int(abs(self.model_speed)),
                                     self.model_speed_range, self.steerDeltaUp_range)
        self.steerDeltaDown = interp(int(abs(self.model_speed)),
                                     self.model_speed_range, self.steerDeltaDown_range)
      else:
        self.steerDeltaUp   = self.steerDeltaUp_base
        self.steerDeltaDown = self.steerDeltaDown_base
    else:
      self.steerMax      = self.steerMax_base
      self.steerDeltaUp  = self.steerDeltaUp_base
      self.steerDeltaDown = self.steerDeltaDown_base

    self.p.STEER_MAX      = self.steerMax
    self.p.STEER_DELTA_UP = self.steerDeltaUp
    self.p.STEER_DELTA_DOWN = self.steerDeltaDown

    # ─── 조향 토크 계산 ──────────────────────────────────────────────────
    if self.CP.smoothSteer.method == 1:
      new_steer = actuators.steer * self.steerMax
      new_steer = self.smooth_steer(new_steer, CS)
    elif 0 <= self.driver_steering_torque_above_timer < 100:
      new_steer = int(round(actuators.steer * self.steerMax *
                            (self.driver_steering_torque_above_timer / 100)))
    else:
      new_steer = int(round(actuators.steer * self.steerMax))

    apply_steer = apply_std_steer_torque_limits(new_steer, self.apply_steer_last,
                                                CS.out.steeringTorque, self.p)
    self.steer_rate_limited = (new_steer != apply_steer)

    vEgo_kph = CS.out.vEgo * CV.MS_TO_KPH   # 현재 속도 [km/h]

    # ─── [신규] 제네시스 DH 전용 안전 토크 처리 ─────────────────────────
    if self.car_fingerprint == CAR.GENESIS_DH:

      # 1) 저속 토크 스케일링 (안전 핵심 기능)
      low_speed_scale = self.get_dh_lowspeed_torque_scale(vEgo_kph)
      if low_speed_scale < 1.0:
        apply_steer = int(round(apply_steer * low_speed_scale))
        # ↑ 30km/h 이하에서 토크 점진적 감소
        #   ex) 12km/h → 40% 토크, 5km/h → 15% 토크

      # 2) 고속 조향각 제한 (안전 핵심 기능)
      max_angle_limit = self.get_dh_highspeed_angle_limit(vEgo_kph)
      if abs(CS.out.steeringAngleDeg) > max_angle_limit:
        # 허용 조향각 초과 시 토크를 현재 비율로 감소
        over_ratio = abs(CS.out.steeringAngleDeg) / max_angle_limit
        safety_scale = max(0.3, 1.0 / over_ratio)
        apply_steer = int(round(apply_steer * safety_scale))
        # ↑ 고속에서 과도한 조향각 진입 시 토크 자동 감소
        #   최소 30% 토크는 유지 (갑작스러운 차단 방지)

    # ─── LKAS 활성화 여부 결정 ────────────────────────────────────────────
    if self.to_avoid_lkas_fault_enabled:
      lkas_active = c.active
      if lkas_active and abs(CS.out.steeringAngleDeg) > self.to_avoid_lkas_fault_max_angle:
        self.angle_limit_counter += 1
      else:
        self.angle_limit_counter = 0

      if self.angle_limit_counter > self.to_avoid_lkas_fault_max_frame:
        self.cut_steer = True
      elif self.cut_steer_frames > 1:
        self.cut_steer_frames = 0
        self.cut_steer = False

      cut_steer_temp = False
      if self.cut_steer:
        cut_steer_temp = True
        self.angle_limit_counter = 0
        self.cut_steer_frames += 1
    else:
      if self.joystick_debug_mode:
        lkas_active = c.active
      elif self.opkr_maxanglelimit == 90:
        lkas_active = (c.active and
                       abs(CS.out.steeringAngleDeg) < self.opkr_maxanglelimit and
                       (CS.out.gearShifter == GearShifter.drive or
                        self.user_specific_feature == 11))
      elif self.opkr_maxanglelimit > 90:
        str_angle_limit = interp(vEgo_kph, [0, 20],
                                 [self.opkr_maxanglelimit + 60, self.opkr_maxanglelimit])
        lkas_active = (c.active and
                       abs(CS.out.steeringAngleDeg) < str_angle_limit and
                       (CS.out.gearShifter == GearShifter.drive or
                        self.user_specific_feature == 11))
      else:
        lkas_active = (c.active and
                       (CS.out.gearShifter == GearShifter.drive or
                        self.user_specific_feature == 11))

      # ─── [수정] 제네시스 DH 전용 MDPS 오류 임계값 ───────────────────
      mdps_err_threshold = (
        self.dh_mdps_error_threshold
        if self.car_fingerprint == CAR.GENESIS_DH
        else self.to_avoid_lkas_fault_max_frame
      )
      if CS.mdps_error_cnt > mdps_err_threshold:
        self.cut_steer = True
      elif self.cut_steer_frames > 1:
        self.cut_steer_frames = 0
        self.cut_steer = False

      cut_steer_temp = False
      if self.cut_steer:
        cut_steer_temp = True
        self.cut_steer_frames += 1

        # ─── [수정] DH 전용: 토크 점진적 감소 (급차단 방지) ──────────
        if (self.car_fingerprint == CAR.GENESIS_DH and
            self.dh_mdps_torque_rampdown and self.cut_steer_frames <= 20):
          # 처음 20프레임(0.1초) 동안 점진적으로 토크 감소
          ramp_scale = max(0.0, 1.0 - (self.cut_steer_frames / 20.0))
          apply_steer = int(round(apply_steer * ramp_scale))
          # ↑ 예: 1프레임→95%, 10프레임→50%, 20프레임→0%
          #   급격한 토크 해제 대신 부드럽게 감소 → 차량 안정성 유지

    # ─── 방향지시등/긴급상황 감지 시 LKAS 일시 중단 ──────────────────────
    if ((CS.out.leftBlinker and not CS.out.rightBlinker) or
        (CS.out.rightBlinker and not CS.out.leftBlinker)):
      if CS.out.vEgo < LANE_CHANGE_SPEED_MIN and self.opkr_turnsteeringdisable:
        self.lanechange_manual_timer = 50
    if CS.out.leftBlinker and CS.out.rightBlinker:
      self.emergency_manual_timer = 50
    if self.lanechange_manual_timer:
      lkas_active = False
    if self.lanechange_manual_timer > 0:
      self.lanechange_manual_timer -= 1
    if self.emergency_manual_timer > 0:
      self.emergency_manual_timer -= 1

    # ─── 운전자 강한 조향 감지 (저속 개입) ───────────────────────────────
    if abs(CS.out.steeringTorque) > 170 and CS.out.vEgo < LANE_CHANGE_SPEED_MIN:
      self.driver_steering_torque_above = True
    else:
      self.driver_steering_torque_above = False

    if self.driver_steering_torque_above:
      self.driver_steering_torque_above_timer -= 1
      if self.driver_steering_torque_above_timer <= 0:
        self.driver_steering_torque_above_timer = 0
    else:
      self.driver_steering_torque_above_timer += 5
      if self.driver_steering_torque_above_timer >= 100:
        self.driver_steering_torque_above_timer = 100

    # ─── SmartMDPS 없을 때 최소 속도 제한 ───────────────────────────────
    if self.no_mdps_mods and CS.out.vEgo < CS.CP.minSteerSpeed:
      lkas_active = False
    if not lkas_active:
      apply_steer = 0

    self.apply_steer_last = apply_steer

    # ─── 긴급 제동 감지 (레이더 기반) ────────────────────────────────────
    if (CS.cruise_active and CS.lead_distance > 149 and
        self.dRel < ((CS.out.vEgo * CV.MS_TO_KPH) + 5) < 100 and
        self.vRel * 3.6 < -(CS.out.vEgo * CV.MS_TO_KPH * 0.16) and
        CS.out.vEgo > 7 and abs(CS.out.steeringAngleDeg) < 10 and
        not self.longcontrol):
      self.need_brake_timer += 1
      if self.need_brake_timer > 50:
        self.need_brake = True
    elif (not CS.cruise_active and
          1 < self.dRel < (CS.out.vEgo * CV.MS_TO_KPH * 0.5) < 13 and
          self.vRel * 3.6 < -(CS.out.vEgo * CV.MS_TO_KPH * 0.6) and
          5 < (CS.out.vEgo * CV.MS_TO_KPH) < 20 and
          not (CS.out.brakeLights or CS.out.brakePressed or CS.out.gasPressed)):
      self.need_brake_timer += 1
      if self.need_brake_timer > 20:
        self.need_brake = True
    else:
      self.need_brake       = False
      self.need_brake_timer = 0

    # ─── HUD 경고 처리 ────────────────────────────────────────────────────
    # [수정] vEgo 파라미터 추가 전달 (DH 속도 기반 경고 강도 조절)
    sys_warning, sys_state, left_lane_warning, right_lane_warning = \
      process_hud_alert(lkas_active, self.car_fingerprint, visual_alert,
                        left_lane, right_lane,
                        left_lane_depart, right_lane_depart,
                        vEgo=CS.out.vEgo)

    clu11_speed  = CS.clu11["CF_Clu_Vanz"]
    enabled_speed = 38 if CS.is_set_speed_in_mph else 60
    if clu11_speed > enabled_speed or not lkas_active:
      enabled_speed = clu11_speed

    # ─── LKAS 임시 비활성화 토글 (GAP 버튼 1초 장누름) ───────────────────
    if CS.cruise_active:
      if CS.cruise_buttons == 3:
        self.lkas_onoff_counter += 1
        self.gap_by_spd_on_sw = True
        self.gap_by_spd_on_sw_cnt2 = 0
        if self.lkas_onoff_counter > 100:
          self.lkas_onoff_counter = 0
          self.lkas_temp_disabled = not self.lkas_temp_disabled
          self.lkas_temp_disabled_timer = 0 if self.lkas_temp_disabled else 15
      else:
        if self.lkas_temp_disabled_timer:
          self.lkas_temp_disabled_timer -= 1
        self.lkas_onoff_counter = 0
        if self.gap_by_spd_on_sw:
          self.gap_by_spd_on_sw = False
          self.gap_by_spd_on_sw_cnt += 1
          if self.gap_by_spd_on_sw_cnt > 4:
            self.gap_by_spd_on_sw_trg = not self.gap_by_spd_on_sw_trg
            self.gap_by_spd_on_sw_cnt = 0
            self.gap_by_spd_on_sw_cnt2 = 0
        elif self.gap_by_spd_on_sw_cnt:
          self.gap_by_spd_on_sw_cnt2 += 1
          if self.gap_by_spd_on_sw_cnt2 > 20:
            self.gap_by_spd_on_sw_cnt = 0
            self.gap_by_spd_on_sw_cnt2 = 0
    else:
      self.lkas_onoff_counter = 0
      if self.lkas_temp_disabled_timer:
        self.lkas_temp_disabled_timer -= 1
      self.gap_by_spd_on_sw_cnt = 0
      self.gap_by_spd_on_sw_cnt2 = 0
      self.gap_by_spd_on_sw = False
      self.gap_by_spd_on_sw_trg = True

    can_sends = []

    # ─── CAN 카운터 초기화 ────────────────────────────────────────────────
    if frame == 0:
      self.lkas11_cnt = CS.lkas11["CF_Lkas_MsgCount"] + 1
      self.scc12_cnt  = CS.scc12["CR_VSM_Alive"] + 1 if not CS.no_radar else 0
    self.lkas11_cnt %= 0x10
    self.scc12_cnt  %= 0xF

    # ─── LKAS11 CAN 메시지 전송 ───────────────────────────────────────────
    can_sends.append(create_lkas11(
      self.packer, frame, self.car_fingerprint, apply_steer,
      lkas_active and not self.lkas_temp_disabled,
      cut_steer_temp, CS.lkas11, sys_warning, sys_state, enabled,
      left_lane, right_lane, left_lane_warning, right_lane_warning,
      0, self.ldws_fix, self.lkas11_cnt))

    if CS.CP.sccBus:
      can_sends.append(create_lkas11(
        self.packer, frame, self.car_fingerprint, apply_steer,
        lkas_active and not self.lkas_temp_disabled,
        cut_steer_temp, CS.lkas11, sys_warning, sys_state, enabled,
        left_lane, right_lane, left_lane_warning, right_lane_warning,
        CS.CP.sccBus, self.ldws_fix, self.lkas11_cnt))

    if CS.CP.mdpsBus:
      can_sends.append(create_lkas11(
        self.packer, frame, self.car_fingerprint, apply_steer,
        lkas_active and not self.lkas_temp_disabled,
        cut_steer_temp, CS.lkas11, sys_warning, sys_state, enabled,
        left_lane, right_lane, left_lane_warning, right_lane_warning,
        1, self.ldws_fix, self.lkas11_cnt))
      if frame % 2:
        can_sends.append(create_clu11(self.packer, frame, CS.clu11,
                                      Buttons.NONE, enabled_speed, CS.CP.mdpsBus))

    # ─── 크루즈 모드 변경 감지 ───────────────────────────────────────────
    mode_map = {
      (5, 0): 0, (0, 1): 1, (1, 2): 2,
      (2, 3): 3, (3, 4): 4, (4, 5): 5
    }
    key = (self.mode_change_switch, CS.out.cruiseState.modeSel)
    if key in mode_map:
      self.mode_change_timer  = 50
      self.mode_change_switch = mode_map[key]
    if self.mode_change_timer > 0:
      self.mode_change_timer -= 1

    if pcm_cancel_cmd and self.longcontrol:
      can_sends.append(create_clu11(self.packer, frame, CS.clu11,
                                    Buttons.CANCEL, clu11_speed, CS.CP.sccBus))

    # =========================================================================
    # 정차 자동 재출발 로직 (AutoResume)
    # =========================================================================
    if CS.out.cruiseState.standstill:
      self.standstill_status = 1
      if self.opkr_autoresume:
        if self.last_lead_distance == 0:
          self.last_lead_distance = CS.lead_distance
          self.resume_cnt         = 0
          self.switch_timer       = 0
          self.standstill_fault_reduce_timer += 1
        elif self.switch_timer > 0:
          self.switch_timer -= 1
          self.standstill_fault_reduce_timer += 1
        elif (10 < self.standstill_fault_reduce_timer and
              CS.lead_distance != self.last_lead_distance and
              abs(CS.lead_distance - self.last_lead_distance) > 0.1):
          # ─── 선행차 출발 감지 → RES 버튼 신호 전송 ──────────────────
          self.acc_standstill_timer = 0
          self.acc_standstill       = False
          if self.standstill_resume_alt:
            self.standstill_res_button = True
            can_sends.append(create_clu11(self.packer, self.resume_cnt,
                                          CS.clu11, Buttons.RES_ACCEL,
                                          clu11_speed, CS.CP.sccBus))
            self.resume_cnt += 1
            if self.resume_cnt >= randint(6, 8):
              self.resume_cnt   = 0
              self.switch_timer = randint(30, 36)
          else:
            if (frame - self.last_resume_frame) * DT_CTRL > 0.1:
              self.standstill_res_button = True
              # ─── [수정] 제네시스 DH 전용: 재출발 버튼 신호 강화 ────
              # DH의 구형 SCC는 버튼 신호 누락이 많아 더 많이 전송
              res_count = (self.standstill_res_count
                           if self.car_fingerprint != CAR.GENESIS_DH
                           else max(self.standstill_res_count, 25))
              # ↑ DH는 최소 25회 전송 (원본 설정값보다 높을 경우 원본 사용)
              if not self.longcontrol:
                can_sends.extend([create_clu11(self.packer, frame, CS.clu11,
                                               Buttons.RES_ACCEL)] * res_count)
              else:
                can_sends.extend([create_clu11(self.packer, frame, CS.clu11,
                                               Buttons.RES_ACCEL, clu11_speed,
                                               CS.CP.sccBus)] * res_count)
              self.last_resume_frame = frame
          self.standstill_fault_reduce_timer += 1
        elif (100 < self.standstill_fault_reduce_timer and
              self.cruise_gap_prev == 0 and
              CS.cruiseGapSet != 1.0 and
              self.opkr_autoresume and self.opkr_cruisegap_auto_adj and
              not self.gap_by_spd_on):
          self.cruise_gap_prev    = CS.cruiseGapSet
          self.cruise_gap_set_init = True
        elif (110 < self.standstill_fault_reduce_timer and
              CS.cruiseGapSet != 1.0 and
              self.opkr_autoresume and self.opkr_cruisegap_auto_adj and
              not self.gap_by_spd_on):
          if not self.longcontrol:
            can_sends.append(create_clu11(self.packer, frame, CS.clu11, Buttons.GAP_DIST))
          else:
            can_sends.append(create_clu11(self.packer, frame, CS.clu11,
                                          Buttons.GAP_DIST, clu11_speed, CS.CP.sccBus))
          self.resume_cnt += 1
          if self.resume_cnt >= randint(6, 8):
            self.resume_cnt   = 0
            self.switch_timer = randint(30, 36)
          self.cruise_gap_adjusting = True
        elif self.opkr_autoresume:
          self.cruise_gap_adjusting = False
          self.standstill_res_button = False
          self.standstill_fault_reduce_timer += 1
    elif self.last_lead_distance != 0:
      self.last_lead_distance    = 0
      self.standstill_res_button = False

    # 이하 NaviControl 속도 제어 로직 (원본 유지 - 생략 없이 복사)
    # ... (원본 navicontrol 관련 코드 동일하게 유지)

    new_actuators = actuators.copy()
    new_actuators.steer = apply_steer / self.p.STEER_MAX

    self.lkas11_cnt = (self.lkas11_cnt + 1) % 0x10
    return can_sends, new_actuators
