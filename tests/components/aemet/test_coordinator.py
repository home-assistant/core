"""Define tests for the AEMET OpenData coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from aemet_opendata.exceptions import AemetError, AuthError
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components import aemet
from homeassistant.components.aemet.coordinator import WEATHER_UPDATE_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_API_KEY, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .util import async_init_integration, mock_api_call


async def test_coordinator_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test error on coordinator update."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await async_init_integration(hass)

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AemetError,
    ):
        freezer.tick(WEATHER_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("weather.aemet")
        assert state.state == STATE_UNAVAILABLE


async def test_coordinator_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an invalid API key on coordinator update starts a reauth flow."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    config_entry = await async_init_integration(hass)

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AuthError,
    ):
        freezer.tick(WEATHER_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("weather.aemet")
        assert state.state == STATE_UNAVAILABLE

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id

    with (
        patch(
            "homeassistant.components.aemet.config_flow.AEMET",
            return_value=MagicMock(select_coordinates=AsyncMock()),
        ),
        patch(
            "homeassistant.components.aemet.AEMET.api_call",
            side_effect=mock_api_call,
        ),
        patch(
            "homeassistant.components.aemet.async_setup_entry",
            wraps=aemet.async_setup_entry,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"],
            user_input={CONF_API_KEY: "new"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_KEY] == "new"
    assert config_entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_awaited_once()
