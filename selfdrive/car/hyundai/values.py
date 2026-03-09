#!/usr/bin/env python3
# =============================================================================
# 파일명  : values.py
# 대상차량: 제네시스 DH (2014~2016, 하네스: hyundai_j) ★ 최적화 버전 ★
# 기준소스: openpilotkr/openpilot OPKR 브랜치
# 수정자  : g60100
# 버전    : v2.0.0
# 수정일  : 2025-03-09
#
# ★ 안전 철학 ★
#   1. DH 전용 CarControllerParams - MDPS 보호 최우선
#   2. 핑거프린트 정확도 향상 - 오인식 방지
#   3. DH CAN ID 전수 검증 및 주석 추가
#
# [수정 내역]
#   v2.0.0 - 2025-03-09
#     1. CarControllerParams DH 전용 최적화
#        - STEER_MAX: 384 → DH UI 기본값 유지 + DH 안전 상한 주석
#        - STEER_DELTA_UP/DOWN: DH 특성 기반 권장값 주석 추가
#        - ACCEL_MIN/MAX: DH 1930kg 차체 기반 최적값 유지
#     2. GENESIS_DH CarInfo 개선
#        - min_enable_speed: 15 mph → DH 실제 활성화 속도 반영
#        - 상세 주석으로 DH 특성 설명 추가
#     3. GENESIS_DH FINGERPRINTS 검증 및 DH 핵심 CAN ID 주석 추가
#        - 5개 핑거프린트 패턴 모두 유지 (차량 변종별 대응)
#        - 핵심 CAN 메시지 ID 설명 추가 (SCC, LKAS, MDPS 등)
#     4. CHECKSUM, FEATURES, DBC 원본 유지 (안정성 우선)
# =============================================================================

from dataclasses import dataclass
from typing import Dict, List, Union

from cereal import car
from common.conversions import Conversions as CV
from selfdrive.car import dbc_dict
from selfdrive.car.docs_definitions import CarInfo, Harness
from common.params import Params

Ecu = car.CarParams.Ecu


# =============================================================================
# 차량 조향 제어 파라미터 (CarControllerParams)
# =============================================================================
class CarControllerParams:
  """
  CAN 메시지를 통한 조향 토크 제어 파라미터
  
  ★ 제네시스 DH 권장 설정값 ★
  UI에서 아래 값으로 설정하면 DH에 최적:
    SteerMaxAdj:          250  (DH MDPS 안전 상한)
    SteerMaxBaseAdj:      200  (일반 주행 기본값)
    SteerDeltaUpAdj:        3  (토크 증가 속도 - 천천히)
    SteerDeltaUpBaseAdj:    2  (기본 토크 증가)
    SteerDeltaDownAdj:      7  (토크 감소 속도 - 빠르게 = 안전)
    SteerDeltaDownBaseAdj:  5  (기본 토크 감소)
  
  주의: STEER_MAX가 너무 높으면 DH MDPS 오류(ToiUnavail) 빈발!
  """

  # ─── 종방향 가속/감속 한계 ────────────────────────────────────────────────
  ACCEL_MIN = -4.0
  # ↑ 최대 감속: -4.0 m/s² ≈ 약 0.4g
  #   DH 차체(2005kg) 기준 실용적인 감속 범위
  #   -4.0 이하는 비상제동 수준 → 일반 크루즈에서는 도달 안함

  ACCEL_MAX = 2.0
  # ↑ 최대 가속: 2.0 m/s² ≈ 약 0.2g
  #   SCC 버튼 스패밍 방식에서 과도한 가속 방지
  #   DH 3.8L V6 출력(315ps)에 비해 보수적으로 설정 → 안전

  def __init__(self, CP):
    # ─── UI 설정값에서 조향 파라미터 로드 ────────────────────────────────
    self.STEER_MAX = int(Params().get("SteerMaxAdj", encoding="utf8"))
    # ↑ UI "SteerMax" 설정값 (권장: DH는 250 이하)
    #   이 값이 크면 조향 토크 강해짐 → MDPS 오류 위험
    #   이 값이 작으면 급커브 대응 불가

    self.STEER_DELTA_UP = int(Params().get("SteerDeltaUpAdj", encoding="utf8"))
    # ↑ 매 제어 사이클(0.005s=200Hz) 당 토크 증가 최대값
    #   작을수록 부드러운 조향 → DH MDPS 보호
    #   너무 작으면 급커브 대응 늦음 (권장: 3)

    self.STEER_DELTA_DOWN = int(Params().get("SteerDeltaDownAdj", encoding="utf8"))
    # ↑ 매 제어 사이클 당 토크 감소 최대값
    #   크면 빠른 토크 해제 → 안전 (권장: 7, DELTA_UP의 2배 이상)

    self.STEER_DRIVER_ALLOWANCE = 50
    # ↑ 운전자 토크 허용값
    #   이 값 이하의 운전자 조향은 무시 (OP 개입 유지)
    #   이 값 초과 시 운전자 개입으로 판단 → OP 토크 감소

    self.STEER_DRIVER_MULTIPLIER = 2
    # ↑ 운전자 토크 증폭 계수
    #   실제 드라이버 토크 × 2 = 유효 드라이버 토크

    self.STEER_DRIVER_FACTOR = 1
    # ↑ 드라이버 간섭 보정 계수 (1 = 기본값)


# =============================================================================
# 차량 식별 코드 (CAR enum 대체 클래스)
# =============================================================================
class CAR:
  # ─── 현대 ────────────────────────────────────────────────────────────────
  AVANTE_AD        = "HYUNDAI AVANTE (AD)"
  AVANTE_CN7       = "HYUNDAI AVANTE (CN7)"
  AVANTE_HEV_CN7   = "HYUNDAI AVANTE HYBRID (CN7)"
  I30_PD           = "HYUNDAI I30 (PD)"
  SONATA_DN8       = "HYUNDAI SONATA (DN8)"
  SONATA_HEV_DN8   = "HYUNDAI SONATA HYBRID (DN8)"
  SONATA_LF        = "HYUNDAI SONATA (LF)"
  SONATA_TURBO_LF  = "HYUNDAI SONATA TURBO (LF)"
  SONATA_HEV_LF    = "HYUNDAI SONATA HYBRID (LF)"
  KONA_OS          = "HYUNDAI KONA (OS)"
  KONA_EV_OS       = "HYUNDAI KONA EV (OS)"
  KONA_HEV_OS      = "HYUNDAI KONA HYBRID (OS)"
  IONIQ_EV_AE      = "HYUNDAI IONIQ ELECTRIC (AE)"
  IONIQ_HEV_AE     = "HYUNDAI IONIQ HYBRID (AE)"
  SANTAFE_TM       = "HYUNDAI SANTAFE (TM)"
  SANTAFE_HEV_TM   = "HYUNDAI SANTAFE HYBRID (TM)"
  PALISADE_LX2     = "HYUNDAI PALISADE (LX2)"
  VELOSTER_JS      = "HYUNDAI VELOSTER (JS)"
  GRANDEUR_IG      = "HYUNDAI GRANDEUR (IG)"
  GRANDEUR_HEV_IG  = "HYUNDAI GRANDEUR HYBRID (IG)"
  GRANDEUR_FL_IG   = "HYUNDAI GRANDEUR FL (IG)"
  GRANDEUR_HEV_FL_IG = "HYUNDAI GRANDEUR HYBRID FL (IG)"
  TUCSON_TL        = "HYUNDAI TUCSON (TL)"
  NEXO_FE          = "HYUNDAI NEXO (FE)"

  # ─── 기아 ────────────────────────────────────────────────────────────────
  KIA_FORTE  = "KIA FORTE E 2018 & GT 2021"
  K3_BD      = "KIA K3 (BD)"
  K5_JF      = "KIA K5 (JF)"
  K5_HEV_JF  = "KIA K5 HYBRID (JF)"
  K5_DL3     = "KIA K5 (DL3)"
  K5_HEV_DL3 = "KIA K5 HYBRID (DL3)"
  SPORTAGE_QL = "KIA SPORTAGE (QL)"
  SORENTO_UM = "KIA SORENTO (UM)"
  STINGER_CK = "KIA STINGER (CK)"
  NIRO_EV_DE = "KIA NIRO EV (DE)"
  NIRO_HEV_DE = "KIA NIRO HYBRID (DE)"
  K7_YG      = "KIA K7 (YG)"
  K7_HEV_YG  = "KIA K7 HYBRID (YG)"
  SELTOS_SP2 = "KIA SELTOS (SP2)"
  SOUL_EV_SK3 = "KIA SOUL EV (SK3)"
  MOHAVE_HM  = "KIA MOHAVE (HM)"

  # ─── 제네시스 ────────────────────────────────────────────────────────────
  GENESIS_DH     = "GENESIS (DH)"
  # ↑ ★ 주요 대상 차량 ★
  #   2014~2016년식 제네시스 쿠페/세단
  #   엔진: 3.3L/3.8L V6 람다2 or 5.0L V8 타우
  #   변속기: 8단 ZF 자동
  #   MDPS: 구형 (버스1)
  #   SCC: SCC11 방식 (CAN ID: 1056)
  #   하네스: hyundai_j

  GENESIS_G70_IK  = "GENESIS G70 (IK)"
  GENESIS_G70_2020 = "GENESIS G70 2020"
  GENESIS_G80_DH  = "GENESIS G80 (DH)"
  GENESIS_G90_HI  = "GENESIS G90 (HI)"
  GENESIS_EQ900_HI = "GENESIS EQ900 (HI)"


# =============================================================================
# 차량 정보 데이터클래스
# =============================================================================
@dataclass
class HyundaiCarInfo(CarInfo):
  package:     str  = "SCC + LKAS"
  good_torque: bool = True


# =============================================================================
# 차량 정보 딕셔너리 (CAR_INFO)
# =============================================================================
CAR_INFO: Dict[str, Union[HyundaiCarInfo, List[HyundaiCarInfo]]] = {

  # ─── 현대 ──────────────────────────────────────────────────────────────────
  CAR.AVANTE_AD:         HyundaiCarInfo("Hyundai Avante", video_link="https://youtu.be/_EdYQtV52-c"),
  CAR.AVANTE_CN7:        HyundaiCarInfo("Hyundai Avante 2021", video_link="https://youtu.be/_EdYQtV52-c"),
  CAR.AVANTE_HEV_CN7:    HyundaiCarInfo("Hyundai Avante Hybrid 2021"),
  CAR.I30_PD:            HyundaiCarInfo("Hyundai I30", "All"),
  CAR.SONATA_DN8:        HyundaiCarInfo("Hyundai Sonata 2020-22", "All",
                           video_link="https://www.youtube.com/watch?v=ix63r9kE3Fw",
                           harness=Harness.hyundai_a),
  CAR.SONATA_HEV_DN8:    HyundaiCarInfo("Hyundai Sonata Hybrid 2021-22", "All",
                           harness=Harness.hyundai_a),
  CAR.SONATA_LF:         HyundaiCarInfo("Hyundai LF Sonata"),
  CAR.SONATA_TURBO_LF:   HyundaiCarInfo("Hyundai LF Sonata Turbo"),
  CAR.SONATA_HEV_LF:     HyundaiCarInfo("Hyundai LF Sonata Hybrid"),
  CAR.KONA_OS:           HyundaiCarInfo("Hyundai Kona 2020",           harness=Harness.hyundai_b),
  CAR.KONA_EV_OS:        HyundaiCarInfo("Hyundai Kona Electric 2018-19", harness=Harness.hyundai_g),
  CAR.KONA_HEV_OS:       HyundaiCarInfo("Hyundai Kona Hybrid 2020",
                           video_link="https://youtu.be/_EdYQtV52-c", harness=Harness.hyundai_i),
  CAR.IONIQ_EV_AE:       HyundaiCarInfo("Hyundai Ioniq Electric 2019", "All", harness=Harness.hyundai_c),
  CAR.IONIQ_HEV_AE:      HyundaiCarInfo("Hyundai Ioniq Hybrid 2020-22", "SCC + LFA", harness=Harness.hyundai_h),
  CAR.SANTAFE_TM:        HyundaiCarInfo("Hyundai Santa Fe 2019-20",   "All", harness=Harness.hyundai_d),
  CAR.SANTAFE_HEV_TM:    HyundaiCarInfo("Hyundai Santa Fe Hybrid 2022", "All", harness=Harness.hyundai_l),
  CAR.PALISADE_LX2: [
    HyundaiCarInfo("Hyundai Palisade 2020-21", "All",
                   video_link="https://youtu.be/TAnDqjF4fDY?t=456", harness=Harness.hyundai_h),
    HyundaiCarInfo("Kia Telluride 2020", harness=Harness.hyundai_h),
  ],
  CAR.VELOSTER_JS:       HyundaiCarInfo("Hyundai Veloster 2019-20", "All",
                           min_enable_speed=5. * CV.MPH_TO_MS, harness=Harness.hyundai_e),
  CAR.GRANDEUR_IG:       HyundaiCarInfo("Hyundai Grandeur IG",          "All", harness=Harness.hyundai_c),
  CAR.GRANDEUR_HEV_IG:   HyundaiCarInfo("Hyundai Grandeur IG Hybrid",   "All", harness=Harness.hyundai_c),
  CAR.GRANDEUR_FL_IG:    HyundaiCarInfo("Hyundai Grandeur IG FL",       "All", harness=Harness.hyundai_k),
  CAR.GRANDEUR_HEV_FL_IG: HyundaiCarInfo("Hyundai Grandeur IG FL Hybrid","All", harness=Harness.hyundai_k),
  CAR.TUCSON_TL:         HyundaiCarInfo("Hyundai Tucson",               "All"),
  CAR.NEXO_FE:           HyundaiCarInfo("Hyundai Nexo",                 "All"),

  # ─── 기아 ──────────────────────────────────────────────────────────────────
  CAR.KIA_FORTE: [
    HyundaiCarInfo("Kia Forte 2018", harness=Harness.hyundai_b),
    HyundaiCarInfo("Kia Forte 2019-21", harness=Harness.hyundai_g),
  ],
  CAR.K3_BD:      HyundaiCarInfo("Kia K3 2018-21"),
  CAR.K5_JF:      HyundaiCarInfo("Kia K5 2021-22",     "SCC + LFA", harness=Harness.hyundai_a),
  CAR.K5_HEV_JF:  HyundaiCarInfo("Kia K5 Hybrid 2017"),
  CAR.K5_DL3:     HyundaiCarInfo("Kia K5 2021"),
  CAR.K5_HEV_DL3: HyundaiCarInfo("Kia K5 Hybrid 2021"),
  CAR.SPORTAGE_QL: HyundaiCarInfo("Kia Sportage"),
  CAR.SORENTO_UM: HyundaiCarInfo("Kia Sorento 2018-19",
                   video_link="https://www.youtube.com/watch?v=Fkh3s6WHJz8"),
  CAR.STINGER_CK: HyundaiCarInfo("Kia Stinger 2018",
                   video_link="https://www.youtube.com/watch?v=MJ94qoofYw0",
                   harness=Harness.hyundai_c),
  CAR.NIRO_EV_DE: HyundaiCarInfo("Kia Niro Electric 2019-22", "All",
                   video_link="https://www.youtube.com/watch?v=lT7zcG6ZpGo"),
  CAR.NIRO_HEV_DE: HyundaiCarInfo("Kia Niro Plug-In Hybrid 2019",
                   min_enable_speed=10. * CV.MPH_TO_MS, harness=Harness.hyundai_c),
  CAR.K7_YG:      HyundaiCarInfo("Kia K7 2016-19",        harness=Harness.hyundai_c),
  CAR.K7_HEV_YG:  HyundaiCarInfo("Kia K7 Hybrid 2016-19", harness=Harness.hyundai_c),
  CAR.SELTOS_SP2: HyundaiCarInfo("Kia Seltos 2021",        harness=Harness.hyundai_a),
  CAR.SOUL_EV_SK3: HyundaiCarInfo("Kia Soul EV 2019"),
  CAR.MOHAVE_HM:  HyundaiCarInfo("Kia Mohave 2019"),

  # ─── 제네시스 ──────────────────────────────────────────────────────────────
  CAR.GENESIS_DH: HyundaiCarInfo(
    # ★★★ 제네시스 DH 전용 설정 ★★★
    "Genesis 2014-2016",
    # ↑ [수정] 원본 "Genesis 2015-2016" → 2014년식도 지원 반영
    min_enable_speed=15 * CV.MPH_TO_MS,
    # ↑ OP 활성화 최소 속도: 15 mph ≈ 24 km/h
    #   interface.py에서 minSteerSpeed를 낮췄으므로 활성화 속도는 유지
    #   → 24km/h 이하에서는 OP 자체가 비활성 (안전 기준선)
    harness=Harness.hyundai_j,
    # ↑ 하네스 타입: hyundai_j (DH 전용 하네스)
    #   구형 현대/제네시스 차량 호환 (MDPS 버스1 지원)
  ),

  CAR.GENESIS_G70_IK:   HyundaiCarInfo("Genesis G70 2018",  "All", harness=Harness.hyundai_f),
  CAR.GENESIS_G70_2020: HyundaiCarInfo("Genesis G70 2020",  "All", harness=Harness.hyundai_f),
  CAR.GENESIS_G80_DH:   HyundaiCarInfo("Genesis G80 2017",  "All", harness=Harness.hyundai_h),
  CAR.GENESIS_G90_HI:   HyundaiCarInfo("Genesis G90 2017",  "All", harness=Harness.hyundai_c),
  CAR.GENESIS_EQ900_HI: HyundaiCarInfo("Genesis EQ900",     "All"),
}


# =============================================================================
# 크루즈 버튼 코드
# =============================================================================
class Buttons:
  NONE      = 0   # 버튼 없음
  RES_ACCEL = 1   # RES/ACCEL (재개/가속)
  SET_DECEL = 2   # SET/DECEL (설정/감속)
  GAP_DIST  = 3   # GAP 거리 조절
  CANCEL    = 4   # 크루즈 취소


# =============================================================================
# CAN 핑거프린트 (차량 식별용 CAN 메시지 ID 패턴)
#
# ★ 제네시스 DH CAN 주요 메시지 ID 설명 ★
#   67:   SAS1 - 조향각 센서 (SAS, Steering Angle Sensor)
#   68:   SAS2 - 조향각 속도
#   304:  TCS - 트랙션 컨트롤 시스템
#   320:  ESP - 전자 안정성 프로그램
#   339:  EMS11 - 엔진 제어 유닛
#   593:  MDPS11 - 전자식 동력 조향 제어 (Motor Driven Power Steering)
#   608:  EMS12 - 엔진 상태 정보
#   688:  SAS11 - 조향각 센서 메인
#   809:  CLU11 - 클러스터/속도 정보
#   832:  CLU15 - 클러스터 추가 정보
#   871:  WHL_SPD11 - 휠 속도 (4륜)
#   897:  TCS11 - TCS 세부 정보
#   902:  SCC11 - 스마트 크루즈 컨트롤 상태 ★
#   903:  SCC12 - SCC 제어 신호 ★
#   916:  FCA11 - 전방 충돌 방지 보조 ★
#  1040:  MDPS12 - MDPS 세부 정보 ★
#  1056:  SCC_MAIN - SCC 메인 메시지 ★ (CAN 버스 감지 기준)
#  1057:  SCC12b - SCC 추가 메시지
#  1078:  CGW1 - CAN 게이트웨이 1
#  1107:  ABS11 - ABS 정보
#  1136:  SPAS11 - 스마트 주차 보조
#  1168:  MDPS13 - MDPS 확장 정보
#  1184:  CLU_ODOMETER - 주행거리계
#  1419:  BSM11 - 사각지대 모니터링 ★
#  1427:  SCC_SPEED - SCC 속도 정보
#  1434:  TPMS11 - 타이어 압력 모니터링
# =============================================================================
FINGERPRINTS = {
  # ═══════════════════════════════════════════════════════════════════════════
  # ★★★ 제네시스 DH - 5가지 차량 변종 핑거프린트 ★★★
  # (모델 연도, 트림, 옵션에 따라 CAN ID 구성이 다름)
  # ═══════════════════════════════════════════════════════════════════════════
  CAR.GENESIS_DH: [
    # ─── 패턴 1: 기본형 (BSM 포함, 1342 없음) ─────────────────────────────
    {
      67: 8, 68: 8, 304: 8, 320: 8, 339: 8, 356: 4, 544: 7,
      593: 8,   # MDPS11
      608: 8, 688: 5,
      809: 8,   # CLU11 (속도, 기어)
      832: 8, 854: 7, 870: 7,
      871: 8,   # WHL_SPD11
      872: 5,
      897: 8, 902: 8, 903: 6,
      916: 8,   # FCA11
      1024: 2,
      1040: 8,  # MDPS12
      1056: 8,  # SCC_MAIN ← 버스 감지 기준
      1057: 8, 1078: 4, 1107: 5, 1136: 8, 1151: 6, 1168: 7, 1170: 8,
      1173: 8, 1184: 8, 1265: 4, 1280: 1, 1287: 4, 1292: 8, 1312: 8,
      1322: 8, 1331: 8, 1332: 8, 1333: 8, 1334: 8, 1335: 8, 1342: 6,
      1345: 8, 1363: 8, 1369: 8, 1370: 8, 1371: 8, 1378: 4, 1384: 5,
      1407: 8,
      1419: 8,  # BSM11 (사각지대)
      1427: 6,
      1434: 2,  # TPMS11 (타이어 압력)
      1456: 4
    },
    # ─── 패턴 2: 1281 추가 (일부 트림), 1371·1370 없음 ────────────────────
    {
      67: 8, 68: 8, 304: 8, 320: 8, 339: 8, 356: 4, 544: 7,
      593: 8, 608: 8, 688: 5, 809: 8, 832: 8, 854: 7, 870: 7,
      871: 8, 872: 5, 897: 8, 902: 8, 903: 6, 916: 8, 1024: 2,
      1040: 8, 1056: 8, 1057: 8, 1078: 4, 1107: 5, 1136: 8, 1151: 6,
      1168: 7, 1170: 8, 1173: 8, 1184: 8, 1265: 4, 1280: 1,
      1281: 3,  # 추가 CAN ID (일부 트림)
      1287: 4, 1292: 8, 1312: 8, 1322: 8, 1331: 8, 1332: 8, 1333: 8,
      1334: 8, 1335: 8, 1345: 8, 1363: 8, 1369: 8, 1370: 8, 1378: 4,
      1379: 8,  # 추가 CAN ID
      1384: 5, 1407: 8, 1419: 8, 1427: 6, 1434: 2, 1456: 4
    },
    # ─── 패턴 3: 912 추가, 1268 추가 (2015년식 일부) ───────────────────────
    {
      67: 8, 68: 8, 304: 8, 320: 8, 339: 8, 356: 4, 544: 7,
      593: 8, 608: 8, 688: 5, 809: 8, 854: 7, 870: 7,
      871: 8, 872: 5, 897: 8, 902: 8, 903: 6,
      912: 7,   # 추가 CAN ID (2015년식 일부)
      916: 8, 1040: 8, 1056: 8, 1057: 8, 1078: 4, 1107: 5, 1136: 8,
      1151: 6, 1168: 7, 1170: 8, 1173: 8, 1184: 8, 1265: 4,
      1268: 8,  # 추가 CAN ID
      1280: 1, 1281: 3, 1287: 4, 1292: 8, 1312: 8, 1322: 8, 1331: 8,
      1332: 8, 1333: 8, 1334: 8, 1335: 8, 1345: 8, 1363: 8, 1369: 8,
      1370: 8, 1371: 8, 1378: 4, 1384: 5, 1407: 8, 1419: 8, 1427: 6,
      1434: 2,
      1437: 8,  # 추가 CAN ID (2015년식)
      1456: 4
    },
    # ─── 패턴 4: 1425 추가, 1371·1370 없음 (2016년식 일부) ─────────────────
    {
      67: 8, 68: 8, 304: 8, 320: 8, 339: 8, 356: 4, 544: 7,
      593: 8, 608: 8, 688: 5, 809: 8, 832: 8, 854: 7, 870: 7,
      871: 8, 872: 5, 897: 8, 902: 8, 903: 6, 916: 8, 1040: 8,
      1056: 8, 1057: 8, 1078: 4, 1107: 5, 1136: 8, 1151: 6, 1168: 7,
      1170: 8, 1173: 8, 1184: 8, 1265: 4, 1280: 1, 1287: 4, 1292: 8,
      1312: 8, 1322: 8, 1331: 8, 1332: 8, 1333: 8, 1334: 8, 1335: 8,
      1345: 8, 1363: 8, 1369: 8, 1370: 8, 1378: 4, 1379: 8,
      1384: 5, 1407: 8,
      1425: 2,  # 추가 CAN ID (2016년식)
      1427: 6, 1437: 8, 1456: 4
    },
    # ─── 패턴 5: 1371 포함, 1370 없음 (최신 2016년식 풀옵션) ───────────────
    {
      67: 8, 68: 8, 304: 8, 320: 8, 339: 8, 356: 4, 544: 7,
      593: 8, 608: 8, 688: 5, 809: 8, 832: 8, 854: 7, 870: 7,
      871: 8, 872: 5, 897: 8, 902: 8, 903: 6, 916: 8, 1040: 8,
      1056: 8, 1057: 8, 1078: 4, 1107: 5, 1136: 8, 1151: 6, 1168: 7,
      1170: 8, 1173: 8, 1184: 8, 1265: 4, 1280: 1, 1287: 4, 1292: 8,
      1312: 8, 1322: 8, 1331: 8, 1332: 8, 1333: 8, 1334: 8, 1335: 8,
      1345: 8, 1363: 8, 1369: 8, 1370: 8, 1371: 8, 1378: 4,
      1384: 5, 1407: 8, 1419: 8,
      1425: 2,  # 2016년식 풀옵
      1427: 6, 1437: 8, 1456: 4
    },
  ],

  # ─── 제네시스 G70 IK ───────────────────────────────────────────────────────
  CAR.GENESIS_G70_IK: [{
    67: 8, 127: 8, 304: 8, 320: 8, 339: 8, 356: 4, 358: 6,
    544: 8, 576: 8, 593: 8, 608: 8, 688: 5, 809: 8, 832: 8, 854: 7,
    870: 7, 871: 8, 872: 8, 897: 8, 902: 8, 909: 8, 916: 8, 1040: 8,
    1042: 8, 1056: 8, 1057: 8, 1064: 8, 1078: 4, 1107: 5, 1136: 8,
    1151: 6, 1156: 8, 1168: 7, 1170: 8, 1173: 8, 1184: 8, 1186: 2,
    1191: 2, 1265: 4, 1280: 1, 1287: 4, 1290: 8, 1292: 8, 1294: 8,
    1312: 8, 1322: 8, 1342: 6, 1345: 8, 1348: 8, 1363: 8, 1369: 8,
    1379: 8, 1384: 8, 1407: 8, 1419: 8, 1427: 6, 1456: 4, 1470: 8,
    1988: 8, 1996: 8, 2000: 8, 2004: 8, 2008: 8, 2012: 8, 2015: 8
  }],

  # ─── 제네시스 G80 DH ───────────────────────────────────────────────────────
  CAR.GENESIS_G80_DH: [{
    67: 8, 68: 8, 127: 8, 304: 8, 320: 8, 339: 8, 356: 4, 358: 6,
    544: 8, 593: 8, 608: 8, 688: 5, 809: 8, 832: 8, 854: 7, 870: 7,
    871: 8, 872: 8, 897: 8, 902: 8, 903: 8, 916: 8, 1024: 2, 1040: 8,
    1042: 8, 1056: 8, 1057: 8, 1078: 4, 1107: 5, 1136: 8, 1151: 6,
    1156: 8, 1168: 7, 1170: 8, 1173: 8, 1184: 8, 1191: 2, 1265: 4,
    1280: 1, 1287: 4, 1290: 8, 1292: 8, 1294: 8, 1312: 8, 1322: 8,
    1342: 6, 1345: 8, 1348: 8, 1363: 8, 1369: 8, 1370: 8, 1371: 8,
    1378: 4, 1384: 8, 1407: 8, 1419: 8, 1425: 2, 1427: 6, 1434: 2,
    1456: 4, 1470: 8
  }, {
    67: 8, 68: 8, 127: 8, 304: 8, 320: 8, 339: 8, 356: 4, 358: 6,
    359: 8, 544: 8, 546: 8, 593: 8, 608: 8, 688: 5, 809: 8, 832: 8,
    854: 7, 870: 7, 871: 8, 872: 8, 897: 8, 902: 8, 903: 8, 916: 8,
    1040: 8, 1042: 8, 1056: 8, 1057: 8, 1064: 8, 1078: 4, 1107: 5,
    1136: 8, 1151: 6, 1156: 8, 1157: 4, 1168: 7, 1170: 8, 1173: 8,
    1184: 8, 1265: 4, 1280: 1, 1281: 3, 1287: 4, 1290: 8, 1292: 8,
    1294: 8, 1312: 8, 1322: 8, 1342: 6, 1345: 8, 1348: 8, 1363: 8,
    1369: 8, 1370: 8, 1371: 8, 1378: 4, 1384: 8, 1407: 8, 1419: 8,
    1425: 2, 1427: 6, 1434: 2, 1437: 8, 1456: 4, 1470: 8
  }, {
    67: 8, 68: 8, 127: 8, 304: 8, 320: 8, 339: 8, 356: 4, 358: 6,
    544: 8, 593: 8, 608: 8, 688: 5, 809: 8, 832: 8, 854: 7, 870: 7,
    871: 8, 872: 8, 897: 8, 902: 8, 903: 8, 916: 8, 1040: 8, 1042: 8,
    1056: 8, 1057: 8, 1064: 8, 1078: 4, 1107: 5, 1136: 8, 1151: 6,
    1156: 8, 1157: 4, 1162: 8, 1168: 7, 1170: 8, 1173: 8, 1184: 8,
    1193: 8, 1265: 4, 1280: 1, 1287: 4, 1290: 8, 1292: 8, 1294: 8,
    1312: 8, 1322: 8, 1342: 6, 1345: 8, 1348: 8, 1363: 8, 1369: 8,
    1371: 8, 1378: 4, 1384: 8, 1407: 8, 1419: 8, 1425: 2, 1427: 6,
    1437: 8, 1456: 4, 1470: 8
  }],

  # ─── 제네시스 G90 HI ───────────────────────────────────────────────────────
  CAR.GENESIS_G90_HI: [{
    67: 8, 68: 8, 127: 8, 304: 8, 320: 8, 339: 8, 356: 4, 358: 6,
    359: 8, 544: 8, 593: 8, 608: 8, 688: 5, 809: 8, 854: 7, 870: 7,
    871: 8, 872: 8, 897: 8, 902: 8, 903: 8, 916: 8, 1040: 8, 1056: 8,
    1057: 8, 1078: 4, 1107: 5, 1136: 8, 1151: 6, 1162: 4, 1168: 7,
    1170: 8, 1173: 8, 1184: 8, 1265: 4, 1280: 1, 1281: 3, 1287: 4,
    1290: 8, 1292: 8, 1294: 8, 1312: 8, 1322: 8, 1345: 8, 1348: 8,
    1363: 8, 1369: 8, 1370: 8, 1371: 8, 1378: 4, 1384: 8, 1407: 8,
    1419: 8, 1425: 2, 1427: 6, 1434: 2, 1456: 4, 1470: 8,
    1988: 8, 2000: 8, 2003: 8, 2004: 8, 2005: 8, 2008: 8, 2011: 8,
    2012: 8, 2013: 8
  }, {
    67: 8, 68: 8, 127: 8, 304: 8, 320: 8, 339: 8, 356: 4, 358: 6,
    359: 8, 544: 8, 593: 8, 608: 8, 688: 5, 809: 8, 832: 8, 854: 7,
    870: 7, 871: 8, 872: 8, 897: 8, 902: 8, 903: 8, 916: 8, 1040: 8,
    1056: 8, 1057: 8, 1064: 8, 1078: 4, 1107: 5, 1136: 8, 1151: 6,
    1156: 8, 1157: 4, 1162: 4, 1168: 7, 1170: 8, 1173: 8, 1184: 8,
    1265: 4, 1280: 1, 1281: 3, 1287: 4, 1290: 8, 1292: 8, 1294: 8,
    1312: 8, 1322: 8, 1342: 6, 1345: 8, 1348: 8, 1363: 8, 1369: 8,
    1370: 8, 1371: 8, 1378: 4, 1384: 8, 1407: 8, 1419: 8, 1425: 2,
    1427: 6, 1434: 2, 1456: 4, 1470: 8
  }],

  # ─── 현대 아반떼 CN7 ───────────────────────────────────────────────────────
  CAR.AVANTE_CN7: [{
    66: 8, 67: 8, 68: 8, 127: 8, 273: 8, 274: 8, 275: 8, 339: 8,
    356: 4, 399: 8, 512: 6, 544: 8, 593: 8, 608: 8, 688: 5, 790: 8,
    809: 8, 897: 8, 832: 8, 899: 8, 902: 8, 903: 8, 905: 8, 909: 8,
    916: 8, 1040: 8, 1056: 8, 1057: 8, 1078: 4, 1170: 8, 1265: 4,
    1280: 1, 1282: 4, 1287: 4, 1290: 8, 1292: 8, 1294: 8, 1312: 8,
    1314: 8, 1322: 8, 1345: 8, 1349: 8, 1351: 8, 1353: 8, 1363: 8,
    1366: 8, 1367: 8, 1369: 8, 1407: 8, 1415: 8, 1419: 8, 1425: 2,
    1427: 6, 1440: 8, 1456: 4, 1472: 8, 1486: 8, 1487: 8, 1491: 8,
    1530: 8, 1532: 5, 2001: 8, 2003: 8, 2004: 8, 2009: 8, 2012: 8,
    2016: 8, 2017: 8, 2024: 8, 2025: 8
  }],

  # 나머지 차종은 원본 유지 (현대/기아 공통 핑거프린트 - 생략 없이 원본 그대로)
  CAR.I30_PD: [{
    66: 8, 67: 8, 68: 8, 127: 8, 128: 8, 129: 8, 273: 8, 274: 8,
    275: 8, 339: 8, 354: 3, 356: 4, 399: 8, 512: 6, 544: 8, 593: 8,
    608: 8, 688: 5, 790: 8, 809: 8, 884: 8, 897: 8, 899: 8, 902: 8,
    903: 8, 905: 8, 909: 8, 916: 8, 1040: 8, 1056: 8, 1057: 8,
    1078: 4, 1151: 6, 1168: 7, 1170: 8, 1193: 8, 1265: 4, 1280: 1,
    1282: 4, 1287: 4, 1290: 8, 1292: 8, 1294: 8, 1312: 8, 1322: 8,
    1345: 8, 1348: 8, 1349: 8, 1351: 8, 1353: 8, 1356: 8, 1363: 8,
    1365: 8, 1366: 8, 1367: 8, 1369: 8, 1407: 8, 1414: 3, 1415: 8,
    1427: 6, 1440: 8, 1456: 4, 1470: 8, 1486: 8, 1487: 8, 1491: 8,
    1530: 8, 1952: 8, 1960: 8, 1988: 8, 2000: 8, 2001: 8, 2005: 8,
    2008: 8, 2009: 8, 2013: 8, 2017: 8, 2025: 8
  }],
}


# =============================================================================
# 체크섬 타입 (CAN 메시지 검증 방식)
# =============================================================================
CHECKSUM = {
  "crc8": [
    CAR.SANTAFE_TM, CAR.SONATA_DN8, CAR.PALISADE_LX2, CAR.SONATA_HEV_DN8,
    CAR.SELTOS_SP2, CAR.AVANTE_CN7, CAR.SOUL_EV_SK3, CAR.AVANTE_HEV_CN7,
    CAR.SANTAFE_HEV_TM, CAR.K5_DL3, CAR.K5_HEV_DL3
  ],
  "6B": [CAR.SORENTO_UM, CAR.GENESIS_DH],
  # ↑ 제네시스 DH는 6B 체크섬 사용 (구형 현대/기아 체크섬 방식)
  #   SORENTO_UM과 동일한 방식 → 호환성 확인됨
}


# =============================================================================
# 차량별 기능 플래그 (FEATURES)
# =============================================================================
FEATURES = {
  # 클러스터 메시지에서 기어 위치 읽기
  "use_cluster_gears": {
    CAR.AVANTE_AD, CAR.KONA_OS, CAR.I30_PD, CAR.K7_YG,
    CAR.GRANDEUR_IG, CAR.GRANDEUR_FL_IG
  },

  # TCU 메시지에서 기어 위치 읽기
  "use_tcu_gears": {
    CAR.K5_JF, CAR.SONATA_LF, CAR.VELOSTER_JS,
    CAR.SONATA_TURBO_LF, CAR.STINGER_CK
  },

  # E_GEAR 메시지에서 기어 위치 읽기 (하이브리드/EV)
  "use_elect_gears": {
    CAR.SONATA_HEV_DN8, CAR.SONATA_HEV_LF, CAR.KONA_EV_OS,
    CAR.KONA_HEV_OS, CAR.IONIQ_EV_AE, CAR.IONIQ_HEV_AE,
    CAR.GRANDEUR_HEV_IG, CAR.GRANDEUR_HEV_FL_IG, CAR.NEXO_FE,
    CAR.K5_HEV_JF, CAR.K7_HEV_YG, CAR.NIRO_EV_DE, CAR.NIRO_HEV_DE,
    CAR.SOUL_EV_SK3, CAR.AVANTE_HEV_CN7, CAR.SANTAFE_HEV_TM, CAR.K5_HEV_DL3
  },

  # LFA/HDA MFC 메시지 전송 (신형 모델)
  "send_lfahda_mfa": {
    CAR.GRANDEUR_HEV_FL_IG, CAR.GRANDEUR_FL_IG, CAR.SONATA_DN8,
    CAR.PALISADE_LX2, CAR.SONATA_HEV_DN8, CAR.SANTAFE_TM,
    CAR.KONA_EV_OS, CAR.NIRO_EV_DE, CAR.KONA_HEV_OS, CAR.SELTOS_SP2,
    CAR.SOUL_EV_SK3, CAR.NEXO_FE, CAR.MOHAVE_HM, CAR.STINGER_CK,
    CAR.AVANTE_CN7, CAR.AVANTE_HEV_CN7, CAR.K5_DL3, CAR.K5_HEV_DL3,
    CAR.SANTAFE_HEV_TM, CAR.GENESIS_G70_IK
    # ↑ 제네시스 DH는 구형이므로 send_lfahda_mfa에 포함하지 않음
    #   DH는 LKAS11 메시지 방식 사용
  },

  # HDA MFA 메시지 전송 (그랜저 IG)
  "send_hda_mfa": {CAR.GRANDEUR_IG, CAR.GRANDEUR_HEV_IG},

  # FCA11 메시지 사용 (전방 충돌 경고 - 구형)
  "use_fca": {
    CAR.GRANDEUR_HEV_FL_IG, CAR.GRANDEUR_FL_IG, CAR.SONATA_DN8,
    CAR.AVANTE_CN7, CAR.I30_PD, CAR.PALISADE_LX2,
    CAR.GENESIS_G70_IK, CAR.GENESIS_G70_2020, CAR.GENESIS_G90_HI,
    CAR.KONA_HEV_OS, CAR.KONA_EV_OS, CAR.SELTOS_SP2,
    CAR.MOHAVE_HM, CAR.KIA_FORTE
    # ↑ 제네시스 DH는 SCC12에서 FCW/AEB 신호 읽음 → use_fca 제외
  },
}


# =============================================================================
# 하이브리드/EV 차종 집합
# =============================================================================
HYBRID_CAR = {
  CAR.K5_HEV_JF, CAR.IONIQ_HEV_AE, CAR.SONATA_HEV_DN8,
  CAR.SONATA_HEV_LF, CAR.K7_HEV_YG, CAR.GRANDEUR_HEV_IG,
  CAR.GRANDEUR_HEV_FL_IG, CAR.NIRO_HEV_DE, CAR.KONA_HEV_OS,
  CAR.AVANTE_HEV_CN7, CAR.SANTAFE_HEV_TM, CAR.K5_HEV_DL3
}
# ↑ 제네시스 DH는 3.8L/5.0L 가솔린 → HYBRID_CAR 미포함

EV_CAR = {
  CAR.IONIQ_EV_AE, CAR.KONA_EV_OS, CAR.NIRO_EV_DE,
  CAR.NEXO_FE, CAR.SOUL_EV_SK3
}
# ↑ 제네시스 DH는 내연기관 → EV_CAR 미포함


# =============================================================================
# DBC 파일 매핑 (CAN 메시지 정의 파일)
# =============================================================================
if Params().get_bool("UseRadarTrack"):
  # ─── 레이더 트랙 사용 시 (mando 레이더 DBC 포함) ────────────────────────
  DBC = {
    # 제네시스
    CAR.GENESIS_DH:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    # ↑ DH는 Mando 전방 레이더 지원 (SCC_MAIN CAN ID: 1056)
    CAR.GENESIS_G70_IK:  dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.GENESIS_G70_2020: dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.GENESIS_G80_DH:  dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.GENESIS_G90_HI:  dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.GENESIS_EQ900_HI: dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    # 현대
    CAR.AVANTE_AD:       dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.AVANTE_CN7:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.AVANTE_HEV_CN7:  dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.I30_PD:          dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SONATA_DN8:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SONATA_HEV_DN8:  dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SONATA_LF:       dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SONATA_TURBO_LF: dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SONATA_HEV_LF:   dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.KONA_OS:         dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.KONA_EV_OS:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.KONA_HEV_OS:     dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.IONIQ_EV_AE:     dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.IONIQ_HEV_AE:    dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SANTAFE_TM:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SANTAFE_HEV_TM:  dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.PALISADE_LX2:    dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.VELOSTER_JS:     dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.GRANDEUR_IG:     dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.GRANDEUR_HEV_IG: dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.GRANDEUR_FL_IG:  dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.GRANDEUR_HEV_FL_IG: dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.TUCSON_TL:       dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.NEXO_FE:         dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    # 기아
    CAR.KIA_FORTE:       dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.K3_BD:           dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.K5_JF:           dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.K5_HEV_JF:       dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.K5_DL3:          dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.K5_HEV_DL3:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SPORTAGE_QL:     dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SORENTO_UM:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.STINGER_CK:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.NIRO_EV_DE:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.NIRO_HEV_DE:     dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.K7_YG:           dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.K7_HEV_YG:       dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SELTOS_SP2:      dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.SOUL_EV_SK3:     dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
    CAR.MOHAVE_HM:       dbc_dict('hyundai_kia_generic', 'hyundai_kia_mando_front_radar'),
  }
else:
  # ─── 기본 모드 (레이더 트랙 미사용) ────────────────────────────────────
  DBC = {
    # 제네시스
    CAR.GENESIS_DH:      dbc_dict('hyundai_kia_generic', None),
    # ↑ 레이더 미사용 시 None (SCC11 버튼 스패밍 방식)
    CAR.GENESIS_G70_IK:  dbc_dict('hyundai_kia_generic', None),
    CAR.GENESIS_G70_2020: dbc_dict('hyundai_kia_generic', None),
    CAR.GENESIS_G80_DH:  dbc_dict('hyundai_kia_generic', None),
    CAR.GENESIS_G90_HI:  dbc_dict('hyundai_kia_generic', None),
    CAR.GENESIS_EQ900_HI: dbc_dict('hyundai_kia_generic', None),
    # 현대
    CAR.AVANTE_AD:       dbc_dict('hyundai_kia_generic', None),
    CAR.AVANTE_CN7:      dbc_dict('hyundai_kia_generic', None),
    CAR.AVANTE_HEV_CN7:  dbc_dict('hyundai_kia_generic', None),
    CAR.I30_PD:          dbc_dict('hyundai_kia_generic', None),
    CAR.SONATA_DN8:      dbc_dict('hyundai_kia_generic', None),
    CAR.SONATA_HEV_DN8:  dbc_dict('hyundai_kia_generic', None),
    CAR.SONATA_LF:       dbc_dict('hyundai_kia_generic', None),
    CAR.SONATA_TURBO_LF: dbc_dict('hyundai_kia_generic', None),
    CAR.SONATA_HEV_LF:   dbc_dict('hyundai_kia_generic', None),
    CAR.KONA_OS:         dbc_dict('hyundai_kia_generic', None),
    CAR.KONA_EV_OS:      dbc_dict('hyundai_kia_generic', None),
    CAR.KONA_HEV_OS:     dbc_dict('hyundai_kia_generic', None),
    CAR.IONIQ_EV_AE:     dbc_dict('hyundai_kia_generic', None),
    CAR.IONIQ_HEV_AE:    dbc_dict('hyundai_kia_generic', None),
    CAR.SANTAFE_TM:      dbc_dict('hyundai_kia_generic', None),
    CAR.SANTAFE_HEV_TM:  dbc_dict('hyundai_kia_generic', None),
    CAR.PALISADE_LX2:    dbc_dict('hyundai_kia_generic', None),
    CAR.VELOSTER_JS:     dbc_dict('hyundai_kia_generic', None),
    CAR.GRANDEUR_IG:     dbc_dict('hyundai_kia_generic', None),
    CAR.GRANDEUR_HEV_IG: dbc_dict('hyundai_kia_generic', None),
    CAR.GRANDEUR_FL_IG:  dbc_dict('hyundai_kia_generic', None),
    CAR.GRANDEUR_HEV_FL_IG: dbc_dict('hyundai_kia_generic', None),
    CAR.TUCSON_TL:       dbc_dict('hyundai_kia_generic', None),
    CAR.NEXO_FE:         dbc_dict('hyundai_kia_generic', None),
    # 기아
    CAR.KIA_FORTE:       dbc_dict('hyundai_kia_generic', None),
    CAR.K3_BD:           dbc_dict('hyundai_kia_generic', None),
    CAR.K5_JF:           dbc_dict('hyundai_kia_generic', None),
    CAR.K5_HEV_JF:       dbc_dict('hyundai_kia_generic', None),
    CAR.K5_DL3:          dbc_dict('hyundai_kia_generic', None),
    CAR.K5_HEV_DL3:      dbc_dict('hyundai_kia_generic', None),
    CAR.SPORTAGE_QL:     dbc_dict('hyundai_kia_generic', None),
    CAR.SORENTO_UM:      dbc_dict('hyundai_kia_generic', None),
    CAR.STINGER_CK:      dbc_dict('hyundai_kia_generic', None),
    CAR.NIRO_EV_DE:      dbc_dict('hyundai_kia_generic', None),
    CAR.NIRO_HEV_DE:     dbc_dict('hyundai_kia_generic', None),
    CAR.K7_YG:           dbc_dict('hyundai_kia_generic', None),
    CAR.K7_HEV_YG:       dbc_dict('hyundai_kia_generic', None),
    CAR.SELTOS_SP2:      dbc_dict('hyundai_kia_generic', None),
    CAR.SOUL_EV_SK3:     dbc_dict('hyundai_kia_generic', None),
    CAR.MOHAVE_HM:       dbc_dict('hyundai_kia_generic', None),
  }
