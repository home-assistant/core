"""Support for HomematicIP Cloud alarm control panel."""

import logging
from typing import TYPE_CHECKING, override

from homematicip.connection.rest_connection import RestResult
from homematicip.functionalHomes import SecurityAndAlarmHome
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .hap import AsyncHome, HomematicIPConfigEntry, HomematicipHAP

_LOGGER = logging.getLogger(__name__)

CONST_ALARM_CONTROL_PANEL_NAME = "HmIP Alarm Control Panel"

MODE_AWAY = "away"
MODE_HOME = "home"
SERVICE_ARM_ANYWAY = "arm_anyway"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP alrm control panel from a config entry."""
    hap = config_entry.runtime_data
    async_add_entities([HomematicipAlarmControlPanelEntity(hap)])

    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_ARM_ANYWAY,
        {vol.Required(ATTR_MODE): vol.In([MODE_HOME, MODE_AWAY])},
        "async_arm_anyway",
    )


class HomematicipAlarmControlPanelEntity(AlarmControlPanelEntity):
    """Representation of the HomematicIP alarm control panel."""

    _attr_should_poll = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_code_arm_required = False
    _feature_id = "alarm"

    def __init__(self, hap: HomematicipHAP) -> None:
        """Initialize the alarm control panel."""
        self._hap = hap
        self._home: AsyncHome = hap.home

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        if TYPE_CHECKING:
            assert self.platform.config_entry is not None
        return DeviceInfo(
            identifiers={(DOMAIN, f"ACP {self._home.id}")},
            manufacturer="eQ-3",
            model=CONST_ALARM_CONTROL_PANEL_NAME,
            name=self.name,
            via_device_id=dr.async_get_device_id_by_identifier(
                self.hass,
                (DOMAIN, self._home.id),
                config_entry_id=self.platform.config_entry.entry_id,
            ),
        )

    @property
    @override
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the state of the alarm control panel."""
        # check for triggered alarm
        if self._security_and_alarm.alarmActive:
            return AlarmControlPanelState.TRIGGERED

        activation_state = self._home.get_security_zones_activation()
        # check arm_away
        if activation_state == (True, True):
            return AlarmControlPanelState.ARMED_AWAY
        # check arm_home
        if activation_state == (False, True):
            return AlarmControlPanelState.ARMED_HOME

        return AlarmControlPanelState.DISARMED

    @property
    def _security_and_alarm(self) -> SecurityAndAlarmHome:
        return self._home.get_functionalHome(SecurityAndAlarmHome)

    async def _async_set_zones_activation(
        self, *, internal: bool, external: bool
    ) -> None:
        """Set the zone activation and raise when the panel refuses it."""
        result = await self._home.set_security_zones_activation_async(
            internal, external
        )
        # a request-based panel answers 200 without arming when a sensor blocks it
        self._raise_for_result(result)

    def _publish_problems(self, result: RestResult) -> tuple[list[str], list[str]]:
        """Publish what refused the request and return its labels and channels."""
        # the access point does not push this, so it is taken from the reply
        blocking = sorted(
            label.strip()
            for label in self._home.get_security_zone_activation_problems(result)
        )
        channels = sorted(
            f"{channel['deviceId']}:{channel['channelIndex']}"
            for channel in self._home.get_security_zone_activation_problem_channels(
                result
            )
        )
        self._hap.async_set_arming_problems(blocking, channels)
        return blocking, channels

    def _raise_for_result(self, result: RestResult) -> None:
        """Raise a translated error when the panel did not accept the request."""
        blocking, _ = self._publish_problems(result)
        if result.success and not blocking:
            return
        if not blocking:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="alarm_activation_failed",
            )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="alarm_activation_blocked",
            translation_placeholders={"devices": ", ".join(blocking)},
        )

    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._async_set_zones_activation(internal=False, external=False)

    @override
    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._async_set_zones_activation(internal=False, external=True)

    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._async_set_zones_activation(internal=True, external=True)

    async def async_arm_anyway(self, mode: str) -> None:
        """Arm although sensors report a problem, leaving them unmonitored."""
        internal = mode == MODE_AWAY
        approved = set(self._hap.arming_problem_channels)

        # The user decides on the list of a previous attempt, and the access point
        # ignores whatever is open at the time of the call, not what was listed.
        # Ask again and refuse when anything else has opened since. Compared per
        # channel, because one device can block on several of them under one label.
        result = await self._home.set_security_zones_activation_async(internal, True)
        problems, channels = self._publish_problems(result)
        if not problems:
            # armed after all, or refused without naming a device
            self._raise_for_result(result)
            return

        if not approved.issuperset(channels):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="alarm_activation_outdated",
                translation_placeholders={"devices": ", ".join(problems)},
            )

        result = await self._home.set_security_zones_activation_with_ignore_list_async(
            internal, True
        )
        self._raise_for_result(result)

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._home.on_update(self._async_device_changed)

    @callback
    def _async_device_changed(self, *args, **kwargs) -> None:
        """Handle entity state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Event %s (%s)", self.name, CONST_ALARM_CONTROL_PANEL_NAME)
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                (
                    "Device Changed Event for %s (Alarm Control Panel) not fired."
                    " Entity is disabled"
                ),
                self.name,
            )

    @property
    @override
    def name(self) -> str:
        """Return the name of the generic entity."""
        name = CONST_ALARM_CONTROL_PANEL_NAME
        if self._home.name:
            name = f"{self._home.name} {name}"
        return name

    @property
    @override
    def available(self) -> bool:
        """Return if alarm control panel is available."""
        return self._home.connected

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._home.id}_{self._feature_id}"
