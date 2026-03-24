"""Provides triggers for air quality."""

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
from homeassistant.helpers.trigger import (
    EntityTargetStateTriggerBase,
    Trigger,
    make_entity_numerical_state_changed_trigger,
    make_entity_numerical_state_changed_with_unit_trigger,
    make_entity_numerical_state_crossed_threshold_trigger,
    make_entity_numerical_state_crossed_threshold_with_unit_trigger,
    make_entity_target_state_trigger,
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


def _make_detected_trigger(
    device_class: BinarySensorDeviceClass,
) -> type[EntityTargetStateTriggerBase]:
    """Create a detected trigger for a binary sensor device class."""

    return make_entity_target_state_trigger(
        {BINARY_SENSOR_DOMAIN: DomainSpec(device_class=device_class)}, STATE_ON
    )


def _make_cleared_trigger(
    device_class: BinarySensorDeviceClass,
) -> type[EntityTargetStateTriggerBase]:
    """Create a cleared trigger for a binary sensor device class."""

    return make_entity_target_state_trigger(
        {BINARY_SENSOR_DOMAIN: DomainSpec(device_class=device_class)}, STATE_OFF
    )


TRIGGERS: dict[str, type[Trigger]] = {
    # Binary sensor triggers (detected/cleared)
    "gas_detected": _make_detected_trigger(BinarySensorDeviceClass.GAS),
    "gas_cleared": _make_cleared_trigger(BinarySensorDeviceClass.GAS),
    "co_detected": _make_detected_trigger(BinarySensorDeviceClass.CO),
    "co_cleared": _make_cleared_trigger(BinarySensorDeviceClass.CO),
    "smoke_detected": _make_detected_trigger(BinarySensorDeviceClass.SMOKE),
    "smoke_cleared": _make_cleared_trigger(BinarySensorDeviceClass.SMOKE),
    # Numerical sensor triggers with unit conversion
    "co_changed": make_entity_numerical_state_changed_with_unit_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.CO)},
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        CarbonMonoxideConcentrationConverter,
    ),
    "co_crossed_threshold": make_entity_numerical_state_crossed_threshold_with_unit_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.CO)},
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        CarbonMonoxideConcentrationConverter,
    ),
    "ozone_changed": make_entity_numerical_state_changed_with_unit_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.OZONE)},
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        OzoneConcentrationConverter,
    ),
    "ozone_crossed_threshold": make_entity_numerical_state_crossed_threshold_with_unit_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.OZONE)},
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        OzoneConcentrationConverter,
    ),
    "voc_changed": make_entity_numerical_state_changed_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        MassVolumeConcentrationConverter,
    ),
    "voc_crossed_threshold": make_entity_numerical_state_crossed_threshold_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        MassVolumeConcentrationConverter,
    ),
    "voc_ratio_changed": make_entity_numerical_state_changed_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
            )
        },
        CONCENTRATION_PARTS_PER_BILLION,
        UnitlessRatioConverter,
    ),
    "voc_ratio_crossed_threshold": make_entity_numerical_state_crossed_threshold_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS
            )
        },
        CONCENTRATION_PARTS_PER_BILLION,
        UnitlessRatioConverter,
    ),
    "no_changed": make_entity_numerical_state_changed_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROGEN_MONOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        NitrogenMonoxideConcentrationConverter,
    ),
    "no_crossed_threshold": make_entity_numerical_state_crossed_threshold_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROGEN_MONOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        NitrogenMonoxideConcentrationConverter,
    ),
    "no2_changed": make_entity_numerical_state_changed_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROGEN_DIOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        NitrogenDioxideConcentrationConverter,
    ),
    "no2_crossed_threshold": make_entity_numerical_state_crossed_threshold_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROGEN_DIOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        NitrogenDioxideConcentrationConverter,
    ),
    "so2_changed": make_entity_numerical_state_changed_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.SULPHUR_DIOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        SulphurDioxideConcentrationConverter,
    ),
    "so2_crossed_threshold": make_entity_numerical_state_crossed_threshold_with_unit_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.SULPHUR_DIOXIDE
            )
        },
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        SulphurDioxideConcentrationConverter,
    ),
    # Numerical sensor triggers without unit conversion (single-unit device classes)
    "co2_changed": make_entity_numerical_state_changed_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.CO2)},
        valid_unit=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "co2_crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.CO2)},
        valid_unit=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "pm1_changed": make_entity_numerical_state_changed_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM1)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "pm1_crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM1)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "pm25_changed": make_entity_numerical_state_changed_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM25)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "pm25_crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM25)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "pm4_changed": make_entity_numerical_state_changed_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM4)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "pm4_crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM4)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "pm10_changed": make_entity_numerical_state_changed_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM10)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "pm10_crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        {SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.PM10)},
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "n2o_changed": make_entity_numerical_state_changed_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROUS_OXIDE
            )
        },
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    "n2o_crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        {
            SENSOR_DOMAIN: NumericalDomainSpec(
                device_class=SensorDeviceClass.NITROUS_OXIDE
            )
        },
        valid_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for air quality."""
    return TRIGGERS
