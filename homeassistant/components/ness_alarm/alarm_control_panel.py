"""Support for Ness D8X/D16X alarm panel."""

from __future__ import annotations

import logging

from nessclient import ArmingMode, ArmingState

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_NESS, SIGNAL_ARMING_STATE_CHANGED, NessAlarmConfigEntry
from .const import DOMAIN, SUBENTRY_TYPE_HOME

_LOGGER = logging.getLogger(__name__)

ARMING_MODE_TO_STATE = {
    ArmingMode.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    ArmingMode.ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
    ArmingMode.ARMED_DAY: AlarmControlPanelState.ARMED_AWAY,  # no applicable state, fallback to away
    ArmingMode.ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
    ArmingMode.ARMED_VACATION: AlarmControlPanelState.ARMED_VACATION,
    ArmingMode.ARMED_HIGHEST: AlarmControlPanelState.ARMED_AWAY,  # no applicable state, fallback to away
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NessAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ness Alarm alarm control panel from config entry."""
    client = entry.runtime_data
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    # Get home subentries
    home_subentries = filter(
        lambda subentry: subentry.subentry_type == SUBENTRY_TYPE_HOME,
        entry.subentries.values(),
    )

    # Create alarm panel entities from home subentries
    for subentry in home_subentries:
        async_add_entities(
            [NessAlarmPanel(client, host, port)],
            config_subentry_id=subentry.subentry_id,
        )


async def async_setup_platform(  # pragma: no cover
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ness Alarm alarm control panel devices (deprecated YAML)."""
    if discovery_info is None:
        return

    device = NessAlarmPanel(hass.data[DATA_NESS])
    async_add_entities([device])


class NessAlarmPanel(AlarmControlPanelEntity):
    """Representation of a Ness alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_should_poll = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(
        self, client, host: str | None = None, port: int | None = None
    ) -> None:
        """Initialize the alarm panel."""
        self._client = client

        # Config entry setup (has unique_id)
        if host is not None and port is not None:
            self._attr_has_entity_name = True
            self._attr_name = None
            self._attr_unique_id = f"{host}_{port}"

            # Create device info for the alarm panel (makes it a separate device)
            self._attr_device_info = DeviceInfo(
                name="Alarm Panel",
                identifiers={(DOMAIN, self._attr_unique_id)},
            )
        else:  # pragma: no cover
            # YAML setup (no unique_id, for backward compatibility)
            self._attr_name = "Alarm Panel"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ARMING_STATE_CHANGED, self._handle_arming_state_change
            )
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._client.disarm(code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._client.arm_away(code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._client.arm_home(code)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send trigger/panic command."""
        await self._client.panic(code)

    @callback
    def _handle_arming_state_change(
        self, arming_state: ArmingState, arming_mode: ArmingMode | None
    ) -> None:
        """Handle arming state update."""

        if arming_state == ArmingState.UNKNOWN:
            self._attr_alarm_state = None
        elif arming_state == ArmingState.DISARMED:
            self._attr_alarm_state = AlarmControlPanelState.DISARMED
        elif arming_state in (ArmingState.ARMING, ArmingState.EXIT_DELAY):
            self._attr_alarm_state = AlarmControlPanelState.ARMING
        elif arming_state == ArmingState.ARMED:
            self._attr_alarm_state = ARMING_MODE_TO_STATE.get(
                arming_mode, AlarmControlPanelState.ARMED_AWAY
            )
        elif arming_state == ArmingState.ENTRY_DELAY:
            self._attr_alarm_state = AlarmControlPanelState.PENDING
        elif arming_state == ArmingState.TRIGGERED:
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
        else:
            _LOGGER.warning("Unhandled arming state: %s", arming_state)

        self.async_write_ha_state()
