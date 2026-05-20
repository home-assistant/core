"""Sensor platform for the Easywave Core integration."""

import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EntityCategory
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EasywaveConfigEntry, get_devices
from .const import (
    CONF_BUTTON_COUNT,
    CONF_DEVICE_PATH,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SWITCH_MODE,
    DOMAIN,
    ENTRY_TYPE_TRANSMITTER,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
)
from .coordinator import EasywaveCoordinator
from .entity import EasywaveDeviceEntry, EasywaveTransmitterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave sensors for gateway and device subentries."""
    # Gateway status sensor — always one per gateway entry.
    coordinator = entry.runtime_data.coordinator
    async_add_entities([EasywaveGatewaySensor(entry, coordinator)])

    # Per-subentry sensors: type-1 group-mode transmitters only.
    for subentry in get_devices(entry):
        if subentry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_TRANSMITTER:
            continue
        if str(subentry.data.get(CONF_OPERATING_TYPE, "1")) != "1":
            continue
        grouping_mode: str = str(subentry.data.get(CONF_GROUPING_MODE, "single"))
        if grouping_mode != TRANSMITTER_GROUPING_GROUP:
            continue
        last_button = EasywaveTransmitterLastButtonSensor(entry, subentry)
        battery = EasywaveTransmitterBatterySensor(entry, subentry)
        async_add_entities([last_button, battery])


class EasywaveGatewaySensor(CoordinatorEntity[EasywaveCoordinator], SensorEntity):
    """Represents the RX11 USB gateway connectivity/state."""

    STATUS_KEYS = [
        "connected",
        "disconnected",
    ]

    _attr_has_entity_name = True
    _attr_translation_key = "gateway_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = STATUS_KEYS

    def __init__(
        self, entry: EasywaveConfigEntry, coordinator: EasywaveCoordinator
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rx11_gateway"
        # Attach to the RX11 gateway device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self._last_status = "disconnected"
        self._ha_started = False

        # Keep _current_status as None until EVENT_HOMEASSISTANT_STARTED so the
        # recorder/logbook can capture an initial "unknown" → "connected" transition
        # instead of leaving the last shutdown "unavailable" state as the latest entry.
        self._current_status: str | None = None

    def _connection_status(self) -> str:
        """Get connection status as constant key (translated by HA frontend).

        Returns the current connection status from the coordinator:
        - "connected": Device is currently connected
        - "disconnected": Device is not found or offline
        """
        # Check if device is offline (not found)
        if self.coordinator.is_offline:
            return "disconnected"

        # Check transceiver connection status
        transceiver = self.coordinator.transceiver
        if transceiver and transceiver.is_connected:
            return "connected"

        return "disconnected"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        new_status = self._connection_status()

        # Only update the persisted status and fire events once HA is
        # running.  Coordinator updates can arrive during early startup
        # before EVENT_HOMEASSISTANT_STARTED fires; ignoring them keeps the
        # initial None (unknown) → connected/disconnected transition intact.
        if self._ha_started:
            if new_status != self._last_status:
                old_status = self._last_status
                _LOGGER.info("Gateway status: %s -> %s", old_status, new_status)
                self._last_status = new_status

                if new_status == "connected":
                    self.coordinator.fire_device_event(
                        self._entry.entry_id, "gateway_connected"
                    )
                elif new_status == "disconnected":
                    self.coordinator.fire_device_event(
                        self._entry.entry_id, "gateway_disconnected"
                    )

            self._current_status = new_status

        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to hass."""
        await super().async_added_to_hass()

        # Initialise last status.
        self._last_status = self._connection_status()

        # Write the correct state once HA has fully started so the recorder
        # captures a real unknown → connected transition.
        # native_value returns None until this fires (see _current_status).
        @callback
        def _on_ha_started(_event: Any = None) -> None:
            self._ha_started = True
            self._handle_coordinator_update()

        if self.hass.state is CoreState.running:
            # Added while HA was already fully running (e.g. via UI config flow).
            # Defer by one event-loop tick so the entity is fully registered
            # in the state machine before the write.
            self.hass.loop.call_soon(_on_ha_started)
        else:
            # async_listen_once removes itself after firing — do NOT also wrap
            # with async_on_remove or HA raises ValueError on the double-remove.
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)

    @property
    def native_value(self) -> str | None:
        """Return connection status key - translated by frontend via translation_key.

        Returns None before EVENT_HOMEASSISTANT_STARTED so the
        recorder captures the state transition on first write.
        """
        return self._current_status

    @property
    def icon(self) -> str:
        """Return icon based on connection status."""
        if self._current_status == "connected":
            return "mdi:usb"
        # None / disconnected
        return "mdi:close-thick"

    @property
    def available(self) -> bool:
        """Gateway sensor is always available to show status."""
        # Gateway sensor should always be available so users can see the connection status.
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the USB device path as a state attribute.

        The path may change across reconnects (e.g. /dev/ttyACM0 → ttyACM1),
        which is why it is exposed here rather than stored only in config data.
        """
        coordinator_data = self.coordinator.data
        device_path = (
            coordinator_data.get("device_path")
            if isinstance(coordinator_data, dict)
            else None
        ) or self._entry.data.get(CONF_DEVICE_PATH)
        return {"device_path": device_path}


_BUTTON_STATE_A = "a"
_BUTTON_STATE_B = "b"
_BUTTON_STATE_C = "c"
_BUTTON_STATE_D = "d"
_BUTTON_STATE_RELEASED = "released"

_BUTTON_STATES: list[str] = [
    _BUTTON_STATE_A,
    _BUTTON_STATE_B,
    _BUTTON_STATE_C,
    _BUTTON_STATE_D,
]

_ICON_MAP_LAST_BUTTON: dict[str, str] = {
    _BUTTON_STATE_A: "mdi:alpha-a-circle",
    _BUTTON_STATE_B: "mdi:alpha-b-circle",
    _BUTTON_STATE_C: "mdi:alpha-c-circle",
    _BUTTON_STATE_D: "mdi:alpha-d-circle",
    _BUTTON_STATE_RELEASED: "mdi:radiobox-blank",
}


class EasywaveTransmitterLastButtonSensor(EasywaveTransmitterEntity, RestoreSensor):
    """Enum sensor showing the last button pressed on a type-1 group transmitter.

    States: ``a`` / ``b`` / ``c`` / ``d`` and, in impulse mode, ``released``
    once the button is released. In permanent mode, the state stays on the
    most recently pressed button.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "transmitter_last_button"

    def __init__(
        self,
        entry: EasywaveConfigEntry,
        subentry: EasywaveDeviceEntry,
    ) -> None:
        """Initialize the last-button sensor."""
        super().__init__(entry, subentry, "last_button")
        button_count: int = min(subentry.data.get(CONF_BUTTON_COUNT, 4), 4)
        switch_mode: str = subentry.data.get(
            CONF_SWITCH_MODE, TRANSMITTER_SWITCH_IMPULSE
        )
        options = list(_BUTTON_STATES[:button_count])
        if switch_mode == TRANSMITTER_SWITCH_IMPULSE:
            options.append(_BUTTON_STATE_RELEASED)
        self._attr_options = options
        self._switch_mode = switch_mode
        self._native_value: str | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator and restore last known state.

        Restore BEFORE calling super() to prevent the coordinator listener
        from overwriting the restored value.
        """
        # Restore first
        if (last_data := await self.async_get_last_sensor_data()) is not None:
            native = last_data.native_value
            if native in (self._attr_options or ()):
                self._native_value = str(native)
        # Then subscribe to coordinator
        await super().async_added_to_hass()

    @property
    def native_value(self) -> str | None:
        """Return the current state (last button or 'released')."""
        return self._native_value

    @property
    def icon(self) -> str:
        """Return an icon reflecting the most recent button state."""
        return _ICON_MAP_LAST_BUTTON.get(
            self._native_value or _BUTTON_STATE_RELEASED, "mdi:radiobox-blank"
        )

    @callback
    def handle_telegram(self, info_type: int, button: int) -> None:
        """Update the sensor state from an incoming transmitter telegram."""
        if info_type == 0x01:
            if 0 <= button < 4:
                state = _BUTTON_STATES[button]
                if state in (self._attr_options or ()):
                    self._native_value = state
                    self.async_write_ha_state()
                    self.hass.async_create_task(
                        self.async_persist_state(),
                        eager_start=False,
                    )
        elif info_type == 0x00 and self._switch_mode == TRANSMITTER_SWITCH_IMPULSE:
            if _BUTTON_STATE_RELEASED in (self._attr_options or ()):
                self._native_value = _BUTTON_STATE_RELEASED
                self.async_write_ha_state()
                self.hass.async_create_task(
                    self.async_persist_state(),
                    eager_start=False,
                )


_BATTERY_STATE_OK = "ok"
_BATTERY_STATE_LOW = "low"
_BATTERY_OPTIONS = [_BATTERY_STATE_OK, _BATTERY_STATE_LOW]


class EasywaveTransmitterBatterySensor(EasywaveTransmitterEntity, RestoreSensor):
    """Diagnostic battery-state sensor for an Easywave transmitter.

    Requires two consecutive non-low PUSH telegrams to clear an existing
    warning (_CLEAR_THRESHOLD) to avoid spurious OK flashes on restart.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "battery_warning"
    _attr_options = _BATTERY_OPTIONS

    _CLEAR_THRESHOLD = 2

    def __init__(
        self, entry: EasywaveConfigEntry, subentry: EasywaveDeviceEntry
    ) -> None:
        """Initialize the transmitter battery sensor."""
        super().__init__(entry, subentry, "battery_warning")
        self._native_value: str | None = None
        self._ok_streak: int = 0

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator and restore last known battery state.

        Restore BEFORE calling super() to prevent the coordinator listener
        from overwriting the restored value.
        """
        # Restore first
        if (last_data := await self.async_get_last_sensor_data()) is not None:
            native = last_data.native_value
            if native in _BATTERY_OPTIONS:
                self._native_value = str(native)
        # Then subscribe to coordinator
        await super().async_added_to_hass()

    @property
    def native_value(self) -> str | None:
        """Return the current battery state."""
        return self._native_value

    @property
    def icon(self) -> str:
        """Return a battery icon reflecting the current state."""
        if self._native_value == _BATTERY_STATE_LOW:
            return "mdi:battery-alert"
        if self._native_value == _BATTERY_STATE_OK:
            return "mdi:battery"
        return "mdi:battery-unknown"

    @callback
    def handle_telegram(self, info_type: int, button: int) -> None:
        """Button press/release; battery state is updated via handle_battery_status."""

    @callback
    def handle_battery_status(self, is_low: bool) -> None:
        """Update battery state from the LOWBAT flag of a PUSH telegram."""
        if is_low:
            self._ok_streak = 0
            if self._native_value != _BATTERY_STATE_LOW:
                self._native_value = _BATTERY_STATE_LOW
                self.async_write_ha_state()
                self._coordinator.fire_device_event(self._subentry_id, "battery_low")
            return
        if self._native_value == _BATTERY_STATE_OK:
            return
        self._ok_streak += 1
        if self._ok_streak >= self._CLEAR_THRESHOLD:
            self._native_value = _BATTERY_STATE_OK
            self._ok_streak = 0
            self.async_write_ha_state()
            self._coordinator.fire_device_event(self._subentry_id, "battery_normal")
