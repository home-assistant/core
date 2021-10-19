"""
Alexa Devices Alarm Control Panel using Guard Mode.

SPDX-License-Identifier: Apache-2.0

For more details about this platform, please refer to the documentation at
https://community.home-assistant.io/t/echo-devices-alexa-as-media-player-testers-needed/58639
"""
from asyncio import sleep
import logging
from typing import Dict, List, Optional, Text  # noqa pylint: disable=unused-import

from alexapy import hide_email, hide_serial
from homeassistant.const import (
    CONF_EMAIL,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
    STATE_UNAVAILABLE,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .alexa_entity import parse_guard_state_from_coordinator
from .alexa_media import AlexaMedia
from .const import (
    CONF_EXCLUDE_DEVICES,
    CONF_INCLUDE_DEVICES,
    CONF_QUEUE_DELAY,
    DATA_ALEXAMEDIA,
    DEFAULT_QUEUE_DELAY,
    DOMAIN as ALEXA_DOMAIN,
)
from .helpers import _catch_login_errors, add_devices

try:
    from homeassistant.components.alarm_control_panel import (
        AlarmControlPanelEntity as AlarmControlPanel,
    )
except ImportError:
    from homeassistant.components.alarm_control_panel import AlarmControlPanel


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [ALEXA_DOMAIN]


async def async_setup_platform(
    hass, config, add_devices_callback, discovery_info=None
) -> bool:
    """Set up the Alexa alarm control panel platform."""
    devices = []  # type: List[AlexaAlarmControlPanel]
    account = config[CONF_EMAIL] if config else discovery_info["config"][CONF_EMAIL]
    include_filter = config.get(CONF_INCLUDE_DEVICES, [])
    exclude_filter = config.get(CONF_EXCLUDE_DEVICES, [])
    account_dict = hass.data[DATA_ALEXAMEDIA]["accounts"][account]
    guard_media_players = {}
    for key, device in account_dict["devices"]["media_player"].items():
        if key not in account_dict["entities"]["media_player"]:
            _LOGGER.debug(
                "%s: Media player %s not loaded yet; delaying load",
                hide_email(account),
                hide_serial(key),
            )
            raise ConfigEntryNotReady
        if "GUARD_EARCON" in device["capabilities"]:
            guard_media_players[key] = account_dict["entities"]["media_player"][key]
    if "alarm_control_panel" not in (account_dict["entities"]):
        (
            hass.data[DATA_ALEXAMEDIA]["accounts"][account]["entities"][
                "alarm_control_panel"
            ]
        ) = {}
    alexa_client: Optional[AlexaAlarmControlPanel] = None
    guard_entities = account_dict.get("devices", {}).get("guard", [])
    if guard_entities:
        alexa_client = AlexaAlarmControlPanel(
            account_dict["login_obj"],
            account_dict["coordinator"],
            guard_entities[0],
            guard_media_players,
        )
    else:
        _LOGGER.debug("%s: No Alexa Guard entity found", account)
    if not (alexa_client and alexa_client.unique_id):
        _LOGGER.debug(
            "%s: Skipping creation of uninitialized device: %s",
            hide_email(account),
            alexa_client,
        )
    elif alexa_client.unique_id not in (
        account_dict["entities"]["alarm_control_panel"]
    ):
        devices.append(alexa_client)
        (
            hass.data[DATA_ALEXAMEDIA]["accounts"][account]["entities"][
                "alarm_control_panel"
            ][alexa_client.unique_id]
        ) = alexa_client
    else:
        _LOGGER.debug(
            "%s: Skipping already added device: %s", hide_email(account), alexa_client
        )
    return await add_devices(
        hide_email(account),
        devices,
        add_devices_callback,
        include_filter,
        exclude_filter,
    )


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Alexa alarm control panel platform by config_entry."""
    return await async_setup_platform(
        hass, config_entry.data, async_add_devices, discovery_info=None
    )


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    account = entry.data[CONF_EMAIL]
    _LOGGER.debug("Attempting to unload alarm control panel")
    account_dict = hass.data[DATA_ALEXAMEDIA]["accounts"][account]
    for device in account_dict["entities"]["alarm_control_panel"].values():
        _LOGGER.debug("Removing %s", device)
        await device.async_remove()
    return True


class AlexaAlarmControlPanel(AlarmControlPanel, AlexaMedia, CoordinatorEntity):
    """Implementation of Alexa Media Player alarm control panel."""

    def __init__(self, login, coordinator, guard_entity, media_players=None) -> None:
        # pylint: disable=unexpected-keyword-arg
        """Initialize the Alexa device."""
        AlexaMedia.__init__(self, None, login)
        CoordinatorEntity.__init__(self, coordinator)
        _LOGGER.debug("%s: Initiating alarm control panel", hide_email(login.email))
        # AlexaAPI requires a AlexaClient object, need to clean this up

        # Guard info
        self._appliance_id = guard_entity["appliance_id"]
        self._guard_entity_id = guard_entity["id"]
        self._friendly_name = "Alexa Guard " + self._appliance_id[-5:]
        self._media_players = {} or media_players
        self._attrs: Dict[Text, Text] = {}
        _LOGGER.debug(
            "%s: Guard Discovered %s: %s %s",
            self.account,
            self._friendly_name,
            hide_serial(self._appliance_id),
            hide_serial(self._guard_entity_id),
        )

    @_catch_login_errors
    async def _async_alarm_set(self, command: Text = "", code=None) -> None:
        # pylint: disable=unexpected-keyword-arg
        """Send command."""
        try:
            if not self.enabled:
                return
        except AttributeError:
            pass
        if command not in (STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED):
            _LOGGER.error("Invalid command: %s", command)
            return
        command_map = {STATE_ALARM_ARMED_AWAY: "AWAY", STATE_ALARM_DISARMED: "HOME"}
        available_media_players = list(
            filter(lambda x: x.state != STATE_UNAVAILABLE, self._media_players.values())
        )
        if available_media_players:
            _LOGGER.debug("Sending guard command to: %s", available_media_players[0])
            available_media_players[0].check_login_changes()
            await available_media_players[0].alexa_api.set_guard_state(
                self._appliance_id.split("_")[2],
                command_map[command],
                queue_delay=self.hass.data[DATA_ALEXAMEDIA]["accounts"][self.email][
                    "options"
                ].get(CONF_QUEUE_DELAY, DEFAULT_QUEUE_DELAY),
            )
            await sleep(2)  # delay
        else:
            _LOGGER.debug("Performing static guard command")
            await self.alexa_api.static_set_guard_state(
                self._login, self._guard_entity_id, command
            )
        await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code=None) -> None:
        # pylint: disable=unexpected-keyword-arg
        """Send disarm command."""
        await self._async_alarm_set(STATE_ALARM_DISARMED)

    async def async_alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        # pylint: disable=unexpected-keyword-arg
        await self._async_alarm_set(STATE_ALARM_ARMED_AWAY)

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._guard_entity_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._friendly_name

    @property
    def state(self):
        """Return the state of the device."""
        _state = parse_guard_state_from_coordinator(
            self.coordinator, self._guard_entity_id
        )
        if _state == "ARMED_AWAY":
            return STATE_ALARM_ARMED_AWAY
        elif _state == "ARMED_STAY":
            return STATE_ALARM_DISARMED
        else:
            return STATE_ALARM_DISARMED

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        try:
            from homeassistant.components.alarm_control_panel import (
                SUPPORT_ALARM_ARM_AWAY,
            )
        except ImportError:
            return 0
        return SUPPORT_ALARM_ARM_AWAY

    @property
    def assumed_state(self) -> bool:
        last_refresh_success = (
            self.coordinator.data and self._guard_entity_id in self.coordinator.data
        )
        return not last_refresh_success

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs
