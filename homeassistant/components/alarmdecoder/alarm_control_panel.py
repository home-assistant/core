"""Support for AlarmDecoder-based alarm control panels (Honeywell/DSC)."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AlarmDecoderConfigEntry
from .const import (
    CONF_ALT_NIGHT_MODE,
    CONF_AUTO_BYPASS,
    CONF_CODE_ARM_REQUIRED,
    DEFAULT_ARM_OPTIONS,
    OPTIONS_ARM,
    SIGNAL_PANEL_MESSAGE,
)
from .entity import AlarmDecoderEntity

SERVICE_ALARM_TOGGLE_CHIME = "alarm_toggle_chime"

SERVICE_ALARM_KEYPRESS = "alarm_keypress"
ATTR_KEYPRESS = "keypress"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmDecoderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up for AlarmDecoder alarm panels."""
    options = entry.options
    arm_options = options.get(OPTIONS_ARM, DEFAULT_ARM_OPTIONS)

    entity = AlarmDecoderAlarmPanel(
        client=entry.runtime_data.client,
        auto_bypass=arm_options[CONF_AUTO_BYPASS],
        code_arm_required=arm_options[CONF_CODE_ARM_REQUIRED],
        alt_night_mode=arm_options[CONF_ALT_NIGHT_MODE],
    )
    async_add_entities([entity])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_ALARM_TOGGLE_CHIME,
        {
            vol.Required(ATTR_CODE): cv.string,
        },
        "alarm_toggle_chime",
    )

    platform.async_register_entity_service(
        SERVICE_ALARM_KEYPRESS,
        {
            vol.Required(ATTR_KEYPRESS): cv.string,
        },
        "alarm_keypress",
    )


class AlarmDecoderAlarmPanel(AlarmDecoderEntity, AlarmControlPanelEntity):
    """Representation of an AlarmDecoder-based alarm panel."""

    _attr_name = "Alarm Panel"
    _attr_should_poll = False
    _attr_code_format = CodeFormat.NUMBER
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def __init__(self, client, auto_bypass, code_arm_required, alt_night_mode):
        """Initialize the alarm panel."""
        super().__init__(client)
        self._attr_unique_id = f"{client.serial_number}-panel"
        self._auto_bypass = auto_bypass
        self._attr_code_arm_required = code_arm_required
        self._alt_night_mode = alt_night_mode

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PANEL_MESSAGE, self._message_callback
            )
        )

    def _message_callback(self, message):
        """Handle received messages."""
        if message.alarm_sounding or message.fire_alarm:
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
        elif message.armed_away:
            self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
        elif message.armed_home and (message.entry_delay_off or message.perimeter_only):
            self._attr_alarm_state = AlarmControlPanelState.ARMED_NIGHT
        elif message.armed_home:
            self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        else:
            self._attr_alarm_state = AlarmControlPanelState.DISARMED

        self._attr_extra_state_attributes = {
            "ac_power": message.ac_power,
            "alarm_event_occurred": message.alarm_event_occurred,
            "backlight_on": message.backlight_on,
            "battery_low": message.battery_low,
            "check_zone": message.check_zone,
            "chime": message.chime_on,
            "entry_delay_off": message.entry_delay_off,
            "programming_mode": message.programming_mode,
            "ready": message.ready,
            "zone_bypassed": message.zone_bypassed,
        }
        self.schedule_update_ha_state()

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if code:
            self._client.send(f"{code!s}1")

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._client.arm_away(
            code=code,
            code_arm_required=self._attr_code_arm_required,
            auto_bypass=self._auto_bypass,
        )

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._client.arm_home(
            code=code,
            code_arm_required=self._attr_code_arm_required,
            auto_bypass=self._auto_bypass,
        )

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        self._client.arm_night(
            code=code,
            code_arm_required=self._attr_code_arm_required,
            alt_night_mode=self._alt_night_mode,
            auto_bypass=self._auto_bypass,
        )

    def alarm_toggle_chime(self, code=None):
        """Send toggle chime command."""
        if code:
            self._client.send(f"{code!s}9")

    def alarm_keypress(self, keypress):
        """Send custom keypresses."""
        if keypress:
            self._client.send(keypress)
