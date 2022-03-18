"""Tests for the Google Assistant integration."""
from unittest.mock import MagicMock

from homeassistant.components.google_assistant import helpers


def mock_google_config_store(agent_user_ids=None):
    """Fake a storage for google assistant."""
    store = MagicMock(spec=helpers.GoogleConfigStore)
    if agent_user_ids is not None:
        store.agent_user_ids = agent_user_ids
    else:
        store.agent_user_ids = {}
    return store


class MockConfig(helpers.AbstractConfig):
    """Fake config that always exposes everything."""

    def __init__(
        self,
        *,
        agent_user_ids=None,
        enabled=True,
        entity_config=None,
        hass=None,
        secure_devices_pin=None,
        should_2fa=None,
        should_expose=None,
        should_report_state=False,
    ):
        """Initialize config."""
        super().__init__(hass)
        self._enabled = enabled
        self._entity_config = entity_config or {}
        self._secure_devices_pin = secure_devices_pin
        self._should_2fa = should_2fa
        self._should_expose = should_expose
        self._should_report_state = should_report_state
        self._store = mock_google_config_store(agent_user_ids)

    @property
    def enabled(self):
        """Return if Google is enabled."""
        return self._enabled

    @property
    def secure_devices_pin(self):
        """Return secure devices pin."""
        return self._secure_devices_pin

    @property
    def entity_config(self):
        """Return secure devices pin."""
        return self._entity_config

    def get_agent_user_id(self, context):
        """Get agent user ID making request."""
        return context.user_id

    def should_expose(self, state):
        """Expose it all."""
        return self._should_expose is None or self._should_expose(state)

    @property
    def should_report_state(self):
        """Return if states should be proactively reported."""
        return self._should_report_state

    def should_2fa(self, state):
        """Expose it all."""
        return self._should_2fa is None or self._should_2fa(state)


BASIC_CONFIG = MockConfig()

DEMO_DEVICES = [
    {
        "id": "light.kitchen_lights",
        "name": {"name": "Kitchen Lights"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Brightness",
            "action.devices.traits.ColorSetting",
        ],
        "type": "action.devices.types.LIGHT",
        "willReportState": False,
    },
    {
        "id": "switch.ac",
        "name": {"name": "AC"},
        "traits": ["action.devices.traits.OnOff"],
        "type": "action.devices.types.OUTLET",
        "willReportState": False,
    },
    {
        "id": "switch.decorative_lights",
        "name": {"name": "Decorative Lights"},
        "traits": ["action.devices.traits.OnOff"],
        "type": "action.devices.types.SWITCH",
        "willReportState": False,
    },
    {
        "id": "light.ceiling_lights",
        "name": {
            "name": "Roof Lights",
            "nicknames": ["Roof Lights", "top lights", "ceiling lights"],
        },
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Brightness",
            "action.devices.traits.ColorSetting",
        ],
        "type": "action.devices.types.LIGHT",
        "willReportState": False,
    },
    {
        "id": "light.bed_light",
        "name": {"name": "Bed Light"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Brightness",
            "action.devices.traits.ColorSetting",
            "action.devices.traits.Modes",
        ],
        "type": "action.devices.types.LIGHT",
        "willReportState": False,
    },
    {
        "id": "cover.living_room_window",
        "name": {"name": "Living Room Window"},
        "traits": [
            "action.devices.traits.StartStop",
            "action.devices.traits.OpenClose",
        ],
        "type": "action.devices.types.BLINDS",
        "willReportState": False,
    },
    {
        "id": "cover.pergola_roof",
        "name": {"name": "Pergola Roof"},
        "traits": [
            "action.devices.traits.OpenClose",
        ],
        "type": "action.devices.types.BLINDS",
        "willReportState": False,
    },
    {
        "id": "cover.hall_window",
        "name": {"name": "Hall Window"},
        "traits": [
            "action.devices.traits.StartStop",
            "action.devices.traits.OpenClose",
        ],
        "type": "action.devices.types.BLINDS",
        "willReportState": False,
    },
    {
        "id": "cover.garage_door",
        "name": {"name": "Garage Door"},
        "traits": ["action.devices.traits.OpenClose"],
        "type": "action.devices.types.GARAGE",
        "willReportState": False,
    },
    {
        "id": "cover.kitchen_window",
        "name": {"name": "Kitchen Window"},
        "traits": [
            "action.devices.traits.StartStop",
            "action.devices.traits.OpenClose",
        ],
        "type": "action.devices.types.BLINDS",
        "willReportState": False,
    },
    {
        "id": "media_player.bedroom",
        "name": {"name": "Bedroom"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Volume",
            "action.devices.traits.Modes",
            "action.devices.traits.TransportControl",
            "action.devices.traits.MediaState",
        ],
        "type": "action.devices.types.SETTOP",
        "willReportState": False,
    },
    {
        "id": "media_player.kitchen",
        "name": {"name": "Kitchen"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Volume",
            "action.devices.traits.Modes",
            "action.devices.traits.TransportControl",
            "action.devices.traits.MediaState",
        ],
        "type": "action.devices.types.SETTOP",
        "willReportState": False,
    },
    {
        "id": "media_player.living_room",
        "name": {"name": "Living Room"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Volume",
            "action.devices.traits.Modes",
            "action.devices.traits.TransportControl",
            "action.devices.traits.MediaState",
        ],
        "type": "action.devices.types.SETTOP",
        "willReportState": False,
    },
    {
        "id": "media_player.lounge_room",
        "name": {"name": "Lounge room"},
        "traits": [
            "action.devices.traits.InputSelector",
            "action.devices.traits.OnOff",
            "action.devices.traits.Modes",
            "action.devices.traits.TransportControl",
            "action.devices.traits.MediaState",
        ],
        "type": "action.devices.types.SETTOP",
        "willReportState": False,
    },
    {
        "id": "media_player.walkman",
        "name": {"name": "Walkman"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Volume",
            "action.devices.traits.Modes",
            "action.devices.traits.TransportControl",
            "action.devices.traits.MediaState",
        ],
        "type": "action.devices.types.SETTOP",
        "willReportState": False,
    },
    {
        "id": "fan.living_room_fan",
        "name": {"name": "Living Room Fan"},
        "traits": [
            "action.devices.traits.FanSpeed",
            "action.devices.traits.OnOff",
        ],
        "type": "action.devices.types.FAN",
        "willReportState": False,
    },
    {
        "id": "fan.ceiling_fan",
        "name": {"name": "Ceiling Fan"},
        "traits": [
            "action.devices.traits.FanSpeed",
            "action.devices.traits.OnOff",
        ],
        "type": "action.devices.types.FAN",
        "willReportState": False,
    },
    {
        "id": "fan.percentage_full_fan",
        "name": {"name": "Percentage Full Fan"},
        "traits": ["action.devices.traits.FanSpeed", "action.devices.traits.OnOff"],
        "type": "action.devices.types.FAN",
        "willReportState": False,
    },
    {
        "id": "fan.percentage_limited_fan",
        "name": {"name": "Percentage Limited Fan"},
        "traits": ["action.devices.traits.FanSpeed", "action.devices.traits.OnOff"],
        "type": "action.devices.types.FAN",
        "willReportState": False,
    },
    {
        "id": "fan.preset_only_limited_fan",
        "name": {"name": "Preset Only Limited Fan"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Modes",
        ],
        "type": "action.devices.types.FAN",
        "willReportState": False,
    },
    {
        "id": "climate.hvac",
        "name": {"name": "Hvac"},
        "traits": [
            "action.devices.traits.TemperatureSetting",
            "action.devices.traits.FanSpeed",
        ],
        "type": "action.devices.types.THERMOSTAT",
        "willReportState": False,
        "attributes": {
            "availableThermostatModes": [
                "off",
                "heat",
                "cool",
                "heatcool",
                "auto",
                "dry",
                "fan-only",
            ],
            "thermostatTemperatureUnit": "C",
        },
    },
    {
        "id": "climate.heatpump",
        "name": {"name": "HeatPump"},
        "traits": ["action.devices.traits.TemperatureSetting"],
        "type": "action.devices.types.THERMOSTAT",
        "willReportState": False,
    },
    {
        "id": "climate.ecobee",
        "name": {"name": "Ecobee"},
        "traits": [
            "action.devices.traits.TemperatureSetting",
            "action.devices.traits.FanSpeed",
        ],
        "type": "action.devices.types.THERMOSTAT",
        "willReportState": False,
    },
    {
        "id": "humidifier.humidifier",
        "name": {"name": "Humidifier"},
        "traits": [
            "action.devices.traits.HumiditySetting",
            "action.devices.traits.OnOff",
        ],
        "type": "action.devices.types.HUMIDIFIER",
        "willReportState": False,
        "attributes": {"humiditySetpointRange": {"minPercent": 0, "maxPercent": 100}},
    },
    {
        "id": "humidifier.dehumidifier",
        "name": {"name": "Dehumidifier"},
        "traits": [
            "action.devices.traits.HumiditySetting",
            "action.devices.traits.OnOff",
        ],
        "type": "action.devices.types.DEHUMIDIFIER",
        "willReportState": False,
        "attributes": {"humiditySetpointRange": {"minPercent": 0, "maxPercent": 100}},
    },
    {
        "id": "humidifier.hygrostat",
        "name": {"name": "Hygrostat"},
        "traits": [
            "action.devices.traits.HumiditySetting",
            "action.devices.traits.Modes",
            "action.devices.traits.OnOff",
        ],
        "type": "action.devices.types.HUMIDIFIER",
        "willReportState": False,
        "attributes": {"humiditySetpointRange": {"minPercent": 0, "maxPercent": 100}},
    },
    {
        "id": "lock.front_door",
        "name": {"name": "Front Door"},
        "traits": ["action.devices.traits.LockUnlock"],
        "type": "action.devices.types.LOCK",
        "willReportState": False,
    },
    {
        "id": "lock.kitchen_door",
        "name": {"name": "Kitchen Door"},
        "traits": ["action.devices.traits.LockUnlock"],
        "type": "action.devices.types.LOCK",
        "willReportState": False,
    },
    {
        "id": "lock.openable_lock",
        "name": {"name": "Openable Lock"},
        "traits": ["action.devices.traits.LockUnlock"],
        "type": "action.devices.types.LOCK",
        "willReportState": False,
    },
    {
        "id": "lock.poorly_installed_door",
        "name": {"name": "Poorly Installed Door"},
        "traits": ["action.devices.traits.LockUnlock"],
        "type": "action.devices.types.LOCK",
        "willReportState": False,
    },
    {
        "id": "alarm_control_panel.security",
        "name": {"name": "Security"},
        "traits": ["action.devices.traits.ArmDisarm"],
        "type": "action.devices.types.SECURITYSYSTEM",
        "willReportState": False,
    },
    {
        "id": "light.living_room_rgbww_lights",
        "name": {"name": "Living Room RGBWW Lights"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Brightness",
            "action.devices.traits.ColorSetting",
        ],
        "type": "action.devices.types.LIGHT",
        "willReportState": False,
    },
    {
        "id": "light.office_rgbw_lights",
        "name": {"name": "Office RGBW Lights"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Brightness",
            "action.devices.traits.ColorSetting",
        ],
        "type": "action.devices.types.LIGHT",
        "willReportState": False,
    },
    {
        "id": "light.entrance_color_white_lights",
        "name": {"name": "Entrance Color + White Lights"},
        "traits": [
            "action.devices.traits.OnOff",
            "action.devices.traits.Brightness",
            "action.devices.traits.ColorSetting",
        ],
        "type": "action.devices.types.LIGHT",
        "willReportState": False,
    },
]
