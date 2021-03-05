"""Support for Freebox alarm"""
import logging
import json
import time
import async_timeout

from typing import Dict, Optional
from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from datetime import datetime, timedelta

from .const import DOMAIN, VALUE_NOT_SET
from .router import FreeboxRouter
from .base_class import FreeboxHomeBaseClass


from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)

from homeassistant.const import (
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_PENDING,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMING,
    STATE_ALARM_TRIGGERED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities) -> None:
    router = hass.data[DOMAIN][entry.unique_id]
    tracked = set()

    @callback
    def update_callback():
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(async_dispatcher_connect(hass, router.signal_home_device_new, update_callback))
    update_callback()


@callback
def add_entities(hass, router, async_add_entities, tracked):
    """Add new Alarm Control Panel from the router."""
    new_tracked = []

    for nodeId, node in router.home_devices.items():
        if (node["category"]!="alarm") or (nodeId in tracked):
            continue
        new_tracked.append(FreeboxAlarm(hass, router, node))
        tracked.add(nodeId)

    if new_tracked:
        async_add_entities(new_tracked, True)



class FreeboxAlarm(FreeboxHomeBaseClass, AlarmControlPanelEntity):

    def __init__(self, hass, router: FreeboxRouter, node: Dict[str, any]) -> None:
        """Initialize an Alarm"""
        super().__init__(hass, router, node)

        self._command_trigger   = self.get_command_id(node['type']['endpoints'], "slot", "trigger") # Trigger
        self._command_alarm1    = self.get_command_id(node['type']['endpoints'], "slot", "alarm1") # Alarme principale
        self._command_alarm2    = self.get_command_id(node['type']['endpoints'], "slot", "alarm2") # Alarme secondaire
        self._command_skip      = self.get_command_id(node['type']['endpoints'], "slot", "skip") # Passer le délai
        self._command_off       = self.get_command_id(node['type']['endpoints'], "slot", "off") # Désactiver l'alarme
        self._command_pin       = self.get_command_id(node['type']['endpoints'], "slot", "pin") # Code PIN
        self._command_sound     = self.get_command_id(node['type']['endpoints'], "slot", "sound") # Puissance des bips
        self._command_volume    = self.get_command_id(node['type']['endpoints'], "slot", "volume") # Puissance de la sirène
        self._command_timeout1  = self.get_command_id(node['type']['endpoints'], "slot", "timeout1") # Délai avant armement
        self._command_timeout2  = self.get_command_id(node['type']['endpoints'], "slot", "timeout2") # Délai avant sirène
        self._command_timeout3  = self.get_command_id(node['type']['endpoints'], "slot", "timeout3") # Durée de la sirène
        self._command_state     = self.get_command_id(node['type']['endpoints'], "signal", "state" )

        self.set_state("idle")
        self._unsub_watcher = None
        self._supported_features = SUPPORT_ALARM_ARM_AWAY
        self.update_parameters(node)

    @property
    def state(self) -> str:
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._supported_features

    async def async_alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        if( await self.set_home_endpoint_value(self._command_off, {"value": None})):
            time.sleep(1)
            self.schedule_update_ha_state(True)

    async def async_alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        if( await self.set_home_endpoint_value(self._command_alarm1, {"value": None})):
            time.sleep(1)
            self._unsub_watcher = async_track_time_interval(self.hass, self.sync_update_during_arming, timedelta(seconds=1))

    async def async_alarm_arm_home(self, code=None) -> None:
        await self.async_alarm_arm_night(code)

    async def async_alarm_arm_night(self, code=None) -> None:
        """Send arm night command."""
        if( await self.set_home_endpoint_value(self._command_alarm2, {"value": None})):
            time.sleep(1)
            self._unsub_watcher = async_track_time_interval(self.hass, self.sync_update_during_arming, timedelta(seconds=1))


    async def sync_update_during_arming(self, now: Optional[datetime] = None) -> None:
        self.set_state(await self.get_home_endpoint_value( self._command_state))
        self.async_write_ha_state()

    async def async_update(self):
        """Get the state & name and update it."""
        state = await self.get_home_endpoint_value( self._command_state)
        if( state == "idle" and self._unsub_watcher != None):
            self._unsub_watcher()
        self.update_parameters(self._router.home_devices[self._id])


    def update_parameters(self, node):
        #Update name
        self._name = node["label"].strip()

        #Search if Alarm2
        has_alarm2 = False
        for nodeId, local_node in self._router.home_devices.items():
            alarm2 = next(filter(lambda x: (x["name"]=="alarm2" and x["ep_type"]=="signal"), local_node['show_endpoints']), None)
            if( alarm2 != None and alarm2["value"] == True):
                has_alarm2 = True
                break

        if( has_alarm2 ):
            self._supported_features = SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT
        else:
            self._supported_features = SUPPORT_ALARM_ARM_AWAY


        # Parse all endpoints values
        for endpoint in filter(lambda x:(x["ep_type"] == "signal"), node['show_endpoints']):
            if( endpoint["name"] == "pin" ):
                self._pin = endpoint["value"]
            elif( endpoint["name"] == "sound" ):
                self._sound = endpoint["value"]
            elif( endpoint["name"] == "volume" ):
                self._high_volume = endpoint["value"]
            elif( endpoint["name"] == "timeout1" ):
                self._timeout1 = endpoint["value"]
            elif( endpoint["name"] == "timeout3" ):
                self._timeout2 = endpoint["value"]
            elif( endpoint["name"] == "timeout3" ):
                self._timeout3 = endpoint["value"]
            elif( endpoint["name"] == "battery" ):
                self._battery = endpoint["value"]

    def set_state(self, state):
        if( state == "alarm1_arming"):
            self._state = STATE_ALARM_ARMING
        elif( state == "alarm2_arming"):
            self._state = STATE_ALARM_ARMING
        elif( state == "alarm1_armed"):
            self._state = STATE_ALARM_ARMED_AWAY
        elif( state == "alarm2_armed"):
            self._state = STATE_ALARM_ARMED_NIGHT
        elif( state == "alarm1_alert_timer"):
            self._state = STATE_ALARM_TRIGGERED
        elif( state == "alarm2_alert_timer"):
            self._state = STATE_ALARM_TRIGGERED
        elif( state == "alert"):
            self._state = STATE_ALARM_TRIGGERED
        else:
            self._state = STATE_ALARM_DISARMED

