"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from boschshcpy import (
    SHCLightSwitchBSM,
    SHCMicromoduleShutterControl,
    SHCSession,
    SHCSmartPlug,
    SHCSmartPlugCompact,
    SHCThermostat,
    SHCTwinguard,
    SHCWallThermostat,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BoschConfigEntry
from .const import DOMAIN
from .entity import SHCEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SHCSensorEntityDescription[_DeviceT: SHCDevice](SensorEntityDescription):
    """Describes a SHC sensor.

    Never share one instance across descriptions for different device types.
    """

    value_fn: Callable[[_DeviceT], StateType]
    attributes_fn: Callable[[_DeviceT], dict[str, Any]] | None = None


_PowerMeterDevice = SHCSmartPlug | SHCLightSwitchBSM | SHCMicromoduleShutterControl

TEMPERATURE_SENSOR = "temperature"
HUMIDITY_SENSOR = "humidity"
VALVE_TAPPET_SENSOR = "valvetappet"
VALVE_TAPPET_STATE_SENSOR = "valve_tappet_state"
PURITY_SENSOR = "purity"
AIR_QUALITY_SENSOR = "airquality"
TEMPERATURE_RATING_SENSOR = "temperature_rating"
HUMIDITY_RATING_SENSOR = "humidity_rating"
PURITY_RATING_SENSOR = "purity_rating"
POWER_SENSOR = "power"
ENERGY_SENSOR = "energy"
COMMUNICATION_QUALITY_SENSOR = "communication_quality"


def _valve_tappet_state_value(device: SHCThermostat) -> str | None:
    """Return the valve motor status enum string, or None on unknown value."""
    try:
        return str(device.valvestate.name.lower())
    except ValueError, AttributeError:
        return None


_THERMOSTAT_TEMPERATURE_DESCRIPTION: SHCSensorEntityDescription[SHCThermostat] = (
    SHCSensorEntityDescription(
        key=TEMPERATURE_SENSOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    )
)
_VALVE_TAPPET_DESCRIPTION: SHCSensorEntityDescription[SHCThermostat] = (
    SHCSensorEntityDescription(
        key=VALVE_TAPPET_SENSOR,
        translation_key=VALVE_TAPPET_SENSOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Superseded by the "valve" platform's position entity; kept
        # available (opt-in) for anyone already relying on the raw percentage.
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda device: device.position,
        # Kept for anyone already reading this attribute in a template or
        # automation, even though the same value is now also a first-class
        # sensor below (_VALVE_TAPPET_STATE_DESCRIPTION).
        attributes_fn=lambda device: {"valve_tappet_state": device.valvestate.name},
    )
)
_VALVE_TAPPET_STATE_DESCRIPTION: SHCSensorEntityDescription[SHCThermostat] = (
    SHCSensorEntityDescription(
        key=VALVE_TAPPET_STATE_SENSOR,
        translation_key=VALVE_TAPPET_STATE_SENSOR,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            "valve_adaption_successful",
            "valve_adaption_in_progress",
            "valve_adaption_requested",
            "range_too_big",
            "range_too_small",
            "run_to_start_position",
            "start_position_requested",
            "in_start_position",
            "not_available",
            "no_valve_body_error",
            "no_motor_error",
            "valve_too_tight",
            "fix_motor_logic_requested",
            "fix_motor_logic_in_progress",
            "fix_motor_logic_successful",
            "error",
            "unknown",
        ],
        value_fn=_valve_tappet_state_value,
    )
)
_WALLTHERMOSTAT_TEMPERATURE_DESCRIPTION: SHCSensorEntityDescription[
    SHCWallThermostat
] = SHCSensorEntityDescription(
    key=TEMPERATURE_SENSOR,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    value_fn=lambda device: device.temperature,
)
_WALLTHERMOSTAT_HUMIDITY_DESCRIPTION: SHCSensorEntityDescription[SHCWallThermostat] = (
    SHCSensorEntityDescription(
        key=HUMIDITY_SENSOR,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda device: device.humidity,
    )
)
_TWINGUARD_TEMPERATURE_DESCRIPTION: SHCSensorEntityDescription[SHCTwinguard] = (
    SHCSensorEntityDescription(
        key=TEMPERATURE_SENSOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    )
)
_TWINGUARD_HUMIDITY_DESCRIPTION: SHCSensorEntityDescription[SHCTwinguard] = (
    SHCSensorEntityDescription(
        key=HUMIDITY_SENSOR,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda device: device.humidity,
    )
)
_PURITY_DESCRIPTION: SHCSensorEntityDescription[SHCTwinguard] = (
    SHCSensorEntityDescription(
        key=PURITY_SENSOR,
        translation_key=PURITY_SENSOR,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        value_fn=lambda device: device.purity,
    )
)
_AIR_QUALITY_DESCRIPTION: SHCSensorEntityDescription[SHCTwinguard] = (
    SHCSensorEntityDescription(
        key=AIR_QUALITY_SENSOR,
        translation_key="air_quality",
        value_fn=lambda device: device.combined_rating.name,
        attributes_fn=lambda device: {
            "rating_description": device.description,
        },
    )
)
_TEMPERATURE_RATING_DESCRIPTION: SHCSensorEntityDescription[SHCTwinguard] = (
    SHCSensorEntityDescription(
        key=TEMPERATURE_RATING_SENSOR,
        translation_key=TEMPERATURE_RATING_SENSOR,
        value_fn=lambda device: device.temperature_rating.name,
    )
)
_HUMIDITY_RATING_DESCRIPTION: SHCSensorEntityDescription[SHCTwinguard] = (
    SHCSensorEntityDescription(
        key=HUMIDITY_RATING_SENSOR,
        translation_key=HUMIDITY_RATING_SENSOR,
        value_fn=lambda device: device.humidity_rating.name,
    )
)
_PURITY_RATING_DESCRIPTION: SHCSensorEntityDescription[SHCTwinguard] = (
    SHCSensorEntityDescription(
        key=PURITY_RATING_SENSOR,
        translation_key=PURITY_RATING_SENSOR,
        value_fn=lambda device: device.purity_rating.name,
    )
)
_POWER_DESCRIPTION: SHCSensorEntityDescription[_PowerMeterDevice] = (
    SHCSensorEntityDescription(
        key=POWER_SENSOR,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.powerconsumption,
    )
)
_ENERGY_DESCRIPTION: SHCSensorEntityDescription[_PowerMeterDevice] = (
    SHCSensorEntityDescription(
        key=ENERGY_SENSOR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda device: device.energyconsumption / 1000.0,
    )
)
_COMPACT_POWER_DESCRIPTION: SHCSensorEntityDescription[SHCSmartPlugCompact] = (
    SHCSensorEntityDescription(
        key=POWER_SENSOR,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.powerconsumption,
    )
)
_COMPACT_ENERGY_DESCRIPTION: SHCSensorEntityDescription[SHCSmartPlugCompact] = (
    SHCSensorEntityDescription(
        key=ENERGY_SENSOR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda device: device.energyconsumption / 1000.0,
    )
)
_COMMUNICATION_QUALITY_DESCRIPTION: SHCSensorEntityDescription[SHCSmartPlugCompact] = (
    SHCSensorEntityDescription(
        key=COMMUNICATION_QUALITY_SENSOR,
        translation_key=COMMUNICATION_QUALITY_SENSOR,
        value_fn=lambda device: device.communicationquality.name,
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC sensor platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[SensorEntity] = [
        SHCSensor(
            hass,
            device,
            description,
            shc_info.unique_id,
            config_entry.entry_id,
        )
        for device in session.device_helper.thermostats
        for description in (
            _THERMOSTAT_TEMPERATURE_DESCRIPTION,
            _VALVE_TAPPET_DESCRIPTION,
            _VALVE_TAPPET_STATE_DESCRIPTION,
        )
    ]

    entities.extend(
        SHCSensor(
            hass,
            device,
            description,
            shc_info.unique_id,
            config_entry.entry_id,
        )
        for device in session.device_helper.wallthermostats
        for description in (
            _WALLTHERMOSTAT_TEMPERATURE_DESCRIPTION,
            _WALLTHERMOSTAT_HUMIDITY_DESCRIPTION,
        )
    )

    entities.extend(
        SHCSensor(
            hass,
            device,
            description,
            shc_info.unique_id,
            config_entry.entry_id,
        )
        for device in session.device_helper.twinguards
        for description in (
            _TWINGUARD_TEMPERATURE_DESCRIPTION,
            _TWINGUARD_HUMIDITY_DESCRIPTION,
            _PURITY_DESCRIPTION,
            _AIR_QUALITY_DESCRIPTION,
            _TEMPERATURE_RATING_DESCRIPTION,
            _HUMIDITY_RATING_DESCRIPTION,
            _PURITY_RATING_DESCRIPTION,
        )
    )

    power_meter_devices: list[_PowerMeterDevice] = [
        *session.device_helper.smart_plugs,
        *session.device_helper.light_switches_bsm,
        *session.device_helper.micromodule_shutter_controls,
        *session.device_helper.micromodule_blinds,
    ]
    entities.extend(
        SHCSensor(
            hass,
            device,
            description,
            shc_info.unique_id,
            config_entry.entry_id,
        )
        for device in power_meter_devices
        for description in (_POWER_DESCRIPTION, _ENERGY_DESCRIPTION)
    )

    entities.extend(
        SHCSensor(
            hass,
            device,
            description,
            shc_info.unique_id,
            config_entry.entry_id,
        )
        for device in session.device_helper.smart_plugs_compact
        for description in (
            _COMPACT_POWER_DESCRIPTION,
            _COMPACT_ENERGY_DESCRIPTION,
            _COMMUNICATION_QUALITY_DESCRIPTION,
        )
    )

    async_add_entities(entities)

    async_add_entities(
        [SHCOpenWindowsSensor(session=session, parent_id=shc_info.unique_id)],
        update_before_add=True,
    )


class SHCOpenWindowsSensor(SensorEntity):
    """Whole-home summary of open doors/windows (official OpenAPI spec).

    Not tied to one SHC device, so this does not inherit SHCEntity — it's
    scoped to the config entry and linked to the hub device directly. The
    underlying doors-windows/openwindows endpoint is a plain GET, not
    delivered by the long-poll stream, so this needs should_poll=True.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "open_windows_doors"
    _attr_should_poll = True

    def __init__(self, session: SHCSession, parent_id: str) -> None:
        """Initialize the open-windows/doors summary sensor."""
        self._session = session
        self._attr_unique_id = f"{parent_id}_open_windows_doors"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, parent_id)})
        self._open_doors: list[dict[str, Any]] = []
        self._open_windows: list[dict[str, Any]] = []
        self._open_others: list[dict[str, Any]] = []

    @property
    @override
    def native_value(self) -> int:
        """Return the total count of open doors, windows, and other openings."""
        return len(self._open_doors) + len(self._open_windows) + len(self._open_others)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, list[str]]:
        """Return the names of each currently-open door/window/other opening."""
        return {
            "open_doors": [d.get("name", "") for d in self._open_doors],
            "open_windows": [w.get("name", "") for w in self._open_windows],
            "open_others": [o.get("name", "") for o in self._open_others],
        }

    def update(self) -> None:
        """Poll the whole-home open-doors/open-windows summary."""
        data = self._session.api.get_open_windows()
        self._open_doors = data.get("openDoors", [])
        self._open_windows = data.get("openWindows", [])
        self._open_others = data.get("openOthers", [])


class SHCSensor[_DeviceT: SHCDevice](SHCEntity, SensorEntity):
    """Representation of a SHC sensor."""

    entity_description: SHCSensorEntityDescription[_DeviceT]

    def __init__(
        self,
        hass: HomeAssistant,
        device: _DeviceT,
        entity_description: SHCSensorEntityDescription[_DeviceT],
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(hass, device, parent_id, entry_id)
        self._device: _DeviceT = device
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.serial}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.attributes_fn is not None:
            return self.entity_description.attributes_fn(self._device)
        return None
