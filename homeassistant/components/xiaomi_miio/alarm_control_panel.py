"""Support for Xiomi Gateway alarm control panels."""

from functools import partial
import logging

from miio import DeviceException

from homeassistant.components.alarm_control_panel import (
    SUPPORT_ALARM_ARM_AWAY,
    AlarmControlPanelEntity,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

XIAOMI_STATE_ARMED_VALUE = "on"
XIAOMI_STATE_DISARMED_VALUE = "off"
XIAOMI_STATE_ARMING_VALUE = "oning"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Xiaomi Gateway Alarm from a config entry."""
    entities = []
    gateway = hass.data[DOMAIN][config_entry.entry_id]
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

    def __init__(
        self, gateway_device, gateway_name, model, mac_address, gateway_device_id
    ):
        """Initialize the entity."""
        self._gateway = gateway_device
        self._name = gateway_name
        self._gateway_device_id = gateway_device_id
        self._unique_id = f"{model}-{mac_address}"
        self._icon = "mdi:shield-home"
        self._available = None
        self._state = None

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def device_id(self):
        """Return the device id of the gateway."""
        return self._gateway_device_id

    @property
    def device_info(self):
        """Return the device info of the gateway."""
        return {
            "identifiers": {(DOMAIN, self._gateway_device_id)},
        }

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_AWAY

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )
            _LOGGER.debug("Response received from miio device: %s", result)
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)

    async def async_alarm_arm_away(self, code=None):
        """Turn on."""
        await self._try_command(
            "Turning the alarm on failed: %s", self._gateway.alarm.on
        )

    async def async_alarm_disarm(self, code=None):
        """Turn off."""
        await self._try_command(
            "Turning the alarm off failed: %s", self._gateway.alarm.off
        )

    async def async_update(self):
        """Fetch state from the device."""
        try:
            state = await self.hass.async_add_executor_job(self._gateway.alarm.status)
        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)

            return

        _LOGGER.debug("Got new state: %s", state)

        self._available = True

        if state == XIAOMI_STATE_ARMED_VALUE:
            self._state = STATE_ALARM_ARMED_AWAY
        elif state == XIAOMI_STATE_DISARMED_VALUE:
            self._state = STATE_ALARM_DISARMED
        elif state == XIAOMI_STATE_ARMING_VALUE:
            self._state = STATE_ALARM_ARMING
        else:
            _LOGGER.warning(
                "New state (%s) doesn't match expected values: %s/%s/%s",
                state,
                XIAOMI_STATE_ARMED_VALUE,
                XIAOMI_STATE_DISARMED_VALUE,
                XIAOMI_STATE_ARMING_VALUE,
            )
            self._state = None

        _LOGGER.debug("State value: %s", self._state)
