"""Provides conditions for air quality."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec, NumericalDomainSpec
from homeassistant.helpers.condition import (
    Condition,
    make_entity_numerical_condition,
    make_entity_numerical_condition_with_unit,
    make_entity_state_condition,
)
from homeassistant.util.unit_conversion import (
    CarbonMonoxideConcentrationConverter,
    MassVolumeConcentrationConverter,
    NitrogenDioxideConcentrationConverter,
    NitrogenMonoxideConcentrationConverter,
    OzoneConcentrationConverter,
    SulphurDioxideConcentrationConverter,
    UnitlessRatioConverter,
)


def _make_detected_condition(
    device_class: BinarySensorDeviceClass,
) -> type[Condition]:
    """Create a detected condition for a binary sensor device class."""
    return make_entity_state_condition(
        {BINARY_SENSOR_DOMAIN: DomainSpec(device_class=device_class)}, STATE_ON
    )


def _make_cleared_condition(
    device_class: BinarySensorDeviceClass,
) -> type[Condition]:
    """Create a cleared condition for a binary sensor device class."""
    return make_entity_state_condition(
        {BINARY_SENSOR_DOMAIN: DomainSpec(device_class=device_class)}, STATE_OFF
    )


CONDITIONS: dict[str, type[Condition]] = {
    # Binary sensor conditions (detected/cleared)
    "is_gas_detected": _make_detected_condition(BinarySensorDeviceClass.GAS),
    "is_gas_cleared": _make_cleared_condition(BinarySensorDeviceClass.GAS),
    "is_co_detected": _make_detected_condition(BinarySensorDeviceClass.CO),
    "is_co_cleared": _make_cleared_condition(BinarySensorDeviceClass.CO),
    "is_smoke_detected": _make_detected_condition(BinarySensorDeviceClass.SMOKE),
    "is_smoke_cleared": _make_cleared_condition(BinarySensorDeviceClass.SMOKE),
    # Numerical sensor conditions with unit conversion
    "is_co_value": make_entity_numerical_condition_with_unit(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.CO)},
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        CarbonMonoxideConcentrationConverter,
    ),
    "is_ozone_value": make_entity_numerical_condition_with_unit(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.OZONE)},
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        OzoneConcentrationConverter,
    ),
    "is_voc_value": make_entity_numerical_condition_with_unit(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        MassVolumeConcentrationConverter,
    ),
    "is_voc_ratio_value": make_entity_numerical_condition_with_unit(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
            )
        },
        CONCENTRATION_PARTS_PER_BILLION,
        UnitlessRatioConverter,
    ),
    "is_no_value": make_entity_numerical_condition_with_unit(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROGEN_MONOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        NitrogenMonoxideConcentrationConverter,
    ),
    "is_no2_value": make_entity_numerical_condition_with_unit(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROGEN_DIOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        NitrogenDioxideConcentrationConverter,
    ),
    "is_so2_value": make_entity_numerical_condition_with_unit(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.SULPHUR_DIOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        SulphurDioxideConcentrationConverter,
    ),
    # Numerical sensor conditions without unit conversion (single-unit device classes)
    "is_co2_value": make_entity_numerical_condition(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.CO2)},
        valid_unit=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "is_pm1_value": make_entity_numerical_condition(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM1)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "is_pm25_value": make_entity_numerical_condition(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM25)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "is_pm4_value": make_entity_numerical_condition(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM4)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "is_pm10_value": make_entity_numerical_condition(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM10)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "is_n2o_value": make_entity_numerical_condition(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROUS_OXIDE
            )
        },
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the air quality conditions."""
    return CONDITIONS
