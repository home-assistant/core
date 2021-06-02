"""Representation of a deCONZ remote or keypad."""

from pydeconz.sensor import (
    ANCILLARY_CONTROL_ARMED_AWAY,
    ANCILLARY_CONTROL_ARMED_NIGHT,
    ANCILLARY_CONTROL_ARMED_STAY,
    ANCILLARY_CONTROL_DISARMED,
    AncillaryControl,
    Switch,
)

from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE_ID,
    CONF_EVENT,
    CONF_ID,
    CONF_UNIQUE_ID,
    CONF_XY,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify

from .const import CONF_ANGLE, CONF_GESTURE, LOGGER, NEW_SENSOR
from .deconz_device import DeconzBase

CONF_DECONZ_EVENT = "deconz_event"
CONF_DECONZ_ALARM_EVENT = "deconz_alarm_event"

DECONZ_TO_ALARM_STATE = {
    ANCILLARY_CONTROL_ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    ANCILLARY_CONTROL_ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
    ANCILLARY_CONTROL_ARMED_STAY: STATE_ALARM_ARMED_HOME,
    ANCILLARY_CONTROL_DISARMED: STATE_ALARM_DISARMED,
}


async def async_setup_events(gateway) -> None:
    """Set up the deCONZ events."""

    @callback
    def async_add_sensor(sensors=gateway.api.sensors.values()):
        """Create DeconzEvent."""
        for sensor in sensors:

            if not gateway.option_allow_clip_sensor and sensor.type.startswith("CLIP"):
                continue

            if (
                sensor.type not in Switch.ZHATYPE + AncillaryControl.ZHATYPE
                or sensor.uniqueid in {event.unique_id for event in gateway.events}
            ):
                continue

            if sensor.type in Switch.ZHATYPE:
                new_event = DeconzEvent(sensor, gateway)

            elif sensor.type in AncillaryControl.ZHATYPE:
                new_event = DeconzAlarmEvent(sensor, gateway)

            gateway.hass.async_create_task(new_event.async_update_device_registry())
            gateway.events.append(new_event)

    gateway.config_entry.async_on_unload(
        async_dispatcher_connect(
            gateway.hass, gateway.async_signal_new_device(NEW_SENSOR), async_add_sensor
        )
    )

    async_add_sensor()


@callback
def async_unload_events(gateway) -> None:
    """Unload all deCONZ events."""
    for event in gateway.events:
        event.async_will_remove_from_hass()

    gateway.events.clear()


class DeconzEvent(DeconzBase):
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, device, gateway):
        """Register callback that will be used for signals."""
        super().__init__(device, gateway)

        self._device.register_callback(self.async_update_callback)

        self.device_id = None
        self.event_id = slugify(self._device.name)
        LOGGER.debug("deCONZ event created: %s", self.event_id)

    @property
    def device(self):
        """Return Event device."""
        return self._device

    @callback
    def async_will_remove_from_hass(self) -> None:
        """Disconnect event object when removed."""
        self._device.remove_callback(self.async_update_callback)

    @callback
    def async_update_callback(self, force_update=False):
        """Fire the event if reason is that state is updated."""
        if (
            self.gateway.ignore_state_updates
            or "state" not in self._device.changed_keys
        ):
            return

        data = {
            CONF_ID: self.event_id,
            CONF_UNIQUE_ID: self.serial,
            CONF_EVENT: self._device.state,
        }

        if self.device_id:
            data[CONF_DEVICE_ID] = self.device_id

        if self._device.gesture is not None:
            data[CONF_GESTURE] = self._device.gesture

        if self._device.angle is not None:
            data[CONF_ANGLE] = self._device.angle

        if self._device.xy is not None:
            data[CONF_XY] = self._device.xy

        self.gateway.hass.bus.async_fire(CONF_DECONZ_EVENT, data)

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        if not self.device_info:
            return

        device_registry = (
            await self.gateway.hass.helpers.device_registry.async_get_registry()
        )

        entry = device_registry.async_get_or_create(
            config_entry_id=self.gateway.config_entry.entry_id, **self.device_info
        )
        self.device_id = entry.id


class DeconzAlarmEvent(DeconzEvent):
    """Alarm control panel companion event when user inputs a code."""

    @callback
    def async_update_callback(self, force_update=False):
        """Fire the event if reason is that state is updated."""
        if (
            self.gateway.ignore_state_updates
            or "action" not in self._device.changed_keys
            or self._device.action == ""
        ):
            return

        state, code, _area = self._device.action.split(",")

        if state not in DECONZ_TO_ALARM_STATE:
            return

        data = {
            CONF_ID: self.event_id,
            CONF_UNIQUE_ID: self.serial,
            CONF_DEVICE_ID: self.device_id,
            CONF_EVENT: DECONZ_TO_ALARM_STATE[state],
            CONF_CODE: code,
        }

        self.gateway.hass.bus.async_fire(CONF_DECONZ_ALARM_EVENT, data)
