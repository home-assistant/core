"""number.py

Home Assistant NumberEntity for controlling and monitoring the maximum charging current
of a Greencell EVSE device over MQTT, with automatic retry logic.

This module provides:
- EVSEMaxCurrent: NumberEntity that sends SET_CURRENT commands to the EVSE and updates its state.
  * Validates requested current against device-specific limits (Habu Den vs. other).
  * Starts a retry loop (interval SET_CURRENT_RETRY_TIME) until the device confirms the change.
  * Listens on MQTT topics for device_state and current to detect confirmation and update UI.
- async_setup_platform / async_setup_entry: legacy YAML and config-entry setup of the entity.
- _setup_current_number: common helper to subscribe to MQTT topics and instantiate EVSEMaxCurrent.

Constants imported from const.py:
  DEFAULT_MIN_CURRENT, DEFAULT_MAX_CURRENT_HABU_DEN, DEFAULT_MAX_CURRENT_OTHER,
  SET_CURRENT_RETRY_TIME, GREENCELL_HABU_DEN_SERIAL_PREFIX, etc.
"""

import asyncio
import json
import logging

from homeassistant.components.mqtt import async_publish, async_subscribe
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DEFAULT_MAX_CURRENT_HABU_DEN,
    DEFAULT_MAX_CURRENT_OTHER,
    DEFAULT_MIN_CURRENT,
    GREENCELL_HABU_DEN,
    GREENCELL_HABU_DEN_SERIAL_PREFIX,
    GREENCELL_OTHER_DEVICE,
    MANUFACTURER,
    SET_CURRENT_RETRY_TIME,
    GreencellHaAccessLevelEnum as AccessLevel,
)
from .helper import GreencellAccess

_LOGGER = logging.getLogger(__name__)


class EVSEMaxCurrent(NumberEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        serial_number: str,
        max_current: int,
        access: GreencellAccess,
    ):
        self._hass = hass
        self._serial = serial_number
        self._access = access
        self._attr_name = "EVSE Max Current"
        self._attr_native_unit_of_measurement = "A"
        self._attr_native_min_value = DEFAULT_MIN_CURRENT

        self._attr_native_step = 1
        self._value = DEFAULT_MIN_CURRENT

        self._desired_value: int | None = None
        self._retry_task: asyncio.Task | None = None
        self._confirmed: bool = False

        if self._device_is_habu_den():
            if max_current > DEFAULT_MAX_CURRENT_HABU_DEN:
                _LOGGER.warning(
                    "Max current for Habu Den is limited to %d A",
                    DEFAULT_MAX_CURRENT_HABU_DEN,
                )
                max_current = DEFAULT_MAX_CURRENT_HABU_DEN
        elif max_current > DEFAULT_MAX_CURRENT_OTHER:
            _LOGGER.warning(
                "Max current for unknown device type is limited to %d A",
                DEFAULT_MAX_CURRENT_OTHER,
            )
            max_current = DEFAULT_MAX_CURRENT_OTHER

        self._attr_native_max_value = max_current

    def _device_is_habu_den(self) -> bool:
        """Check if the device is a Habu Den based on its serial number."""
        return self._serial.startswith(GREENCELL_HABU_DEN_SERIAL_PREFIX)

    def _device_name(self) -> str:
        """Return the device name based on its type."""
        if self._device_is_habu_den():
            return GREENCELL_HABU_DEN
        return GREENCELL_OTHER_DEVICE

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the entity."""
        return f"{self._device_name()}_{self._serial}_max_current"

    @property
    def native_value(self) -> int:
        """Return the current value."""
        return self._value

    @property
    def device_info(self) -> dict:
        """Return device information."""
        if self._device_is_habu_den():
            device_name = GREENCELL_HABU_DEN
        else:
            device_name = GREENCELL_OTHER_DEVICE
        return {
            "identifiers": {(self._serial,)},
            "name": f"{device_name} {self._serial}",
            "manufacturer": MANUFACTURER,
            "model": device_name,
        }

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return self._access.can_execute()

    @property
    def max_current(self) -> int:
        """Return the max current value."""
        return self._value

    @property
    def enabled(self) -> bool:
        """Return True if the entity is enabled."""
        return self._access.can_execute()

    async def _send_new_value_set_request(self, value: int) -> None:
        """Send the new value to the device."""
        topic = f"/greencell/evse/{self._serial}/cmd"
        payload = json.dumps({"name": "SET_CURRENT", "current": value})

        _LOGGER.info("Set max current to %d A on %s", value, self._serial)
        await async_publish(self._hass, topic, payload, qos=1)

    async def _update_current_value(self, value: int) -> None:
        """Set the value of the entity."""
        self._value = value
        self.async_schedule_update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity. Value will be updated after receiving confirmation from the device. Start retry loop task."""
        if value == self._value:
            ## No change in value
            return

        if value < DEFAULT_MIN_CURRENT or value > self._attr_native_max_value:
            _LOGGER.error("Value %d is out of range for %s", value, self._serial)
            return

        self._confirmed = False
        self._desired_value = int(value)

        await self._send_new_value_set_request(int(value))

        if self._retry_task:
            self._retry_task.cancel()

        self._retry_task = self._hass.async_create_task(self._retry_loop())

    async def _retry_loop(self):
        """Retry loop to confirm the new value."""
        """Wait for confirmation from the device that the new value has been set."""
        try:
            while not self._confirmed:
                await asyncio.sleep(SET_CURRENT_RETRY_TIME)
                if self._confirmed or self._desired_value is None:
                    break
                _LOGGER.info("Retry SET_CURRENT %d A", self._desired_value)
                await self._send_new_value_set_request(self._desired_value)
        except asyncio.CancelledError:
            # The task was cancelled, do nothing
            return

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant."""
        self._access.register_listener(self._schedule_update)

    def _schedule_update(self):
        """Schedule state update from external EVSE state change."""
        if self.hass:
            self.async_schedule_update_ha_state()

    async def update_max_current(self, new_max_current: int) -> None:
        """Update the max current value."""
        if new_max_current == self._attr_native_max_value:
            ## No change in max current
            return

        if new_max_current < self._value:
            self._value = new_max_current
            await self._send_new_value_set_request(new_max_current)

        if self._desired_value is not None and new_max_current != self._desired_value:
            _LOGGER.warning(
                "New max current %d A is different from the desired value %d A",
                new_max_current,
                self._desired_value,
            )

        self._desired_value = None
        self._confirmed = True
        self._attr_native_max_value = new_max_current
        self.async_schedule_update_ha_state()
        if self._retry_task:
            self._retry_task.cancel()
            self._retry_task = None


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up max current number entity from yaml (legacy setup)."""

    serial = (
        discovery_info.get("serial_number")
        if discovery_info
        else config.get("serial_number")
    )
    max_current = (
        int(discovery_info.get("max_current", DEFAULT_MAX_CURRENT_HABU_DEN))
        if discovery_info
        else int(config.get("max_current", DEFAULT_MAX_CURRENT_HABU_DEN))
    )

    await _setup_current_number(hass, async_add_entities, serial, max_current)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up max current number entity from a config entry."""

    serial = (
        discovery_info.get("serial_number")
        if discovery_info
        else entry.data.get("serial_number")
    )
    max_current = (
        int(discovery_info.get("max_current", DEFAULT_MAX_CURRENT_HABU_DEN))
        if discovery_info
        else int(entry.data.get("max_current", DEFAULT_MAX_CURRENT_HABU_DEN))
    )

    if not serial:
        _LOGGER.error("Missing serial_number in configuration or discovery_info")
        return

    await _setup_current_number(hass, async_add_entities, serial, max_current)


async def _setup_current_number(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    serial_number: str,
    max_current: int,
) -> None:
    """Set up the Greencell EVSE max current number entity."""

    mqtt_ha_access_topic = f"/greencell/evse/{serial_number}/device_state"
    mqtt_ha_current_topic = f"/greencell/evse/{serial_number}/current"
    mqtt_evse_state_topic = f"/greencell/evse/{serial_number}/status"

    access = GreencellAccess(AccessLevel.EXECUTE)
    entity = EVSEMaxCurrent(hass, serial_number, max_current, access)

    @callback
    async def device_state_msg_received(msg) -> None:
        """Handle the device state message."""
        try:
            data = json.loads(msg.payload)
            if "level" in data:
                access.update(data["level"])
            if "hems_current" in data:
                hems_current = int(data["hems_current"])
                if entity.enabled:
                    if hems_current == 0:
                        await entity._send_new_value_set_request(entity.max_current)
                    else:
                        await entity._update_current_value(hems_current)

        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to decode HA access message: %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected error: %s", e)

    @callback
    async def current_msg_received(msg) -> None:
        """Handle the current message. Catch maximal current set by electrician for the EVSE."""
        try:
            data = json.loads(msg.payload)
            if "i_max" in data:
                max_current = int(data["i_max"])
                await entity.update_max_current(max_current)
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to decode current message: %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected error: %s", e)

    @callback
    def state_msg_received(msg) -> None:
        """Handle the state message. If the device is offline, disable the entity."""
        try:
            data = json.loads(msg.payload)
            if "state" in data:
                state = data["state"]
                if "OFFLINE" in state:
                    access.update("OFFLINE")
        except json.JSONDecodeError as e:
            _LOGGER.error("Error decoding JSON message: %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected error: %s", e)

    await async_subscribe(hass, mqtt_ha_access_topic, device_state_msg_received)
    await async_subscribe(hass, mqtt_ha_current_topic, current_msg_received)
    await async_subscribe(hass, mqtt_evse_state_topic, state_msg_received)

    async_add_entities([entity])
