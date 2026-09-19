"""Test the BraviaTV number platform."""

from unittest.mock import patch

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data

BRAVIA_SYSTEM_INFO = {
    "product": "TV",
    "region": "XEU",
    "language": "pol",
    "model": "TV-Model",
    "serial": "serial_number",
    "macAddr": "AA:BB:CC:DD:EE:FF",
    "name": "BRAVIA",
    "generation": "5.2.0",
    "area": "POL",
    "cid": "very_unique_string",
}

INPUTS = [
    {
        "uri": "extInput:hdmi?port=1",
        "title": "HDMI 1",
        "connection": False,
        "label": "",
        "icon": "meta:hdmi",
    }
]

NUMERIC_SETTINGS = [
    {
        "target": "brightness",
        "currentValue": 50,
        "candidate": [{"min": 0, "max": 100, "step": 1}],
        "isAvailable": True,
    },
    {
        "target": "hue",
        "currentValue": 10,
        "candidate": [{"min": -50, "max": 50, "step": 1}],
        "isAvailable": True,
    },
    # pictureMode is an enum and belongs to the select platform
    {
        "target": "pictureMode",
        "currentValue": "vivid",
        "candidate": ["vivid", "standard", "cinema"],
        "isAvailable": True,
    },
]


async def test_entities(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test that number entities are created and can be set."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch("pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO),
        patch("pybravia.BraviaClient.get_power_status", return_value="active"),
        patch("pybravia.BraviaClient.get_external_status", return_value=INPUTS),
        patch("pybravia.BraviaClient.get_volume_info", return_value={}),
        patch("pybravia.BraviaClient.get_playing_info", return_value={}),
        patch("pybravia.BraviaClient.get_app_list", return_value=[]),
        patch("pybravia.BraviaClient.get_content_list_all", return_value=[]),
        patch(
            "pybravia.BraviaClient.get_picture_setting",
            return_value=NUMERIC_SETTINGS,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("number.bravia_tv_model_picture_brightness")
        assert state is not None
        assert state.state == "50.0"
        assert state.attributes["min"] == 0
        assert state.attributes["max"] == 100
        assert state.attributes["step"] == 1

        state = hass.states.get("number.bravia_tv_model_picture_hue")
        assert state is not None
        assert state.state == "10.0"
        assert state.attributes["min"] == -50
        assert state.attributes["max"] == 50

        # The enum setting must not be exposed as a number entity
        assert hass.states.get("number.bravia_tv_model_picture_mode") is None


async def test_set_value(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test setting a number value sends the command to the TV."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch("pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO),
        patch("pybravia.BraviaClient.get_power_status", return_value="active"),
        patch("pybravia.BraviaClient.get_external_status", return_value=INPUTS),
        patch("pybravia.BraviaClient.get_volume_info", return_value={}),
        patch("pybravia.BraviaClient.get_playing_info", return_value={}),
        patch("pybravia.BraviaClient.get_app_list", return_value=[]),
        patch("pybravia.BraviaClient.get_content_list_all", return_value=[]),
        patch(
            "pybravia.BraviaClient.get_picture_setting",
            return_value=NUMERIC_SETTINGS,
        ),
        patch("pybravia.BraviaClient.set_picture_setting") as mock_set_picture_setting,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.bravia_tv_model_picture_brightness", "value": 75},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_set_picture_setting.assert_called_once_with("brightness", "75")


async def test_restore_value_when_tv_is_off(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test that the last value is restored when the TV is off at startup."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string",
    )
    config_entry.add_to_hass(hass)

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State("number.bravia_tv_model_picture_brightness", "42.0"),
                {
                    "native_max_value": 100.0,
                    "native_min_value": 0.0,
                    "native_step": 1.0,
                    "native_unit_of_measurement": None,
                    "native_value": 42.0,
                },
            ),
        ),
    )

    with (
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch("pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO),
        patch("pybravia.BraviaClient.get_power_status", return_value="active"),
        patch("pybravia.BraviaClient.get_external_status", return_value=INPUTS),
        patch("pybravia.BraviaClient.get_volume_info", return_value={}),
        patch("pybravia.BraviaClient.get_playing_info", return_value={}),
        patch("pybravia.BraviaClient.get_app_list", return_value=[]),
        patch("pybravia.BraviaClient.get_content_list_all", return_value=[]),
        # The TV is on but does not report the picture setting, so the
        # restored value must be used
        patch("pybravia.BraviaClient.get_picture_setting", return_value=[]),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("number.bravia_tv_model_picture_brightness")
        assert state is not None
        assert state.state == "42.0"
        assert state.attributes["min"] == 0
        assert state.attributes["max"] == 100
        assert state.attributes["step"] == 1
