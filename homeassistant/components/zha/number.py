"""Support for ZHA AnalogOutput cluster."""
from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any, Self

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform, UnitOfMass, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UndefinedType

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_ANALOG_OUTPUT,
    CLUSTER_HANDLER_BASIC,
    CLUSTER_HANDLER_COLOR,
    CLUSTER_HANDLER_INOVELLI,
    CLUSTER_HANDLER_LEVEL,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice

_LOGGER = logging.getLogger(__name__)

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.NUMBER)
CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.NUMBER
)


UNITS = {
    0: "Square-meters",
    1: "Square-feet",
    2: "Milliamperes",
    3: "Amperes",
    4: "Ohms",
    5: "Volts",
    6: "Kilo-volts",
    7: "Mega-volts",
    8: "Volt-amperes",
    9: "Kilo-volt-amperes",
    10: "Mega-volt-amperes",
    11: "Volt-amperes-reactive",
    12: "Kilo-volt-amperes-reactive",
    13: "Mega-volt-amperes-reactive",
    14: "Degrees-phase",
    15: "Power-factor",
    16: "Joules",
    17: "Kilojoules",
    18: "Watt-hours",
    19: "Kilowatt-hours",
    20: "BTUs",
    21: "Therms",
    22: "Ton-hours",
    23: "Joules-per-kilogram-dry-air",
    24: "BTUs-per-pound-dry-air",
    25: "Cycles-per-hour",
    26: "Cycles-per-minute",
    27: "Hertz",
    28: "Grams-of-water-per-kilogram-dry-air",
    29: "Percent-relative-humidity",
    30: "Millimeters",
    31: "Meters",
    32: "Inches",
    33: "Feet",
    34: "Watts-per-square-foot",
    35: "Watts-per-square-meter",
    36: "Lumens",
    37: "Luxes",
    38: "Foot-candles",
    39: "Kilograms",
    40: "Pounds-mass",
    41: "Tons",
    42: "Kilograms-per-second",
    43: "Kilograms-per-minute",
    44: "Kilograms-per-hour",
    45: "Pounds-mass-per-minute",
    46: "Pounds-mass-per-hour",
    47: "Watts",
    48: "Kilowatts",
    49: "Megawatts",
    50: "BTUs-per-hour",
    51: "Horsepower",
    52: "Tons-refrigeration",
    53: "Pascals",
    54: "Kilopascals",
    55: "Bars",
    56: "Pounds-force-per-square-inch",
    57: "Centimeters-of-water",
    58: "Inches-of-water",
    59: "Millimeters-of-mercury",
    60: "Centimeters-of-mercury",
    61: "Inches-of-mercury",
    62: "°C",
    63: "°K",
    64: "°F",
    65: "Degree-days-Celsius",
    66: "Degree-days-Fahrenheit",
    67: "Years",
    68: "Months",
    69: "Weeks",
    70: "Days",
    71: "Hours",
    72: "Minutes",
    73: "Seconds",
    74: "Meters-per-second",
    75: "Kilometers-per-hour",
    76: "Feet-per-second",
    77: "Feet-per-minute",
    78: "Miles-per-hour",
    79: "Cubic-feet",
    80: "Cubic-meters",
    81: "Imperial-gallons",
    82: "Liters",
    83: "Us-gallons",
    84: "Cubic-feet-per-minute",
    85: "Cubic-meters-per-second",
    86: "Imperial-gallons-per-minute",
    87: "Liters-per-second",
    88: "Liters-per-minute",
    89: "Us-gallons-per-minute",
    90: "Degrees-angular",
    91: "Degrees-Celsius-per-hour",
    92: "Degrees-Celsius-per-minute",
    93: "Degrees-Fahrenheit-per-hour",
    94: "Degrees-Fahrenheit-per-minute",
    95: None,
    96: "Parts-per-million",
    97: "Parts-per-billion",
    98: "%",
    99: "Percent-per-second",
    100: "Per-minute",
    101: "Per-second",
    102: "Psi-per-Degree-Fahrenheit",
    103: "Radians",
    104: "Revolutions-per-minute",
    105: "Currency1",
    106: "Currency2",
    107: "Currency3",
    108: "Currency4",
    109: "Currency5",
    110: "Currency6",
    111: "Currency7",
    112: "Currency8",
    113: "Currency9",
    114: "Currency10",
    115: "Square-inches",
    116: "Square-centimeters",
    117: "BTUs-per-pound",
    118: "Centimeters",
    119: "Pounds-mass-per-second",
    120: "Delta-Degrees-Fahrenheit",
    121: "Delta-Degrees-Kelvin",
    122: "Kilohms",
    123: "Megohms",
    124: "Millivolts",
    125: "Kilojoules-per-kilogram",
    126: "Megajoules",
    127: "Joules-per-degree-Kelvin",
    128: "Joules-per-kilogram-degree-Kelvin",
    129: "Kilohertz",
    130: "Megahertz",
    131: "Per-hour",
    132: "Milliwatts",
    133: "Hectopascals",
    134: "Millibars",
    135: "Cubic-meters-per-hour",
    136: "Liters-per-hour",
    137: "Kilowatt-hours-per-square-meter",
    138: "Kilowatt-hours-per-square-foot",
    139: "Megajoules-per-square-meter",
    140: "Megajoules-per-square-foot",
    141: "Watts-per-square-meter-Degree-Kelvin",
    142: "Cubic-feet-per-second",
    143: "Percent-obscuration-per-foot",
    144: "Percent-obscuration-per-meter",
    145: "Milliohms",
    146: "Megawatt-hours",
    147: "Kilo-BTUs",
    148: "Mega-BTUs",
    149: "Kilojoules-per-kilogram-dry-air",
    150: "Megajoules-per-kilogram-dry-air",
    151: "Kilojoules-per-degree-Kelvin",
    152: "Megajoules-per-degree-Kelvin",
    153: "Newton",
    154: "Grams-per-second",
    155: "Grams-per-minute",
    156: "Tons-per-hour",
    157: "Kilo-BTUs-per-hour",
    158: "Hundredths-seconds",
    159: "Milliseconds",
    160: "Newton-meters",
    161: "Millimeters-per-second",
    162: "Millimeters-per-minute",
    163: "Meters-per-minute",
    164: "Meters-per-hour",
    165: "Cubic-meters-per-minute",
    166: "Meters-per-second-per-second",
    167: "Amperes-per-meter",
    168: "Amperes-per-square-meter",
    169: "Ampere-square-meters",
    170: "Farads",
    171: "Henrys",
    172: "Ohm-meters",
    173: "Siemens",
    174: "Siemens-per-meter",
    175: "Teslas",
    176: "Volts-per-degree-Kelvin",
    177: "Volts-per-meter",
    178: "Webers",
    179: "Candelas",
    180: "Candelas-per-square-meter",
    181: "Kelvins-per-hour",
    182: "Kelvins-per-minute",
    183: "Joule-seconds",
    185: "Square-meters-per-Newton",
    186: "Kilogram-per-cubic-meter",
    187: "Newton-seconds",
    188: "Newtons-per-meter",
    189: "Watts-per-meter-per-degree-Kelvin",
}

ICONS = {
    0: "mdi:temperature-celsius",
    1: "mdi:water-percent",
    2: "mdi:gauge",
    3: "mdi:speedometer",
    4: "mdi:percent",
    5: "mdi:air-filter",
    6: "mdi:fan",
    7: "mdi:flash",
    8: "mdi:current-ac",
    9: "mdi:flash",
    10: "mdi:flash",
    11: "mdi:flash",
    12: "mdi:counter",
    13: "mdi:thermometer-lines",
    14: "mdi:timer",
    15: "mdi:palette",
    16: "mdi:brightness-percent",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation Analog Output from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.NUMBER]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
        ),
    )
    config_entry.async_on_unload(unsub)


@STRICT_MATCH(cluster_handler_names=CLUSTER_HANDLER_ANALOG_OUTPUT)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ZhaNumber(ZhaEntity, NumberEntity):
    """Representation of a ZHA Number entity."""

    _attr_name: str = "Number"

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this entity."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._analog_output_cluster_handler = self.cluster_handlers[
            CLUSTER_HANDLER_ANALOG_OUTPUT
        ]

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._analog_output_cluster_handler,
            SIGNAL_ATTR_UPDATED,
            self.async_set_state,
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._analog_output_cluster_handler.present_value

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        min_present_value = self._analog_output_cluster_handler.min_present_value
        if min_present_value is not None:
            return min_present_value
        return 0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        max_present_value = self._analog_output_cluster_handler.max_present_value
        if max_present_value is not None:
            return max_present_value
        return 1023

    @property
    def native_step(self) -> float | None:
        """Return the value step."""
        resolution = self._analog_output_cluster_handler.resolution
        if resolution is not None:
            return resolution
        return super().native_step

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the number entity."""
        description = self._analog_output_cluster_handler.description
        if description is not None and len(description) > 0:
            return f"{super().name} {description}"
        return super().name

    @property
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        application_type = self._analog_output_cluster_handler.application_type
        if application_type is not None:
            return ICONS.get(application_type >> 16, super().icon)
        return super().icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        engineering_units = self._analog_output_cluster_handler.engineering_units
        return UNITS.get(engineering_units)

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle value update from cluster handler."""
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value from HA."""
        num_value = float(value)
        if await self._analog_output_cluster_handler.async_set_present_value(num_value):
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Attempt to retrieve the state of the entity."""
        await super().async_update()
        _LOGGER.debug("polling current state")
        if self._analog_output_cluster_handler:
            value = await self._analog_output_cluster_handler.get_attribute_value(
                "present_value", from_cache=False
            )
            _LOGGER.debug("read value=%s", value)


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class ZHANumberConfigurationEntity(ZhaEntity, NumberEntity):
    """Representation of a ZHA number configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step: float = 1.0
    _attr_multiplier: float = 1
    _zcl_attribute: str

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        cluster_handler = cluster_handlers[0]
        if (
            cls._zcl_attribute in cluster_handler.cluster.unsupported_attributes
            or cls._zcl_attribute not in cluster_handler.cluster.attributes_by_name
            or cluster_handler.cluster.get(cls._zcl_attribute) is None
        ):
            _LOGGER.debug(
                "%s is not supported - skipping %s entity creation",
                cls._zcl_attribute,
                cls.__name__,
            )
            return None

        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this number configuration entity."""
        self._cluster_handler: ClusterHandler = cluster_handlers[0]
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return (
            self._cluster_handler.cluster.get(self._zcl_attribute)
            * self._attr_multiplier
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value from HA."""
        await self._cluster_handler.write_attributes_safe(
            {self._zcl_attribute: int(value / self._attr_multiplier)}
        )
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Attempt to retrieve the state of the entity."""
        await super().async_update()
        _LOGGER.debug("polling current state")
        if self._cluster_handler:
            value = await self._cluster_handler.get_attribute_value(
                self._zcl_attribute, from_cache=False
            )
            _LOGGER.debug("read value=%s", value)


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster",
    models={"lumi.motion.ac02", "lumi.motion.agl04"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraMotionDetectionInterval(
    ZHANumberConfigurationEntity, id_suffix="detection_interval"
):
    """Representation of a ZHA motion detection interval configuration entity."""

    _attr_native_min_value: float = 2
    _attr_native_max_value: float = 65535
    _zcl_attribute: str = "detection_interval"
    _attr_name = "Detection interval"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_LEVEL)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class OnOffTransitionTimeConfigurationEntity(
    ZHANumberConfigurationEntity, id_suffix="on_off_transition_time"
):
    """Representation of a ZHA on off transition time configuration entity."""

    _attr_native_min_value: float = 0x0000
    _attr_native_max_value: float = 0xFFFF
    _zcl_attribute: str = "on_off_transition_time"
    _attr_name = "On/Off transition time"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_LEVEL)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class OnLevelConfigurationEntity(ZHANumberConfigurationEntity, id_suffix="on_level"):
    """Representation of a ZHA on level configuration entity."""

    _attr_native_min_value: float = 0x00
    _attr_native_max_value: float = 0xFF
    _zcl_attribute: str = "on_level"
    _attr_name = "On level"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_LEVEL)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class OnTransitionTimeConfigurationEntity(
    ZHANumberConfigurationEntity, id_suffix="on_transition_time"
):
    """Representation of a ZHA on transition time configuration entity."""

    _attr_native_min_value: float = 0x0000
    _attr_native_max_value: float = 0xFFFE
    _zcl_attribute: str = "on_transition_time"
    _attr_name = "On transition time"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_LEVEL)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class OffTransitionTimeConfigurationEntity(
    ZHANumberConfigurationEntity, id_suffix="off_transition_time"
):
    """Representation of a ZHA off transition time configuration entity."""

    _attr_native_min_value: float = 0x0000
    _attr_native_max_value: float = 0xFFFE
    _zcl_attribute: str = "off_transition_time"
    _attr_name = "Off transition time"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_LEVEL)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class DefaultMoveRateConfigurationEntity(
    ZHANumberConfigurationEntity, id_suffix="default_move_rate"
):
    """Representation of a ZHA default move rate configuration entity."""

    _attr_native_min_value: float = 0x00
    _attr_native_max_value: float = 0xFE
    _zcl_attribute: str = "default_move_rate"
    _attr_name = "Default move rate"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_LEVEL)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class StartUpCurrentLevelConfigurationEntity(
    ZHANumberConfigurationEntity, id_suffix="start_up_current_level"
):
    """Representation of a ZHA startup current level configuration entity."""

    _attr_native_min_value: float = 0x00
    _attr_native_max_value: float = 0xFF
    _zcl_attribute: str = "start_up_current_level"
    _attr_name = "Start-up current level"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_COLOR)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class StartUpColorTemperatureConfigurationEntity(
    ZHANumberConfigurationEntity, id_suffix="start_up_color_temperature"
):
    """Representation of a ZHA startup color temperature configuration entity."""

    _attr_native_min_value: float = 153
    _attr_native_max_value: float = 500
    _zcl_attribute: str = "start_up_color_temperature"
    _attr_name = "Start-up color temperature"

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this ZHA startup color temperature entity."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        if self._cluster_handler:
            self._attr_native_min_value: float = self._cluster_handler.min_mireds
            self._attr_native_max_value: float = self._cluster_handler.max_mireds


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_htnnfasr",
    },
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class TimerDurationMinutes(ZHANumberConfigurationEntity, id_suffix="timer_duration"):
    """Representation of a ZHA timer duration configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[14]
    _attr_native_min_value: float = 0x00
    _attr_native_max_value: float = 0x257
    _attr_native_unit_of_measurement: str | None = UNITS[72]
    _zcl_attribute: str = "timer_duration"
    _attr_name = "Timer duration"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names="ikea_airpurifier")
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class FilterLifeTime(ZHANumberConfigurationEntity, id_suffix="filter_life_time"):
    """Representation of a ZHA filter lifetime configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[14]
    _attr_native_min_value: float = 0x00
    _attr_native_max_value: float = 0xFFFFFFFF
    _attr_native_unit_of_measurement: str | None = UNITS[72]
    _zcl_attribute: str = "filter_life_time"
    _attr_name = "Filter life time"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names=CLUSTER_HANDLER_BASIC,
    manufacturers={"TexasInstruments"},
    models={"ti.router"},
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class TiRouterTransmitPower(ZHANumberConfigurationEntity, id_suffix="transmit_power"):
    """Representation of a ZHA TI transmit power configuration entity."""

    _attr_native_min_value: float = -20
    _attr_native_max_value: float = 20
    _zcl_attribute: str = "transmit_power"
    _attr_name = "Transmit power"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliRemoteDimmingUpSpeed(
    ZHANumberConfigurationEntity, id_suffix="dimming_speed_up_remote"
):
    """Inovelli remote dimming up speed configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 126
    _zcl_attribute: str = "dimming_speed_up_remote"
    _attr_name: str = "Remote dimming up speed"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliButtonDelay(ZHANumberConfigurationEntity, id_suffix="button_delay"):
    """Inovelli button delay configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 9
    _zcl_attribute: str = "button_delay"
    _attr_name: str = "Button delay"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliLocalDimmingUpSpeed(
    ZHANumberConfigurationEntity, id_suffix="dimming_speed_up_local"
):
    """Inovelli local dimming up speed configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 127
    _zcl_attribute: str = "dimming_speed_up_local"
    _attr_name: str = "Local dimming up speed"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliLocalRampRateOffToOn(
    ZHANumberConfigurationEntity, id_suffix="ramp_rate_off_to_on_local"
):
    """Inovelli off to on local ramp rate configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 127
    _zcl_attribute: str = "ramp_rate_off_to_on_local"
    _attr_name: str = "Local ramp rate off to on"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliRemoteDimmingSpeedOffToOn(
    ZHANumberConfigurationEntity, id_suffix="ramp_rate_off_to_on_remote"
):
    """Inovelli off to on remote ramp rate configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 127
    _zcl_attribute: str = "ramp_rate_off_to_on_remote"
    _attr_name: str = "Remote ramp rate off to on"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliRemoteDimmingDownSpeed(
    ZHANumberConfigurationEntity, id_suffix="dimming_speed_down_remote"
):
    """Inovelli remote dimming down speed configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 127
    _zcl_attribute: str = "dimming_speed_down_remote"
    _attr_name: str = "Remote dimming down speed"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliLocalDimmingDownSpeed(
    ZHANumberConfigurationEntity, id_suffix="dimming_speed_down_local"
):
    """Inovelli local dimming down speed configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 127
    _zcl_attribute: str = "dimming_speed_down_local"
    _attr_name: str = "Local dimming down speed"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliLocalRampRateOnToOff(
    ZHANumberConfigurationEntity, id_suffix="ramp_rate_on_to_off_local"
):
    """Inovelli local on to off ramp rate configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 127
    _zcl_attribute: str = "ramp_rate_on_to_off_local"
    _attr_name: str = "Local ramp rate on to off"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliRemoteDimmingSpeedOnToOff(
    ZHANumberConfigurationEntity, id_suffix="ramp_rate_on_to_off_remote"
):
    """Inovelli remote on to off ramp rate configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[3]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 127
    _zcl_attribute: str = "ramp_rate_on_to_off_remote"
    _attr_name: str = "Remote ramp rate on to off"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliMinimumLoadDimmingLevel(
    ZHANumberConfigurationEntity, id_suffix="minimum_level"
):
    """Inovelli minimum load dimming level configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[16]
    _attr_native_min_value: float = 1
    _attr_native_max_value: float = 254
    _zcl_attribute: str = "minimum_level"
    _attr_name: str = "Minimum load dimming level"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliMaximumLoadDimmingLevel(
    ZHANumberConfigurationEntity, id_suffix="maximum_level"
):
    """Inovelli maximum load dimming level configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[16]
    _attr_native_min_value: float = 2
    _attr_native_max_value: float = 255
    _zcl_attribute: str = "maximum_level"
    _attr_name: str = "Maximum load dimming level"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliAutoShutoffTimer(
    ZHANumberConfigurationEntity, id_suffix="auto_off_timer"
):
    """Inovelli automatic switch shutoff timer configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[14]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 32767
    _zcl_attribute: str = "auto_off_timer"
    _attr_name: str = "Automatic switch shutoff timer"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliLoadLevelIndicatorTimeout(
    ZHANumberConfigurationEntity, id_suffix="load_level_indicator_timeout"
):
    """Inovelli load level indicator timeout configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[14]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 11
    _zcl_attribute: str = "load_level_indicator_timeout"
    _attr_name: str = "Load level indicator timeout"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliDefaultAllLEDOnColor(
    ZHANumberConfigurationEntity, id_suffix="led_color_when_on"
):
    """Inovelli default all led color when on configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[15]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 255
    _zcl_attribute: str = "led_color_when_on"
    _attr_name: str = "Default all LED on color"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliDefaultAllLEDOffColor(
    ZHANumberConfigurationEntity, id_suffix="led_color_when_off"
):
    """Inovelli default all led color when off configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[15]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 255
    _zcl_attribute: str = "led_color_when_off"
    _attr_name: str = "Default all LED off color"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliDefaultAllLEDOnIntensity(
    ZHANumberConfigurationEntity, id_suffix="led_intensity_when_on"
):
    """Inovelli default all led intensity when on configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[16]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 100
    _zcl_attribute: str = "led_intensity_when_on"
    _attr_name: str = "Default all LED on intensity"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliDefaultAllLEDOffIntensity(
    ZHANumberConfigurationEntity, id_suffix="led_intensity_when_off"
):
    """Inovelli default all led intensity when off configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[16]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 100
    _zcl_attribute: str = "led_intensity_when_off"
    _attr_name: str = "Default all LED off intensity"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliDoubleTapUpLevel(
    ZHANumberConfigurationEntity, id_suffix="double_tap_up_level"
):
    """Inovelli double tap up level configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[16]
    _attr_native_min_value: float = 2
    _attr_native_max_value: float = 254
    _zcl_attribute: str = "double_tap_up_level"
    _attr_name: str = "Double tap up level"


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_INOVELLI)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class InovelliDoubleTapDownLevel(
    ZHANumberConfigurationEntity, id_suffix="double_tap_down_level"
):
    """Inovelli double tap down level configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon: str = ICONS[16]
    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 254
    _zcl_attribute: str = "double_tap_down_level"
    _attr_name: str = "Double tap down level"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"}
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederServingSize(ZHANumberConfigurationEntity, id_suffix="serving_size"):
    """Aqara pet feeder serving size configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value: float = 1
    _attr_native_max_value: float = 10
    _zcl_attribute: str = "serving_size"
    _attr_name: str = "Serving to dispense"
    _attr_mode: NumberMode = NumberMode.BOX
    _attr_icon: str = "mdi:counter"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"}
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraPetFeederPortionWeight(
    ZHANumberConfigurationEntity, id_suffix="portion_weight"
):
    """Aqara pet feeder portion weight configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value: float = 1
    _attr_native_max_value: float = 100
    _zcl_attribute: str = "portion_weight"
    _attr_name: str = "Portion weight"
    _attr_mode: NumberMode = NumberMode.BOX
    _attr_native_unit_of_measurement: str = UnitOfMass.GRAMS
    _attr_icon: str = "mdi:weight-gram"


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.airrtc.agl001"}
)
# pylint: disable-next=hass-invalid-inheritance # needs fixing
class AqaraThermostatAwayTemp(
    ZHANumberConfigurationEntity, id_suffix="away_preset_temperature"
):
    """Aqara away preset temperature configuration entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value: float = 5
    _attr_native_max_value: float = 30
    _attr_multiplier: float = 0.01
    _zcl_attribute: str = "away_preset_temperature"
    _attr_name: str = "Away preset temperature"
    _attr_mode: NumberMode = NumberMode.SLIDER
    _attr_native_unit_of_measurement: str = UnitOfTemperature.CELSIUS
    _attr_icon: str = ICONS[0]
