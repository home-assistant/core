"""Test the BraviaTV number platform."""

from unittest.mock import AsyncMock, patch

import pytest

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


FRACTIONAL_STEP_SETTINGS = [
    {
        "target": "brightness",
        "currentValue": 1.5,
        "candidate": [{"min": 0, "max": 100, "step": 0.5}],
        "isAvailable": True,
    },
]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_entities(
    hass: HomeAssistant,
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


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_set_value(
    hass: HomeAssistant,
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


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unavailable_when_picture_setting_is_not_available(
    hass: HomeAssistant,
) -> None:
    """Test that unavailable picture settings are not exposed as usable controls."""

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

    unavailable_numeric_settings = [
        {**NUMERIC_SETTINGS[0], "isAvailable": False},
        NUMERIC_SETTINGS[1],
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
            return_value=unavailable_numeric_settings,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("number.bravia_tv_model_picture_brightness")
        assert state is not None
        assert state.state == "unavailable"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_restore_value_when_active_tv_omits_setting(
    hass: HomeAssistant,
) -> None:
    """Test that the last value is restored when an active TV omits the setting."""

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


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unavailable_when_setting_is_not_reported_and_not_restored(
    hass: HomeAssistant,
) -> None:
    """Test that numbers the TV does not report are unavailable without a restored value."""

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
        # The TV does not report contrast, and there is no restored value
        patch("pybravia.BraviaClient.get_picture_setting", return_value=[]),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        state = hass.states.get("number.bravia_tv_model_picture_contrast")
        assert state is not None
        assert state.state == "unavailable"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_keeps_latest_value_when_setting_is_omitted_after_refresh(
    hass: HomeAssistant,
) -> None:
    """Test the fallback value tracks the latest reported setting, not startup restore."""

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

    restored = {
        "native_max_value": 100.0,
        "native_min_value": 0.0,
        "native_step": 1.0,
        "native_unit_of_measurement": None,
        "native_value": 42.0,
    }
    mock_restore_cache_with_extra_data(
        hass,
        ((State("number.bravia_tv_model_picture_brightness", "42.0"), restored),),
    )

    mock_picture_setting = AsyncMock(return_value=NUMERIC_SETTINGS)

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

        state = hass.states.get("number.bravia_tv_model_picture_brightness")
        assert state is not None
        assert state.state == "50.0"
        assert state.attributes["min"] == 0
        assert state.attributes["max"] == 100
        assert state.attributes["step"] == 1

        mock_picture_setting.return_value = []
        await config_entry.runtime_data.picture_coordinator.async_refresh()

        state = hass.states.get("number.bravia_tv_model_picture_brightness")
        assert state is not None
        assert state.state == "50.0"
        assert state.attributes["min"] == 0
        assert state.attributes["max"] == 100
        assert state.attributes["step"] == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_set_fractional_value(
    hass: HomeAssistant,
) -> None:
    """Test that fractional values allowed by the reported step are sent as is."""

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
            return_value=FRACTIONAL_STEP_SETTINGS,
        ),
        patch("pybravia.BraviaClient.set_picture_setting") as mock_set_picture_setting,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.bravia_tv_model_picture_brightness", "value": 1.5},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_set_picture_setting.assert_called_once_with("brightness", "1.5")
