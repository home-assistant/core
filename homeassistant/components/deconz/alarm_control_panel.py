"""Support for deCONZ climate devices."""
from __future__ import annotations

from pydeconz.sensor import AncillaryControl

from homeassistant.components.alarm_control_panel import DOMAIN, AlarmControlPanelEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import NEW_SENSOR
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ alarm control panel devices.

    Alarm control panels are based on the same device class as sensors in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_alarm_control_panel(sensors=gateway.api.sensors.values()):
        """Add alarm control panel devices from deCONZ."""
        entities = []

        for sensor in sensors:

            if (
                sensor.type in AncillaryControl.ZHATYPE
                and sensor.uniqueid not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzAlarmControlPanel(sensor, gateway))

        if entities:
            async_add_entities(entities)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass,
            gateway.async_signal_new_device(NEW_SENSOR),
            async_add_alarm_control_panel,
        )
    )

    async_add_alarm_control_panel()


class DeconzAlarmControlPanel(DeconzDevice, AlarmControlPanelEntity):
    """Representation of a deCONZ alarm control panel."""

    TYPE = DOMAIN

    def __init__(self, device, gateway):
        """Set up alarm control panel device."""
        super().__init__(device, gateway)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
