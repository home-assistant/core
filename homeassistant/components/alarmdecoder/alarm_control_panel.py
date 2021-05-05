"""Support for AlarmDecoder-based alarm control panels (Honeywell/DSC)."""
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ALT_NIGHT_MODE,
    CONF_AUTO_BYPASS,
    CONF_CODE_ARM_REQUIRED,
    DATA_AD,
    DEFAULT_ARM_OPTIONS,
    DOMAIN,
    OPTIONS_ARM,
    SIGNAL_PANEL_MESSAGE,
)

SERVICE_ALARM_TOGGLE_CHIME = "alarm_toggle_chime"

SERVICE_ALARM_KEYPRESS = "alarm_keypress"
ATTR_KEYPRESS = "keypress"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up for AlarmDecoder alarm panels."""
    options = entry.options
    arm_options = options.get(OPTIONS_ARM, DEFAULT_ARM_OPTIONS)
    client = hass.data[DOMAIN][entry.entry_id][DATA_AD]

    entity = AlarmDecoderAlarmPanel(
        client=client,
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


class AlarmDecoderAlarmPanel(AlarmControlPanelEntity):
    """Representation of an AlarmDecoder-based alarm panel."""

    def __init__(self, client, auto_bypass, code_arm_required, alt_night_mode):
        """Initialize the alarm panel."""
        self._client = client
        self._display = ""
        self._name = "Alarm Panel"
        self._state = None
        self._ac_power = None
        self._alarm_event_occurred = None
        self._backlight_on = None
        self._battery_low = None
        self._check_zone = None
        self._chime = None
        self._entry_delay_off = None
        self._programming_mode = None
        self._ready = None
        self._zone_bypassed = None
        self._auto_bypass = auto_bypass
        self._code_arm_required = code_arm_required
        self._alt_night_mode = alt_night_mode

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_PANEL_MESSAGE, self._message_callback
            )
        )

    def _message_callback(self, message):
        """Handle received messages."""
        if message.alarm_sounding or message.fire_alarm:
            self._state = STATE_ALARM_TRIGGERED
        elif message.armed_away:
            self._state = STATE_ALARM_ARMED_AWAY
        elif message.armed_home and (message.entry_delay_off or message.perimeter_only):
            self._state = STATE_ALARM_ARMED_NIGHT
        elif message.armed_home:
            self._state = STATE_ALARM_ARMED_HOME
        else:
            self._state = STATE_ALARM_DISARMED

        self._ac_power = message.ac_power
        self._alarm_event_occurred = message.alarm_event_occurred
        self._backlight_on = message.backlight_on
        self._battery_low = message.battery_low
        self._check_zone = message.check_zone
        self._chime = message.chime_on
        self._entry_delay_off = message.entry_delay_off
        self._programming_mode = message.programming_mode
        self._ready = message.ready
        self._zone_bypassed = message.zone_bypassed

        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        return FORMAT_NUMBER

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._code_arm_required

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "ac_power": self._ac_power,
            "alarm_event_occurred": self._alarm_event_occurred,
            "backlight_on": self._backlight_on,
            "battery_low": self._battery_low,
            "check_zone": self._check_zone,
            "chime": self._chime,
            "entry_delay_off": self._entry_delay_off,
            "programming_mode": self._programming_mode,
            "ready": self._ready,
            "zone_bypassed": self._zone_bypassed,
            "code_arm_required": self._code_arm_required,
        }

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if code:
            self._client.send(f"{code!s}1")

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._client.arm_away(
            code=code,
            code_arm_required=self._code_arm_required,
            auto_bypass=self._auto_bypass,
        )

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._client.arm_home(
            code=code,
            code_arm_required=self._code_arm_required,
            auto_bypass=self._auto_bypass,
        )

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self._client.arm_night(
            code=code,
            code_arm_required=self._code_arm_required,
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
