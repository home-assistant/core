"""Constants for the Luxtronik integration."""
# region Imports
from enum import Enum
import logging
from typing import Final

# endregion Imports

# region Constants Main
DOMAIN = "luxtronik"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: Final = "luxtronik_Key"
# endregion Constants Main

# region Conf
CONF_COORDINATOR: Final = "coordinator"

CONF_PARAMETERS: Final = "parameters"
CONF_CALCULATIONS: Final = "calculations"
CONF_VISIBILITIES: Final = "visibilities"

CONF_HA_SENSOR_PREFIX: Final = "ha_sensor_prefix"

DEFAULT_HOST: Final = "wp-novelan"
DEFAULT_PORT: Final = 8889
# endregion Conf

# region Lux Definitions


class DeviceKey(Enum):
    """Device keys."""

    heatpump: Final = "heatpump"
    heating: Final = "heating"
    domestic_water: Final = "domestic_water"
    cooling: Final = "cooling"


class FirmwareVersionMinor(Enum):
    """Firmware minor versions."""

    minor_88: Final = 88


class LuxOperationMode(Enum):
    """Lux Operation modes heating, hot water etc."""

    heating: Final = "heating"  # 0
    domestic_water: Final = "hot water"  # 1
    swimming_pool_solar: Final = "swimming pool/solar"  # 2
    evu: Final = "evu"  # 3
    defrost: Final = "defrost"  # 4
    no_request: Final = "no request"  # 5
    heating_external_source: Final = "heating external source"  # 6
    cooling: Final = "cooling"  # 7


class LuxMode(Enum):
    """Luxmodes off etc."""

    off: Final = "Off"
    automatic: Final = "Automatic"
    second_heatsource: Final = "Second heatsource"
    party: Final = "Party"
    holidays: Final = "Holidays"


class LuxMkTypes(Enum):
    """LuxMkTypes etc."""

    off: Final = 0
    discharge: Final = 1
    load: Final = 2
    cooling: Final = 3
    heating_cooling: Final = 4


LUX_PARAMETER_MK_SENSORS: Final = [
    "parameters.ID_Einst_MK1Typ_akt",
    "parameters.ID_Einst_MK2Typ_akt",
    "parameters.ID_Einst_MK3Typ_akt",
]

LUX_MODELS_ALPHA_INNOTEC = ["LWP", "LWV", "MSW", "SWC", "SWP"]
LUX_MODELS_NOVELAN = ["BW", "LA", "LD", "LI", "SI", "ZLW"]
LUX_MODELS_OTHER = ["CB", "CI", "CN", "CS"]
# endregion Lux Definitions

# region Lux parameters


class LuxParameter(Enum):
    """Luxtronik parameter ids."""

    UNSET: Final = None
    P0001_HEATING_TARGET_CORRECTION: Final = "parameters.ID_Einst_WK_akt"
    P0002_DOMESTIC_WATER_TARGET_TEMPERATURE: Final = "parameters.ID_Einst_BWS_akt"
    P0003_MODE_HEATING: Final = "parameters.ID_Ba_Hz_akt"
    P0004_MODE_DOMESTIC_WATER: Final = "parameters.ID_Ba_Bw_akt"
    P0011_HEATING_CIRCUIT_CURVE1_TEMPERATURE: Final = "parameters.ID_Einst_HzHwHKE_akt"
    P0012_HEATING_CIRCUIT_CURVE2_TEMPERATURE: Final = "parameters.ID_Einst_HzHKRANH_akt"
    P0013_HEATING_CIRCUIT_CURVE_NIGHT_TEMPERATURE: Final = (
        "parameters.ID_Einst_HzHKRABS_akt"
    )
    P0047_DOMESTIC_WATER_THERMAL_DESINFECTION_TARGET: Final = (
        "parameters.ID_Einst_LGST_akt"
    )
    P0049_PUMP_OPTIMIZATION: Final = "parameters.ID_Einst_Popt_akt"
    P0033_ROOM_THERMOSTAT_TYPE: Final = "parameters.ID_Einst_RFVEinb_akt"
    P0074_DOMESTIC_WATER_HYSTERESIS: Final = "parameters.ID_Einst_BWS_Hyst_akt"
    P0088_HEATING_HYSTERESIS: Final = "parameters.ID_Einst_HRHyst_akt"
    P0089_HEATING_MAX_FLOW_OUT_INCREASE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TRErhmax_akt"
    )
    P0090_RELEASE_SECOND_HEAT_GENERATOR: Final = "parameters.ID_Einst_ZWEFreig_akt"
    P0108_MODE_COOLING: Final = "parameters.ID_Einst_BA_Kuehl_akt"
    P0111_HEATING_NIGHT_LOWERING_TO_TEMPERATURE: Final = (
        "parameters.ID_Einst_TAbsMin_akt"
    )
    P0122_SOLAR_PUMP_ON_DIFFERENCE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TDC_Ein_akt"
    )
    P0123_SOLAR_PUMP_OFF_DIFFERENCE_TEMPERATURE: Final = (
        "parameters.ID_Einst_TDC_Aus_akt"
    )
    P0289_SOLAR_PUMP_OFF_MAX_DIFFERENCE_TEMPERATURE_BOILER: Final = (
        "parameters.ID_Einst_TDC_Max_akt"
    )
    P0699_HEATING_THRESHOLD: Final = "parameters.ID_Einst_Heizgrenze"
    P0700_HEATING_THRESHOLD_TEMPERATURE: Final = "parameters.ID_Einst_Heizgrenze_Temp"
    P0860_REMOTE_MAINTENANCE: Final = "parameters.ID_Einst_Fernwartung_akt"
    P0864_PUMP_OPTIMIZATION_TIME: Final = "parameters.ID_Einst_Popt_Nachlauf_akt"
    P0869_EFFICIENCY_PUMP: Final = "parameters.ID_Einst_Effizienzpumpe_akt"
    P0870_AMOUNT_COUNTER_ACTIVE: Final = "parameters.ID_Einst_Waermemenge_akt"
    P0874_SERIAL_NUMBER: Final = "parameters.ID_WP_SerienNummer_DATUM"
    P0875_SERIAL_NUMBER_MODEL: Final = "parameters.ID_WP_SerienNummer_HEX"
    P0882_SOLAR_OPERATION_HOURS: Final = "parameters.ID_BSTD_Solar"
    P0883_SOLAR_PUMP_MAX_TEMPERATURE_COLLECTOR: Final = (
        "parameters.ID_Einst_TDC_Koll_Max_akt"
    )
    P0979_HEATING_MIN_FLOW_OUT_TEMPERATURE: Final = (
        "parameters.ID_Einst_Minimale_Ruecklaufsolltemperatur"
    )
    P0980_HEATING_ROOM_TEMPERATURE_IMPACT_FACTOR: Final = (
        "parameters.ID_RBE_Einflussfaktor_RT_akt"
    )
    P0992_RELEASE_TIME_SECOND_HEAT_GENERATOR: Final = (
        "parameters.ID_Einst_Freigabe_Zeit_ZWE"
    )
    P1032_HEATING_MAXIMUM_CIRCULATION_PUMP_SPEED: Final = (
        "parameters.ID_Einst_P155_PumpHeat_Max"
    )
    P1033_PUMP_HEAT_CONTROL: Final = "parameters.ID_Einst_P155_PumpHeatCtrl"
    P1059_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER: Final = (
        "parameters.ID_Waermemenge_ZWE"
    )


# endregion Lux parameters

# region Lux calculations
class LuxCalculation(Enum):
    """Luxtronik calculation ids."""

    UNSET: Final = None
    C0012_FLOW_OUT_TEMPERATURE_TARGET: Final = "calculations.ID_WEB_Sollwert_TRL_HZ"
    C0014_HOT_GAS_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_THG"
    C0015_OUTDOOR_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TA"
    C0016_OUTDOOR_TEMPERATURE_AVERAGE: Final = "calculations.ID_WEB_Mitteltemperatur"
    C0017_DOMESTIC_WATER_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TBW"
    C0020_HEAT_SOURCE_OUTPUT_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TWA"
    C0026_SOLAR_COLLECTOR_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TSK"
    C0027_SOLAR_BUFFER_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TSS"
    C0056_COMPRESSOR1_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitVD1"
    C0057_COMPRESSOR1_IMPULSES: Final = "calculations.ID_WEB_Zaehler_BetrZeitImpVD1"
    C0058_COMPRESSOR2_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitVD2"
    C0059_COMPRESSOR2_IMPULSES: Final = "calculations.ID_WEB_Zaehler_BetrZeitImpVD2"
    C0060_ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS: Final = (
        "calculations.ID_WEB_Zaehler_BetrZeitZWE1"
    )
    C0063_OPERATION_HOURS: Final = "calculations.ID_WEB_Zaehler_BetrZeitWP"
    C0078_MODEL_CODE: Final = "calculations.ID_WEB_Code_WP_akt"
    C0080_STATUS: Final = "calculations.ID_WEB_WP_BZ_akt"
    C0081_FIRMWARE_VERSION: Final = "calculations.ID_WEB_SoftStand"
    C0117_STATUS_LINE_1: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile1"
    C0118_STATUS_LINE_2: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile2"
    C0119_STATUS_LINE_3: Final = "calculations.ID_WEB_HauptMenuStatus_Zeile3"
    C0120_STATUS_TIME: Final = "calculations.ID_WEB_HauptMenuStatus_Zeit"
    C0154_HEAT_AMOUNT_COUNTER: Final = "calculations.ID_WEB_WMZ_Seit"
    C0156_ANALOG_OUT1: Final = "calculations.ID_WEB_AnalogOut1"
    C0157_ANALOG_OUT2: Final = "calculations.ID_WEB_AnalogOut2"
    C0175_SUCTION_EVAPORATOR_TEMPERATURE: Final = (
        "calculations.ID_WEB_LIN_ANSAUG_VERDAMPFER"
    )
    C0176_SUCTION_COMPRESSOR_TEMPERATURE: Final = (
        "calculations.ID_WEB_LIN_ANSAUG_VERDICHTER"
    )
    C0177_COMPRESSOR_HEATING_TEMPERATURE: Final = "calculations.ID_WEB_LIN_VDH"
    C0178_OVERHEATING_TEMPERATURE: Final = "calculations.ID_WEB_LIN_UH"
    C0179_OVERHEATING_TARGET_TEMPERATURE: Final = "calculations.ID_WEB_LIN_UH_Soll"
    C0180_HIGH_PRESSURE: Final = "calculations.ID_WEB_LIN_HD"
    C0181_LOW_PRESSURE: Final = "calculations.ID_WEB_LIN_ND"
    C0204_HEAT_SOURCE_INPUT_TEMPERATURE: Final = "calculations.ID_WEB_Temperatur_TWE"
    C0227_ROOM_THERMOSTAT_TEMPERATURE: Final = "calculations.ID_WEB_RBE_RT_Ist"
    C0228_ROOM_THERMOSTAT_TEMPERATURE_TARGET: Final = "calculations.ID_WEB_RBE_RT_Soll"
    C0231_PUMP_FREQUENCY: Final = "calculations.ID_WEB_Freq_VD"
    C0257_CURRENT_HEAT_OUTPUT: Final = "calculations.Heat_Output"


# endregion Lux calculations

# region visibilities
class LuxVisibility(Enum):
    """Luxtronik visibility ids."""

    UNSET: Final = None
    V0023_FLOW_IN_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_Vorlauf"
    V0027_HOT_GAS_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_Heissgas"
    V0029_DOMESTIC_WATER_TEMPERATURE: Final = "visibilities.ID_Visi_Temp_BW_Ist"
    V0038_SOLAR_COLLECTOR: Final = "visibilities.ID_Visi_Temp_Solarkoll"
    V0039_SOLAR_BUFFER: Final = "visibilities.ID_Visi_Temp_Solarsp"
    V0061_SECOND_HEAT_GENERATOR: Final = "visibilities.ID_Visi_OUT_ZWE1"
    V0080_COMPRESSOR1_OPERATION_HOURS: Final = "visibilities.ID_Visi_Bst_BStdVD1"
    V0081_COMPRESSOR1_IMPULSES: Final = "visibilities.ID_Visi_Bst_ImpVD1"
    V0083_COMPRESSOR2_OPERATION_HOURS: Final = "visibilities.ID_Visi_Bst_BStdVD2"
    V0084_COMPRESSOR2_IMPULSES: Final = "visibilities.ID_Visi_Bst_ImpVD2"
    V0086_ADDITIONAL_HEAT_GENERATOR_OPERATION_HOURS: Final = (
        "visibilities.ID_Visi_Bst_BStdZWE1"
    )
    V0122_ROOM_THERMOSTAT: Final = "visibilities.ID_Visi_SysEin_Raumstation"
    V0144_PUMP_OPTIMIZATION: Final = "visibilities.ID_Visi_SysEin_Pumpenoptim"
    V0248_ANALOG_OUT1: Final = "visibilities.ID_Visi_OUT_Analog_1"
    V0249_ANALOG_OUT2: Final = "visibilities.ID_Visi_OUT_Analog_2"
    V0250_SOLAR: Final = "visibilities.ID_Visi_Solar"
    V0289_SUCTION_COMPRESSOR_TEMPERATURE: Final = (
        "visibilities.ID_Visi_LIN_ANSAUG_VERDICHTER"
    )
    V0290_COMPRESSOR_HEATING_TEMPERATURE: Final = "visibilities.ID_Visi_LIN_VDH"
    V0291_OVERHEATING_TEMPERATURE: Final = "visibilities.ID_Visi_LIN_UH"
    V0292_LIN_PRESSURE: Final = "visibilities.ID_Visi_LIN_Druck"
    V0310_SUCTION_EVAPORATOR_TEMPERATURE: Final = (
        "visibilities.ID_Visi_LIN_ANSAUG_VERDAMPFER"
    )
    V0324_ADDITIONAL_HEAT_GENERATOR_AMOUNT_COUNTER: Final = (
        "visibilities.ID_Visi_Waermemenge_ZWE"
    )


# endregion visibilities
