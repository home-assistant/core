"""Base entities for the Easywave integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_BUTTON_COUNT,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SENSOR_CAPABILITIES,
    CONF_SENSOR_SERIAL,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    DOMAIN,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_PERMANENT,
)

if TYPE_CHECKING:
    from . import EasywaveConfigEntry
    from .coordinator import EasywaveCoordinator


@dataclass
class EasywaveDeviceEntry:
    """Device configuration stored on the gateway config entry."""

    device_id: str
    title: str
    data: dict[str, Any]


def _transmitter_model(data: dict[str, Any]) -> str:
    """Return a human-readable model string describing the transmitter configuration."""
    op = data.get(CONF_OPERATING_TYPE, "1")
    parts: list[str] = []
    if op == "1":
        parts.append("1-Button Operation")
        count = data.get(CONF_BUTTON_COUNT, 1)
        parts.append(f"{count} Button{'s' if count != 1 else ''}")
        grouping = data.get(CONF_GROUPING_MODE, TRANSMITTER_GROUPING_GROUP)
        parts.append(
            "Group" if grouping == TRANSMITTER_GROUPING_GROUP else "Individual"
        )
        mode = data.get(CONF_SWITCH_MODE, "")
        parts.append("Permanent" if mode == TRANSMITTER_SWITCH_PERMANENT else "Impulse")
    return ", ".join(parts)


def _neo_sensor_model(data: dict[str, Any]) -> str:
    """Return a human-readable model string for an EWneo sensor."""
    capabilities = data.get(CONF_SENSOR_CAPABILITIES, 0)
    parts = ["Easywave neo Sensor"]
    if (capabilities >> 4) & 1:
        parts.append("Temperature")
    if (capabilities >> 5) & 1:
        parts.append("Humidity")
    return ", ".join(parts)


class EasywaveTransmitterEntity(Entity):
    """Base entity for an Easywave transmitter."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: EasywaveConfigEntry,
        device: EasywaveDeviceEntry,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the transmitter entity."""
        self._entry = entry
        self._transmitter_serial: str = device.data[CONF_TRANSMITTER_SERIAL]
        self._device_id: str = device.device_id

        self._attr_unique_id = f"{device.device_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.title,
            manufacturer="ELDAT",
            model=_transmitter_model(device.data),
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _coordinator(self) -> EasywaveCoordinator:
        """Return the coordinator from the shared runtime data."""
        return self._entry.runtime_data.coordinator

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates and register for telegram dispatch."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
        coordinator = self._coordinator
        coordinator.register_transmitter_entities([self])
        self.async_on_remove(lambda: coordinator.unregister_transmitter_entity(self))

    @property
    def transmitter_serial(self) -> str:
        """Return the transmitter serial for matching telegrams."""
        return self._transmitter_serial

    @property
    def device_id(self) -> str:
        """Return the device id (used for device identifier lookup)."""
        return self._device_id

    @override
    @property
    def available(self) -> bool:
        """Return if entity is available (transceiver connected)."""
        return self._coordinator.transceiver.is_connected

    def handle_battery_status(self, is_low: bool) -> None:
        """Handle a battery status update from a PUSH telegram.

        Default implementation is a no-op; overridden by the per-transmitter
        battery sensor.
        """


class EasywaveNeoSensorEntity(Entity):
    """Base entity for an Easywave neo sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: EasywaveConfigEntry,
        device: EasywaveDeviceEntry,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the neo sensor entity."""
        self._entry = entry
        self._sensor_serial: str = device.data[CONF_SENSOR_SERIAL]
        self._device_id: str = device.device_id

        self._attr_unique_id = f"{device.device_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.title,
            manufacturer="ELDAT",
            model=_neo_sensor_model(device.data),
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _coordinator(self) -> EasywaveCoordinator:
        """Return the coordinator from the shared runtime data."""
        return self._entry.runtime_data.coordinator

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates and register for telegram dispatch."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
        coordinator = self._coordinator
        coordinator.register_sensor_entities([self])
        self.async_on_remove(lambda: coordinator.unregister_sensor_entity(self))

    @property
    def sensor_serial(self) -> str:
        """Return the sensor serial for matching telegrams."""
        return self._sensor_serial

    @property
    def device_id(self) -> str:
        """Return the device id (used for device identifier lookup)."""
        return self._device_id

    @override
    @property
    def available(self) -> bool:
        """Return if entity is available (transceiver connected)."""
        return self._coordinator.transceiver.is_connected

    def handle_telegram(self, event: Any) -> None:
        """Handle an incoming neo sensor telegram."""
        raise NotImplementedError
