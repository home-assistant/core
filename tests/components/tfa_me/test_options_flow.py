"""Test the TFA.me integration: test of config_flow (options flow).py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tfa_me.config_flow import OptionsFlowHandler
from homeassistant.components.tfa_me.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_options_flow_action_rain(
    hass: HomeAssistant, tfa_me_options_flow_mock_entry, tfa_me_mock_coordinator
) -> None:
    """Test the action_rain option in OptionsFlowHandler."""

    # Fake JSON reply from gateway
    fake_json = {"gateway_id": "012345678", "sensors": []}
    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeDataCoordinator._async_update_data",
        new=AsyncMock(return_value=fake_json),
    ):
        result = await hass.config_entries.async_setup(
            tfa_me_options_flow_mock_entry.entry_id
        )
        await hass.async_block_till_done()

    assert result is True
    assert tfa_me_options_flow_mock_entry.state == ConfigEntryState.LOADED

    # Update list and add coordinator to hass.data
    tfa_me_mock_coordinator.sensor_entity_list = [
        "sensor.017654321_a1fffffea_rain_1_hour"
    ]

    hass.data.setdefault(DOMAIN, {})[tfa_me_options_flow_mock_entry.entry_id] = (
        tfa_me_mock_coordinator
    )

    # Register dummy services in case of OptionsFlow calls it
    hass.services.async_register(
        "homeassistant", "reload_config_entry", lambda call: None
    )
    hass.services.async_register("homeassistant", "update_entity", lambda call: None)

    tfa_me_options_flow_mock_entry.runtime_data = tfa_me_mock_coordinator

    # Start OptionsFlow for action "action_rain" via HA API (not manually!)
    result = await hass.config_entries.options.async_init(
        tfa_me_options_flow_mock_entry.entry_id,
        context={"source": "user"},
        data={"action_rain": True},
    )

    # Assertions
    assert result["type"] == "create_entry"
    assert (
        tfa_me_mock_coordinator.data["sensor.017654321_a1fffffea_rain_1_hour"][
            "reset_rain"
        ]
        is True
    )


@pytest.mark.asyncio
async def test_options_flow_show_main_menu(hass: HomeAssistant) -> None:
    """Test that OptionsFlowHandler shows main options menu correctly."""

    flow = OptionsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input=None)
    assert result["step_id"] == "init"
