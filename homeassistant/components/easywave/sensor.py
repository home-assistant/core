"""Sensor platform for the Easywave Core integration."""

import logging
from typing import Any, override

from easywave_home_control.codec import (
    ButtonPushEvent,
    ButtonReleaseEvent,
    SensorTelegramEvent,
)

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EasywaveConfigEntry
from .const import (
    CONF_BUTTON,
    CONF_BUTTON_COUNT,
    CONF_DEVICE_PATH,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SENSOR_CAPABILITIES,
    CONF_SWITCH_MODE,
    DOMAIN,
    ENTRY_TYPE_NEO_SENSOR,
    ENTRY_TYPE_TRANSMITTER,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
    EasywaveGatewayFeature,
    transmitter_button_letters,
    transmitter_trigger_features,
)
from .coordinator import EasywaveCoordinator
from .devices import get_devices
from .entity import (
    EasywaveDeviceEntry,
    EasywaveNeoSensorEntity,
    EasywaveTransmitterEntity,
)
from .neo import sensor_learn_capabilities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave sensors for the gateway and configured devices."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([EasywaveGatewaySensor(entry, coordinator)])

    for device in get_devices(entry):
        entry_type = device.data.get(CONF_ENTRY_TYPE)
        if entry_type == ENTRY_TYPE_TRANSMITTER:
            if str(device.data.get(CONF_OPERATING_TYPE, "1")) != "1":
                continue
            grouping_mode: str = str(
                device.data.get(CONF_GROUPING_MODE, TRANSMITTER_GROUPING_GROUP)
            )
            if grouping_mode != TRANSMITTER_GROUPING_GROUP:
                continue
            last_button = EasywaveTransmitterLastButtonSensor(entry, device)
            battery = EasywaveTransmitterBatterySensor(entry, device)
            async_add_entities(
                [last_button, battery],
                config_subentry_id=device.subentry_id,
            )
        elif entry_type == ENTRY_TYPE_NEO_SENSOR:
            capabilities = sensor_learn_capabilities(
                device.data.get(CONF_SENSOR_CAPABILITIES, 0)
            )
            neo_entities: list[SensorEntity] = []
            if capabilities.measures_temperature:
                neo_entities.append(EasywaveNeoSensorTemperatureSensor(entry, device))
            if capabilities.measures_humidity:
                neo_entities.append(EasywaveNeoSensorHumiditySensor(entry, device))
            if neo_entities:
                async_add_entities(
                    neo_entities,
                    config_subentry_id=device.subentry_id,
                )

    coordinator.ensure_telegram_listener()


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
    _attr_supported_features = EasywaveGatewayFeature.GATEWAY_STATUS

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
        """Get connection status as constant key (translated by HA frontend)."""
        if self.coordinator.is_offline:
            return "disconnected"

        transceiver = self.coordinator.transceiver
        if transceiver and transceiver.is_connected:
            return "connected"

        return "disconnected"

    @override
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
                _LOGGER.debug("Gateway status: %s -> %s", self._last_status, new_status)
                self._last_status = new_status
            self._current_status = new_status

        super()._handle_coordinator_update()

    @override
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
            # Use async_listen (not listen_once): listen_once auto-removes after
            # fire, then entity unload via async_on_remove would error with
            # "Unable to remove unknown job listener".
            self.async_on_remove(
                self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)
            )

    @override
    @property
    def native_value(self) -> str | None:
        """Return connection status key - translated by frontend via translation_key.

        Returns None before EVENT_HOMEASSISTANT_STARTED so the
        recorder captures the state transition on first write.
        """
        return self._current_status

    @override
    @property
    def icon(self) -> str:
        """Return icon based on connection status."""
        if self._current_status == "connected":
            return "mdi:usb"
        # None / disconnected
        return "mdi:close-thick"

    @override
    @property
    def available(self) -> bool:
        """Gateway sensor is always available to show status."""
        return True

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the USB device path as a state attribute.

        The path may change across reconnects (e.g. /dev/ttyACM0 → ttyACM1),
        which is why it is exposed here rather than stored only in config data.
        An explicit offline ``None`` from the coordinator is preserved.
        """
        coordinator_data = self.coordinator.data
        if isinstance(coordinator_data, dict) and "device_path" in coordinator_data:
            device_path = coordinator_data["device_path"]
        else:
            device_path = self._entry.data.get(CONF_DEVICE_PATH)
        return {"device_path": device_path}


_BUTTON_STATE_A = "a"
_BUTTON_STATE_B = "b"
_BUTTON_STATE_C = "c"
_BUTTON_STATE_D = "d"
_BUTTON_STATE_RELEASED = "released"

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
        device: EasywaveDeviceEntry,
    ) -> None:
        """Initialize the last-button sensor."""
        super().__init__(entry, device, "last_button")
        button_letters = transmitter_button_letters(device.data)
        switch_mode: str = device.data.get(CONF_SWITCH_MODE, TRANSMITTER_SWITCH_IMPULSE)
        options = list(button_letters)
        if switch_mode == TRANSMITTER_SWITCH_IMPULSE:
            options.append(_BUTTON_STATE_RELEASED)
        self._attr_options = options
        self._attr_supported_features = transmitter_trigger_features(
            len(button_letters) or int(device.data.get(CONF_BUTTON_COUNT, 4)),
            switch_mode,
            button=device.data.get(CONF_BUTTON),
        )
        self._switch_mode = switch_mode
        self._native_value: str | None = None

    @override
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

    @override
    @property
    def native_value(self) -> str | None:
        """Return the current state (last button or 'released')."""
        return self._native_value

    @override
    @property
    def icon(self) -> str:
        """Return an icon reflecting the most recent button state."""
        return _ICON_MAP_LAST_BUTTON.get(
            self._native_value or _BUTTON_STATE_RELEASED, "mdi:radiobox-blank"
        )

    @callback
    def handle_telegram(self, event: ButtonPushEvent | ButtonReleaseEvent) -> None:
        """Update the sensor state from an incoming transmitter telegram."""
        if isinstance(event, ButtonPushEvent):
            button_letter = "abcd"[event.button] if event.button < 4 else None
            if button_letter in (self._attr_options or ()):
                self._native_value = button_letter
                self.async_write_ha_state()
        elif (
            isinstance(event, ButtonReleaseEvent)
            and self._switch_mode == TRANSMITTER_SWITCH_IMPULSE
        ):
            if _BUTTON_STATE_RELEASED in (self._attr_options or ()):
                self._native_value = _BUTTON_STATE_RELEASED
                self.async_write_ha_state()


_BATTERY_STATE_OK = "ok"
_BATTERY_STATE_LOW = "low"
_BATTERY_OPTIONS = [_BATTERY_STATE_OK, _BATTERY_STATE_LOW]


class EasywaveTransmitterBatterySensor(EasywaveTransmitterEntity, RestoreSensor):
    """Diagnostic battery-state sensor for an Easywave transmitter.

    State transitions are owned by the coordinator; this entity mirrors that
    state for the UI.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "battery_warning"
    _attr_options = _BATTERY_OPTIONS

    def __init__(self, entry: EasywaveConfigEntry, device: EasywaveDeviceEntry) -> None:
        """Initialize the transmitter battery sensor."""
        super().__init__(entry, device, "battery_warning")
        self._native_value: str | None = None

    @override
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
                self._coordinator.sync_transmitter_battery_state(
                    self._device_id, self._native_value
                )
        # Then subscribe to coordinator
        await super().async_added_to_hass()

    @override
    @property
    def native_value(self) -> str | None:
        """Return the current battery state."""
        return self._native_value

    @override
    @property
    def icon(self) -> str:
        """Return a battery icon reflecting the current state."""
        if self._native_value == _BATTERY_STATE_LOW:
            return "mdi:battery-alert"
        if self._native_value == _BATTERY_STATE_OK:
            return "mdi:battery"
        return "mdi:battery-unknown"

    @callback
    def handle_telegram(self, event: ButtonPushEvent | ButtonReleaseEvent) -> None:
        """Battery state is updated via handle_battery_status."""

    @override
    @callback
    def handle_battery_status(self, is_low: bool) -> None:
        """Mirror coordinator battery state after a PUSH telegram."""
        state = self._coordinator.transmitter_battery_state(self._device_id)
        if state is None or state == self._native_value:
            return
        self._native_value = state
        self.async_write_ha_state()


class EasywaveNeoSensorTemperatureSensor(EasywaveNeoSensorEntity, RestoreSensor):
    """Temperature measurement from an Easywave neo sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "neo_sensor_temperature"

    def __init__(self, entry: EasywaveConfigEntry, device: EasywaveDeviceEntry) -> None:
        """Initialize the temperature sensor."""
        super().__init__(entry, device, "temperature")
        self._attr_native_value: float | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last known temperature."""
        if (last_data := await self.async_get_last_sensor_data()) is not None:
            if isinstance(last_data.native_value, (int, float)):
                self._attr_native_value = float(last_data.native_value)
        await super().async_added_to_hass()

    @override
    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        return self._attr_native_value

    @override
    @callback
    def handle_telegram(self, event: SensorTelegramEvent) -> None:
        """Update temperature from a measurement telegram."""
        value = event.payload.temperature_celsius
        if value is None:
            return
        self._attr_native_value = value
        _LOGGER.debug(
            "Updated temperature for sensor %s to %s",
            self._sensor_serial,
            value,
        )
        self.async_write_ha_state()


class EasywaveNeoSensorHumiditySensor(EasywaveNeoSensorEntity, RestoreSensor):
    """Humidity measurement from an Easywave neo sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "neo_sensor_humidity"

    def __init__(self, entry: EasywaveConfigEntry, device: EasywaveDeviceEntry) -> None:
        """Initialize the humidity sensor."""
        super().__init__(entry, device, "humidity")
        self._attr_native_value: float | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last known humidity."""
        if (last_data := await self.async_get_last_sensor_data()) is not None:
            if isinstance(last_data.native_value, (int, float)):
                self._attr_native_value = float(last_data.native_value)
        await super().async_added_to_hass()

    @override
    @property
    def native_value(self) -> float | None:
        """Return the current humidity."""
        return self._attr_native_value

    @override
    @callback
    def handle_telegram(self, event: SensorTelegramEvent) -> None:
        """Update humidity from a measurement telegram."""
        value = event.payload.humidity_percent
        if value is None:
            return
        self._attr_native_value = value
        _LOGGER.debug(
            "Updated humidity for sensor %s to %s",
            self._sensor_serial,
            value,
        )
        self.async_write_ha_state()
