"""Base entities for the Easywave integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreStateData

from .const import (
    CONF_BUTTON_COUNT,
    CONF_GATEWAY_INDEX,
    CONF_GATEWAY_SERIAL,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_RECEIVER_KIND,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    DOMAIN,
    RECEIVER_KIND_UNIVERSAL,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_PERMANENT,
)

if TYPE_CHECKING:
    from . import EasywaveConfigEntry
    from .coordinator import EasywaveCoordinator


@dataclass
class EasywaveDeviceEntry:
    """Device configuration stored in entry.options["devices"]."""

    subentry_id: (
        str  # unique device id (named subentry_id for compat with entity classes)
    )
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
        grouping = data.get(CONF_GROUPING_MODE, "")
        parts.append(
            "Group" if grouping == TRANSMITTER_GROUPING_GROUP else "Individual"
        )
        mode = data.get(CONF_SWITCH_MODE, "")
        parts.append("Permanent" if mode == TRANSMITTER_SWITCH_PERMANENT else "Impulse")
    return ", ".join(parts)


def _receiver_model(data: dict[str, Any]) -> str:
    """Return a human-readable model string describing the receiver operating mode."""
    if data.get(CONF_RECEIVER_KIND) == RECEIVER_KIND_UNIVERSAL:
        return "Universal (4-Button)"
    return ""


class EasywaveReceiverEntity(Entity):
    """Base entity for an Easywave receiver (one subentry per receiver)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: EasywaveConfigEntry,
        subentry: EasywaveDeviceEntry,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the receiver entity."""
        self._entry = entry
        self._gateway_serial: bytes = bytes.fromhex(subentry.data[CONF_GATEWAY_SERIAL])
        self._gateway_index: int = subentry.data[CONF_GATEWAY_INDEX]

        self._attr_unique_id = f"{subentry.subentry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="ELDAT",
            model=_receiver_model(subentry.data),
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _coordinator(self) -> EasywaveCoordinator:
        """Return the coordinator from the shared runtime data."""
        return self._entry.runtime_data.coordinator

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates so availability changes propagate."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def _send_command(self, button_code: int) -> bool:
        """Send a command to the receiver via the transceiver."""
        return await self._coordinator.transceiver.send_command(
            self._gateway_serial, button_code
        )

    @property
    def available(self) -> bool:
        """Return if entity is available (transceiver connected)."""
        return self._coordinator.transceiver.is_connected


class EasywaveTransmitterEntity(Entity):
    """Base entity for an Easywave transmitter (one subentry per transmitter)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: EasywaveConfigEntry,
        subentry: EasywaveDeviceEntry,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the transmitter entity."""
        self._entry = entry
        self._transmitter_serial: str = subentry.data[CONF_TRANSMITTER_SERIAL]
        self._subentry_id: str = subentry.subentry_id
        self._operating_type: str = subentry.data.get(CONF_OPERATING_TYPE, "1")
        self._grouping_mode: str = subentry.data.get(CONF_GROUPING_MODE, "single")

        self._attr_unique_id = f"{subentry.subentry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="ELDAT",
            model=_transmitter_model(subentry.data),
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _coordinator(self) -> EasywaveCoordinator:
        """Return the coordinator from the shared runtime data."""
        return self._entry.runtime_data.coordinator

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates and register for telegram dispatch."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
        coordinator = self._coordinator
        coordinator.register_transmitter_entities([self])
        self.async_on_remove(lambda: coordinator.unregister_transmitter_entity(self))

    async def async_persist_state(self) -> None:
        """Persist the current state immediately so it survives an abrupt shutdown."""
        await RestoreStateData.async_save_persistent_states(self.hass)

    @property
    def transmitter_serial(self) -> str:
        """Return the transmitter serial for matching telegrams."""
        return self._transmitter_serial

    @property
    def subentry_id(self) -> str:
        """Return the subentry id (used for device identifier lookup)."""
        return self._subentry_id

    @property
    def operating_type(self) -> str:
        """Return the transmitter operating type (1, 2 or 3)."""
        return self._operating_type

    @property
    def grouping_mode(self) -> str:
        """Return grouping_mode for type-1 transmitters ('single' or 'group')."""
        return self._grouping_mode

    @property
    def available(self) -> bool:
        """Return if entity is available (transceiver connected)."""
        return self._coordinator.transceiver.is_connected

    def handle_battery_status(self, is_low: bool) -> None:
        """Handle a battery status update from a PUSH telegram.

        Default implementation is a no-op; overridden by the per-transmitter
        battery binary sensor.
        """
