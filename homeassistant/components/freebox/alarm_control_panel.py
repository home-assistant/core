"""Support for Freebox alarms."""
import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ALARM_ARMING, STATE_ALARM_DISARMED, STATE_IDLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LABEL_TO_STATE
from .home_base import FreeboxHomeEntity
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up alarms."""
    router = hass.data[DOMAIN][entry.unique_id]
    tracked: set = set()

    @callback
    def update_callback():
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_home_device_new, update_callback)
    )
    update_callback()


@callback
def add_entities(
    hass: HomeAssistant,
    router: FreeboxRouter,
    async_add_entities: AddEntitiesCallback,
    tracked: set,
):
    """Add new alarms from the router."""
    new_tracked = []

    for nodeid, node in router.home_devices.items():
        if (node["category"] != "alarm") or (nodeid in tracked):
            continue
        new_tracked.append(FreeboxAlarm(hass, router, node))
        tracked.add(nodeid)

    if new_tracked:
        async_add_entities(new_tracked, True)


class FreeboxAlarm(FreeboxHomeEntity, AlarmControlPanelEntity):
    """Representation of a Freebox alarm."""

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize an alarm."""
        super().__init__(hass, router, node)

        self._attr_extra_state_attributes = {}
        self._state: str | Any
        # # Trigger
        # self._command_trigger = self.get_command_id(
        #     node["type"]["endpoints"], "slot", "trigger"
        # )
        # Alarme principale
        self._command_alarm1 = self.get_command_id(
            node["type"]["endpoints"], "slot", "alarm1"
        )
        # Alarme secondaire
        self._command_alarm2 = self.get_command_id(
            node["type"]["endpoints"], "slot", "alarm2"
        )
        # Passer le délai
        self._command_skip = self.get_command_id(
            node["type"]["endpoints"], "slot", "skip"
        )
        # Désactiver l'alarme
        self._command_off = self.get_command_id(
            node["type"]["endpoints"], "slot", "off"
        )
        # # Code PIN
        # self._command_pin = self.get_command_id(
        #     node["type"]["endpoints"], "slot", "pin"
        # )
        # # Puissance des bips
        # self._command_sound = self.get_command_id(
        #     node["type"]["endpoints"], "slot", "sound"
        # )
        # # Puissance de la sirène
        # self._command_volume = self.get_command_id(
        #     node["type"]["endpoints"], "slot", "volume"
        # )
        # # Délai avant armement
        # self._command_timeout1 = self.get_command_id(
        #     node["type"]["endpoints"], "slot", "timeout1"
        # )
        # # Délai avant sirène
        # self._command_timeout2 = self.get_command_id(
        #     node["type"]["endpoints"], "slot", "timeout2"
        # )
        # # Durée de la sirène
        # self._command_timeout3 = self.get_command_id(
        #     node["type"]["endpoints"], "slot", "timeout3"
        # )
        # État
        self._command_state = self.get_command_id(
            node["type"]["endpoints"], "signal", "state"
        )

        self.set_state(STATE_IDLE)
        # self._timeout1 = 15
        # self._attr_supported_features = (
        #     AlarmControlPanelEntityFeature.ARM_AWAY
        #     | AlarmControlPanelEntityFeature.ARM_HOME
        # )
        # self.update_node()
        self.update_node(self._router.home_devices[self._id])

    @property
    def state(self) -> str:
        """Return the state."""
        return self._state

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if await self.set_home_endpoint_value(self._command_off):
            self.set_state(STATE_ALARM_DISARMED)
            self.async_write_ha_state()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if await self.set_home_endpoint_value(self._command_alarm1):
            self.set_state(STATE_ALARM_ARMING)
            self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if await self.set_home_endpoint_value(self._command_alarm2):
            self.set_state(STATE_ALARM_ARMING)
            self.async_write_ha_state()

    async def async_update_signal(self):
        """Update signal."""
        self.set_state(await self.get_home_endpoint_value(self._command_state))
        # self.update_node()
        self.update_node(self._router.home_devices[self._id])
        self.async_write_ha_state()

    def update_node(self, node: dict[str, Any]) -> None:
        """Update the alarm."""
        # Search if Alarm2
        has_alarm2 = False
        for nodeid, local_node in self._router.home_devices.items():
            if nodeid == local_node["id"]:
                alarm2 = next(
                    filter(
                        lambda x: (x["name"] == "alarm2" and x["ep_type"] == "signal"),
                        local_node["show_endpoints"],
                    ),
                    None,
                )
                if alarm2:
                    has_alarm2 = alarm2["value"]
                    break

        if has_alarm2:
            self._attr_supported_features = (
                AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_HOME
            )

        else:
            self._attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY

        # Parse all endpoints values
        for endpoint in filter(
            lambda x: (x["ep_type"] == "signal"), node["show_endpoints"]
        ):
            self._attr_extra_state_attributes[endpoint["name"]] = endpoint["value"]

        # # Parse all endpoints values
        # for endpoint in filter(
        #     lambda x: (x["ep_type"] == "signal"), self._node["show_endpoints"]
        # ):
        #     if endpoint["name"] == "pin":
        #         self._pin = endpoint["value"]
        #     elif endpoint["name"] == "sound":
        #         self._sound = endpoint["value"]
        #     elif endpoint["name"] == "volume":
        #         self._high_volume = endpoint["value"]
        #     elif endpoint["name"] == "timeout1":
        #         self._timeout1 = endpoint["value"]
        #     elif endpoint["name"] == "timeout3":
        #         self._timeout2 = endpoint["value"]
        #     elif endpoint["name"] == "timeout3":
        #         self._timeout3 = endpoint["value"]
        #     elif endpoint["name"] == "battery":
        #         self._battery = endpoint["value"]

    # def set_state2(self, state: str):
    #     """Update state."""
    #     if state == "alarm1_arming":
    #         self._state = STATE_ALARM_ARMING
    #     elif state == "alarm2_arming":
    #         self._state = STATE_ALARM_ARMING
    #     elif state == "alarm1_armed":
    #         self._state = STATE_ALARM_ARMED_AWAY
    #     elif state == "alarm2_armed":
    #         self._state = STATE_ALARM_ARMED_NIGHT
    #     elif state == "alarm1_alert_timer":
    #         self._state = STATE_ALARM_TRIGGERED
    #     elif state == "alarm2_alert_timer":
    #         self._state = STATE_ALARM_TRIGGERED
    #     elif state == "alert":
    #         self._state = STATE_ALARM_TRIGGERED
    #     else:
    #         self._state = STATE_ALARM_DISARMED

    def set_state(self, state: str) -> None:
        """Update state."""
        self._state = LABEL_TO_STATE.get(state)
        if self._state is None:
            self._state = STATE_ALARM_DISARMED
