"""KNX DPT serializer."""

from collections.abc import Mapping
from functools import cache
from typing import Literal, TypedDict

from xknx.dpt import DPTBase, DPTComplex, DPTEnum, DPTNumeric
from xknx.dpt.dpt_16 import DPTString

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

HaDptClass = Literal["numeric", "enum", "complex", "string"]


class DPTInfo(TypedDict):
    """DPT information."""

    dpt_class: HaDptClass
    main: int
    sub: int | None
    name: str | None
    unit: str | None
    sensor_device_class: SensorDeviceClass | None
    sensor_state_class: SensorStateClass | None


@cache
def get_supported_dpts() -> Mapping[str, DPTInfo]:
    """Return a mapping of supported DPTs with HA specific attributes."""
    dpts = {}
    for dpt_class in DPTBase.dpt_class_tree():
        dpt_number_str = dpt_class.dpt_number_str()
        ha_dpt_class = _ha_dpt_class(dpt_class)
        dpts[dpt_number_str] = DPTInfo(
            dpt_class=ha_dpt_class,
            main=dpt_class.dpt_main_number,  # type: ignore[typeddict-item] # checked in xknx unit tests
            sub=dpt_class.dpt_sub_number,
            name=dpt_class.value_type,
            unit=dpt_class.unit,
            sensor_device_class=_sensor_device_classes.get(dpt_number_str),
            sensor_state_class=_get_sensor_state_class(ha_dpt_class, dpt_number_str),
        )
    return dpts


def _ha_dpt_class(dpt_cls: type[DPTBase]) -> HaDptClass:
    """Return the DPT class identifier string."""
    if issubclass(dpt_cls, DPTNumeric):
        return "numeric"
    if issubclass(dpt_cls, DPTEnum):
        return "enum"
    if issubclass(dpt_cls, DPTComplex):
        return "complex"
    if issubclass(dpt_cls, DPTString):
        return "string"
    raise ValueError("Unsupported DPT class")


_sensor_device_classes: Mapping[str, SensorDeviceClass] = {
    "7.011": SensorDeviceClass.DISTANCE,
    "7.012": SensorDeviceClass.CURRENT,
    "7.013": SensorDeviceClass.ILLUMINANCE,
    "8.012": SensorDeviceClass.DISTANCE,
    "9.001": SensorDeviceClass.TEMPERATURE,
    "9.002": SensorDeviceClass.TEMPERATURE_DELTA,
    "9.004": SensorDeviceClass.ILLUMINANCE,
    "9.005": SensorDeviceClass.WIND_SPEED,
    "9.006": SensorDeviceClass.PRESSURE,
    "9.007": SensorDeviceClass.HUMIDITY,
    "9.020": SensorDeviceClass.VOLTAGE,
    "9.021": SensorDeviceClass.CURRENT,
    "9.024": SensorDeviceClass.POWER,
    "9.025": SensorDeviceClass.VOLUME_FLOW_RATE,
    "9.027": SensorDeviceClass.TEMPERATURE,
    "9.028": SensorDeviceClass.WIND_SPEED,
    "9.029": SensorDeviceClass.ABSOLUTE_HUMIDITY,
    "12.1200": SensorDeviceClass.VOLUME,
    "12.1201": SensorDeviceClass.VOLUME,
    "13.002": SensorDeviceClass.VOLUME_FLOW_RATE,
    "13.010": SensorDeviceClass.ENERGY,
    "13.012": SensorDeviceClass.REACTIVE_ENERGY,
    "13.013": SensorDeviceClass.ENERGY,
    "13.015": SensorDeviceClass.REACTIVE_ENERGY,
    "13.016": SensorDeviceClass.ENERGY,
    "13.1200": SensorDeviceClass.VOLUME,
    "13.1201": SensorDeviceClass.VOLUME,
    "14.010": SensorDeviceClass.AREA,
    "14.019": SensorDeviceClass.CURRENT,
    "14.027": SensorDeviceClass.VOLTAGE,
    "14.028": SensorDeviceClass.VOLTAGE,
    "14.030": SensorDeviceClass.VOLTAGE,
    "14.031": SensorDeviceClass.ENERGY,
    "14.033": SensorDeviceClass.FREQUENCY,
    "14.037": SensorDeviceClass.ENERGY_STORAGE,
    "14.039": SensorDeviceClass.DISTANCE,
    "14.051": SensorDeviceClass.WEIGHT,
    "14.056": SensorDeviceClass.POWER,
    "14.057": SensorDeviceClass.POWER_FACTOR,
    "14.058": SensorDeviceClass.PRESSURE,
    "14.065": SensorDeviceClass.SPEED,
    "14.068": SensorDeviceClass.TEMPERATURE,
    "14.069": SensorDeviceClass.TEMPERATURE,
    "14.070": SensorDeviceClass.TEMPERATURE_DELTA,
    "14.076": SensorDeviceClass.VOLUME,
    "14.077": SensorDeviceClass.VOLUME_FLOW_RATE,
    "14.080": SensorDeviceClass.APPARENT_POWER,
    "14.1200": SensorDeviceClass.VOLUME_FLOW_RATE,
    "14.1201": SensorDeviceClass.VOLUME_FLOW_RATE,
    "29.010": SensorDeviceClass.ENERGY,
    "29.012": SensorDeviceClass.REACTIVE_ENERGY,
}

_sensor_state_class_overrides: Mapping[str, SensorStateClass | None] = {
    "5.003": SensorStateClass.MEASUREMENT_ANGLE,  # DPTAngle
    "5.006": None,  # DPTTariff
    "7.010": None,  # DPTPropDataType
    "8.011": SensorStateClass.MEASUREMENT_ANGLE,  # DPTRotationAngle
    "9.026": SensorStateClass.TOTAL_INCREASING,  # DPTRainAmount
    "12.1200": SensorStateClass.TOTAL,  # DPTVolumeLiquidLitre
    "12.1201": SensorStateClass.TOTAL,  # DPTVolumeM3
    "13.010": SensorStateClass.TOTAL,  # DPTActiveEnergy
    "13.011": SensorStateClass.TOTAL,  # DPTApparantEnergy
    "13.012": SensorStateClass.TOTAL,  # DPTReactiveEnergy
    "14.007": SensorStateClass.MEASUREMENT_ANGLE,  # DPTAngleDeg
    "14.037": SensorStateClass.TOTAL,  # DPTHeatQuantity
    "14.051": SensorStateClass.TOTAL,  # DPTMass
    "14.055": SensorStateClass.MEASUREMENT_ANGLE,  # DPTPhaseAngleDeg
    "14.031": SensorStateClass.TOTAL_INCREASING,  # DPTEnergy
    "17.001": None,  # DPTSceneNumber
    "29.010": SensorStateClass.TOTAL,  # DPTActiveEnergy8Byte
    "29.011": SensorStateClass.TOTAL,  # DPTApparantEnergy8Byte
    "29.012": SensorStateClass.TOTAL,  # DPTReactiveEnergy8Byte
}


def _get_sensor_state_class(
    ha_dpt_class: HaDptClass, dpt_number_str: str
) -> SensorStateClass | None:
    """Return the SensorStateClass for a given DPT."""
    if ha_dpt_class != "numeric":
        return None

    return _sensor_state_class_overrides.get(
        dpt_number_str,
        SensorStateClass.MEASUREMENT,
    )
