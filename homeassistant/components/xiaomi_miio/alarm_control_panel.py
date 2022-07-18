"""Support for Xiomi Gateway alarm control panels."""
from __future__ import annotations

from functools import partial
import logging

from miio import DeviceException

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import KEY_DEVICE, DOMAIN

_LOGGER = logging.getLogger(__name__)

XIAOMI_STATE_ARMED_VALUE = "on"
XIAOMI_STATE_DISARMED_VALUE = "off"
XIAOMI_STATE_ARMING_VALUE = "oning"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Xiaomi Gateway Alarm from a config entry."""
    entities = []
    gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
    entity = XiaomiGatewayAlarm(
        gateway,
        f"{config_entry.title} Alarm",
        config_entry.data["model"],
        config_entry.data["mac"],
        config_entry.unique_id,
    )
    entities.append(entity)
    async_add_entities(entities, update_before_add=True)


class XiaomiGatewayAlarm(AlarmControlPanelEntity):
    """Representation of the XiaomiGatewayAlarm."""

    _attr_icon = "mdi:shield-home"
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY

    def __init__(
        self, gateway_device, gateway_name, model, mac_address, gateway_device_id
    ):
        """Initialize the entity."""
        self._gateway = gateway_device
        self._attr_name = gateway_name
        self._attr_unique_id = f"{model}-{mac_address}"
        self._attr_available = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gateway_device_id)},
        )

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )
            _LOGGER.debug("Response received from miio device: %s", result)
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)

    @callback
    def alarm_callback(self, action, params):
        """Push from gateway."""
        _LOGGER.debug("Got new alarm_callback: %s", action)
        if action == "alarm_triggering":
            self._state = STATE_ALARM_TRIGGERED
            self.schedule_update_ha_state()
        self.hass.bus.fire(
            f"{DOMAIN}.alarm", {"entity_id": self.entity_id, "action": action}
        )

    async def async_added_to_hass(self):
        """Subscribe to push server callbacks and install the callbacks on the gateway."""
        self._gateway.register_callback(self.unique_id, self.alarm_callback)
        await self.hass.async_add_executor_job(
            self._gateway.alarm.subscribe_events
        )
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        """Unsubscribe callbacks and remove from gateway memory when removed."""
        await self.hass.async_add_executor_job(
            self._gateway.alarm.unsubscribe_events
        )
        self._gateway.remove_callback(self.unique_id)
        await super().async_will_remove_from_hass()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Turn on."""
        await self._try_command(
            "Turning the alarm on failed: %s", self._gateway.alarm.on
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Turn off."""
        await self._try_command(
            "Turning the alarm off failed: %s", self._gateway.alarm.off
        )

    async def async_update(self) -> None:
        """Fetch state from the device."""
        try:
            state = await self.hass.async_add_executor_job(self._gateway.alarm.status)
        except DeviceException as ex:
            if self._attr_available:
                self._attr_available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)

            return

        _LOGGER.debug("Got new state: %s", state)

        self._attr_available = True

        if state == XIAOMI_STATE_ARMED_VALUE:
            self._attr_state = STATE_ALARM_ARMED_AWAY
        elif state == XIAOMI_STATE_DISARMED_VALUE:
            self._attr_state = STATE_ALARM_DISARMED
        elif state == XIAOMI_STATE_ARMING_VALUE:
            self._attr_state = STATE_ALARM_ARMING
        else:
            _LOGGER.warning(
                "New state (%s) doesn't match expected values: %s/%s/%s",
                state,
                XIAOMI_STATE_ARMED_VALUE,
                XIAOMI_STATE_DISARMED_VALUE,
                XIAOMI_STATE_ARMING_VALUE,
            )
            self._attr_state = None

        _LOGGER.debug("State value: %s", self._attr_state)
