"""Test the BraviaTV select platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.components.braviatv.coordinator import SCAN_INTERVAL
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, mock_restore_cache

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

ENUM_SETTINGS = [
    {
        "target": "pictureMode",
        "currentValue": "vivid",
        "candidate": ["vivid", "standard", "cinema"],
        "isAvailable": True,
    },
    {
        "target": "colorSpace",
        "currentValue": "auto",
        "candidate": [{"value": "auto"}, {"value": "bt2020"}],
        "isAvailable": True,
    },
    # brightness is a numeric setting and belongs to the number platform
    {
        "target": "brightness",
        "currentValue": 50,
        "candidate": [{"min": 0, "max": 100, "step": 1}],
        "isAvailable": True,
    },
]


async def test_entities(hass: HomeAssistant) -> None:
    """Test that select entities are created and can be set."""

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
            return_value=ENUM_SETTINGS,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("select.bravia_tv_model_picture_mode")
        assert state is not None
        assert state.state == "vivid"
        assert state.attributes["options"] == ["vivid", "standard", "cinema"]

        state = hass.states.get("select.bravia_tv_model_color_space")
        assert state is not None
        assert state.state == "auto"
        assert state.attributes["options"] == ["auto", "bt2020"]

        # The numeric setting must not be exposed as a select entity
        assert hass.states.get("select.bravia_tv_model_brightness") is None


async def test_select_option(hass: HomeAssistant) -> None:
    """Test selecting an option sends the command to the TV."""

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
            return_value=ENUM_SETTINGS,
        ),
        patch("pybravia.BraviaClient.set_picture_setting") as mock_set_picture_setting,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        await hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": "select.bravia_tv_model_picture_mode",
                "option": "cinema",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_set_picture_setting.assert_called_once_with("pictureMode", "cinema")


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unavailable_when_picture_setting_is_not_available(
    hass: HomeAssistant,
) -> None:
    """Test that unavailable select settings are not usable while disabled."""

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

    unavailable_enum_settings = [
        {**ENUM_SETTINGS[0], "isAvailable": False},
        ENUM_SETTINGS[1],
    ]

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
            return_value=unavailable_enum_settings,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("select.bravia_tv_model_picture_mode")
        assert state is not None
        assert state.state == "unavailable"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_restore_option(
    hass: HomeAssistant,
) -> None:
    """Test that the last option is restored when no live data is available."""

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

    mock_restore_cache(
        hass,
        (State("select.bravia_tv_model_picture_mode", "cinema"),),
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
        # restored option must be used
        patch("pybravia.BraviaClient.get_picture_setting", return_value=[]),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("select.bravia_tv_model_picture_mode")
        assert state is not None
        assert state.state == "cinema"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unavailable_when_setting_is_not_reported_and_not_restored(
    hass: HomeAssistant,
) -> None:
    """Test that selects the TV does not report are unavailable without a restored option."""

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
        # The TV does not report hdrMode, and there is no restored option
        patch("pybravia.BraviaClient.get_picture_setting", return_value=[]),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("select.bravia_tv_model_hdr_mode")
        assert state is not None
        assert state.state == "unavailable"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_keeps_latest_option_when_setting_is_omitted_after_refresh(
    hass: HomeAssistant,
) -> None:
    """Test the fallback option tracks the latest reported setting, not startup restore."""

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

    mock_restore_cache(
        hass,
        (State("select.bravia_tv_model_picture_mode", "cinema"),),
    )

    mock_picture_setting = AsyncMock(return_value=ENUM_SETTINGS)

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
        patch("pybravia.BraviaClient.get_picture_setting", mock_picture_setting),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("select.bravia_tv_model_picture_mode")
        assert state is not None
        assert state.state == "vivid"
        assert state.attributes["options"] == ["vivid", "standard", "cinema"]

        # A later refresh omits the setting, so the entity must fall back to
        # the latest reported option and option list rather than the
        # startup-restored ones
        mock_picture_setting.return_value = []
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

        state = hass.states.get("select.bravia_tv_model_picture_mode")
        assert state is not None
        assert state.state == "vivid"
        assert state.attributes["options"] == ["vivid", "standard", "cinema"]
