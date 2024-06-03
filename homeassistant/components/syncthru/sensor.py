"""Support for Samsung Printers with SyncThru web interface."""

from __future__ import annotations

from pysyncthru import SyncThru, SyncthruState

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import device_identifiers
from .const import DOMAIN

COLORS = ["black", "cyan", "magenta", "yellow"]
DRUM_COLORS = COLORS
TONER_COLORS = COLORS
TRAYS = range(1, 6)
OUTPUT_TRAYS = range(6)
DEFAULT_MONITORED_CONDITIONS = []
DEFAULT_MONITORED_CONDITIONS.extend([f"toner_{key}" for key in TONER_COLORS])
DEFAULT_MONITORED_CONDITIONS.extend([f"drum_{key}" for key in DRUM_COLORS])
DEFAULT_MONITORED_CONDITIONS.extend([f"tray_{key}" for key in TRAYS])
DEFAULT_MONITORED_CONDITIONS.extend([f"output_tray_{key}" for key in OUTPUT_TRAYS])

SYNCTHRU_STATE_HUMAN = {
    SyncthruState.INVALID: "invalid",
    SyncthruState.OFFLINE: "unreachable",
    SyncthruState.NORMAL: "normal",
    SyncthruState.UNKNOWN: "unknown",
    SyncthruState.WARNING: "warning",
    SyncthruState.TESTING: "testing",
    SyncthruState.ERROR: "error",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up from config entry."""

    coordinator: DataUpdateCoordinator[SyncThru] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    printer: SyncThru = coordinator.data

    supp_toner = printer.toner_status(filter_supported=True)
    supp_drum = printer.drum_status(filter_supported=True)
    supp_tray = printer.input_tray_status(filter_supported=True)
    supp_output_tray = printer.output_tray_status()

    name: str = config_entry.data[CONF_NAME]
    entities: list[SyncThruSensor] = [
        SyncThruMainSensor(coordinator, name),
        SyncThruActiveAlertSensor(coordinator, name),
    ]
    entities.extend(SyncThruTonerSensor(coordinator, name, key) for key in supp_toner)
    entities.extend(SyncThruDrumSensor(coordinator, name, key) for key in supp_drum)
    entities.extend(
        SyncThruInputTraySensor(coordinator, name, key) for key in supp_tray
    )
    entities.extend(
        SyncThruOutputTraySensor(coordinator, name, int_key)
        for int_key in supp_output_tray
    )

    async_add_entities(entities)


class SyncThruSensor(CoordinatorEntity[DataUpdateCoordinator[SyncThru]], SensorEntity):
    """Implementation of an abstract Samsung Printer sensor platform."""

    _attr_icon = "mdi:printer"

    def __init__(self, coordinator: DataUpdateCoordinator[SyncThru], name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.syncthru = coordinator.data
        self._attr_name = name
        self._id_suffix = ""

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        serial = self.syncthru.serial_number()
        return f"{serial}{self._id_suffix}" if serial else None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""
        if (identifiers := device_identifiers(self.syncthru)) is None:
            return None
        return DeviceInfo(
            identifiers=identifiers,
        )


class SyncThruMainSensor(SyncThruSensor):
    """Implementation of the main sensor, conducting the actual polling.

    It also shows the detailed state and presents
    the displayed current status message.
    """

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: DataUpdateCoordinator[SyncThru], name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name)
        self._id_suffix = "_main"

    @property
    def native_value(self):
        """Set state to human readable version of syncthru status."""
        return SYNCTHRU_STATE_HUMAN[self.syncthru.device_status()]

    @property
    def extra_state_attributes(self):
        """Show current printer display text."""
        return {
            "display_text": self.syncthru.device_status_details(),
        }


class SyncThruTonerSensor(SyncThruSensor):
    """Implementation of a Samsung Printer toner sensor platform."""

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: DataUpdateCoordinator[SyncThru], name: str, color: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name)
        self._attr_name = f"{name} Toner {color}"
        self._color = color
        self._id_suffix = f"_toner_{color}"

    @property
    def extra_state_attributes(self):
        """Show all data returned for this toner."""
        return self.syncthru.toner_status().get(self._color, {})

    @property
    def native_value(self):
        """Show amount of remaining toner."""
        return self.syncthru.toner_status().get(self._color, {}).get("remaining")


class SyncThruDrumSensor(SyncThruSensor):
    """Implementation of a Samsung Printer drum sensor platform."""

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: DataUpdateCoordinator[SyncThru], name: str, color: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name)
        self._attr_name = f"{name} Drum {color}"
        self._color = color
        self._id_suffix = f"_drum_{color}"

    @property
    def extra_state_attributes(self):
        """Show all data returned for this drum."""
        return self.syncthru.drum_status().get(self._color, {})

    @property
    def native_value(self):
        """Show amount of remaining drum."""
        return self.syncthru.drum_status().get(self._color, {}).get("remaining")


class SyncThruInputTraySensor(SyncThruSensor):
    """Implementation of a Samsung Printer input tray sensor platform."""

    def __init__(
        self, coordinator: DataUpdateCoordinator[SyncThru], name: str, number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name)
        self._attr_name = f"{name} Tray {number}"
        self._number = number
        self._id_suffix = f"_tray_{number}"

    @property
    def extra_state_attributes(self):
        """Show all data returned for this input tray."""
        return self.syncthru.input_tray_status().get(self._number, {})

    @property
    def native_value(self):
        """Display ready unless there is some error, then display error."""
        tray_state = (
            self.syncthru.input_tray_status().get(self._number, {}).get("newError")
        )
        if tray_state == "":
            tray_state = "Ready"
        return tray_state


class SyncThruOutputTraySensor(SyncThruSensor):
    """Implementation of a Samsung Printer output tray sensor platform."""

    def __init__(
        self, coordinator: DataUpdateCoordinator[SyncThru], name: str, number: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name)
        self._attr_name = f"{name} Output Tray {number}"
        self._number = number
        self._id_suffix = f"_output_tray_{number}"

    @property
    def extra_state_attributes(self):
        """Show all data returned for this output tray."""
        return self.syncthru.output_tray_status().get(self._number, {})

    @property
    def native_value(self):
        """Display ready unless there is some error, then display error."""
        tray_state = (
            self.syncthru.output_tray_status().get(self._number, {}).get("status")
        )
        if tray_state == "":
            tray_state = "Ready"
        return tray_state


class SyncThruActiveAlertSensor(SyncThruSensor):
    """Implementation of a Samsung Printer active alerts sensor platform."""

    def __init__(self, coordinator: DataUpdateCoordinator[SyncThru], name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name)
        self._attr_name = f"{name} Active Alerts"
        self._id_suffix = "_active_alerts"

    @property
    def native_value(self):
        """Show number of active alerts."""
        return self.syncthru.raw().get("GXI_ACTIVE_ALERT_TOTAL")
