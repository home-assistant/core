"""Test the A. O. Smith config flow."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from py_aosmith import AOSmithInvalidCredentialsException
import pytest

from homeassistant import config_entries
from homeassistant.components.aosmith.const import (
    DOMAIN,
    ENERGY_USAGE_INTERVAL,
    REGULAR_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import FIXTURE_USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        return_value=[],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == FIXTURE_USER_INPUT[CONF_EMAIL]
    assert result2["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "expected_error_key"),
    [
        (AOSmithInvalidCredentialsException("Invalid credentials"), "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_form_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error_key: str,
) -> None:
    """Test handling an exception and then recovering on the second attempt."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": expected_error_key}

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        return_value=[],
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == FIXTURE_USER_INPUT[CONF_EMAIL]
    assert result3["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("api_method", "wait_interval"),
    [
        ("get_devices", REGULAR_INTERVAL),
        ("get_energy_use_data", ENERGY_USAGE_INTERVAL),
    ],
)
async def test_reauth_flow(
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    api_method: str,
    wait_interval: timedelta,
) -> None:
    """Test reauth works."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    getattr(mock_client, api_method).side_effect = AOSmithInvalidCredentialsException(
        "Authentication error"
    )
    freezer.tick(wait_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_energy_use_data",
            return_value=[],
        ),
        patch("homeassistant.components.aosmith.async_setup_entry", return_value=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"],
            {CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD]},
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"


async def test_reauth_flow_retry(
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test reauth works with retry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    mock_client.get_devices.side_effect = AOSmithInvalidCredentialsException(
        "Authentication error"
    )
    freezer.tick(REGULAR_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    # First attempt at reauth - authentication fails again
    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        side_effect=AOSmithInvalidCredentialsException("Authentication error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"],
            {CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD]},
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}

    # Second attempt at reauth - authentication succeeds
    with (
        patch(
            "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
            return_value=[],
        ),
        patch("homeassistant.components.aosmith.async_setup_entry", return_value=True),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"],
            {CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD]},
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reauth_successful"
