"""Test the Paperless-ngx integration."""

from pypaperless.exceptions import (
    InitializationError,
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_error_key"),
    [
        (PaperlessConnectionError(), ConfigEntryState.SETUP_RETRY, "cannot_connect"),
        (PaperlessInvalidTokenError(), ConfigEntryState.SETUP_ERROR, "invalid_api_key"),
        (
            PaperlessInactiveOrDeletedError(),
            ConfigEntryState.SETUP_ERROR,
            "user_inactive_or_deleted",
        ),
        (PaperlessForbiddenError(), ConfigEntryState.SETUP_ERROR, "forbidden"),
        (InitializationError(), ConfigEntryState.SETUP_ERROR, "cannot_connect"),
        (Exception("BOOM!"), ConfigEntryState.SETUP_ERROR, "unknown"),
    ],
)
async def test_setup_config_error_handling(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
    side_effect,
    expected_state,
    expected_error_key,
) -> None:
    """Test all initialization error paths during setup."""
    mock_client.initialize.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state == expected_state
    assert mock_config_entry.error_reason_translation_key == expected_error_key


async def test_full_reauth_flow_config(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the re-auth flow."""
    mock_config_entry.add_to_hass(hass)

    result_init = await mock_config_entry.start_reauth_flow(hass)
    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "reauth_confirm"

    result_configure = await hass.config_entries.flow.async_configure(
        result_init["flow_id"],
        {
            CONF_HOST: mock_config_entry.data[CONF_HOST],
            CONF_API_KEY: "12345678",
            CONF_SCAN_INTERVAL: mock_config_entry.data[CONF_SCAN_INTERVAL],
        },
    )
    await hass.async_block_till_done()

    assert result_configure["type"] is FlowResultType.ABORT
    assert result_configure["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (PaperlessConnectionError(), {CONF_HOST: "cannot_connect"}),
        (PaperlessInvalidTokenError(), {CONF_API_KEY: "invalid_api_key"}),
        (PaperlessInactiveOrDeletedError(), {CONF_API_KEY: "user_inactive_or_deleted"}),
        (PaperlessForbiddenError(), {CONF_API_KEY: "forbidden"}),
        (InitializationError(), {CONF_HOST: "cannot_connect"}),
        (Exception("BOOM!"), {"base": "unknown"}),
    ],
)
async def test_reauth_flow_error_handling(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
    side_effect,
    expected_error,
) -> None:
    """Test reauth flow with various initialization errors."""
    mock_config_entry.add_to_hass(hass)
    mock_client.initialize.side_effect = side_effect

    result_init = await mock_config_entry.start_reauth_flow(hass)
    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "reauth_confirm"

    result_configure = await hass.config_entries.flow.async_configure(
        result_init["flow_id"],
        {
            CONF_HOST: mock_config_entry.data[CONF_HOST],
            CONF_API_KEY: "new-api-key",
            CONF_SCAN_INTERVAL: mock_config_entry.data[CONF_SCAN_INTERVAL],
        },
    )
    await hass.async_block_till_done()

    assert result_configure["type"] is FlowResultType.FORM
    assert result_configure["errors"] == expected_error

    assert len(hass.config_entries.async_entries()) == 1
