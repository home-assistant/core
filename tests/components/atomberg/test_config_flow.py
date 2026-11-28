"""Tests for the Atomberg config flow."""

from unittest.mock import AsyncMock

from ha_atomberg_integration import AtombergAuthError, AtombergConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.atomberg.const import (
    CONF_DEVICE_IDS,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import API_KEY, REFRESH_TOKEN

USER_INPUT = {CONF_API_KEY: API_KEY, CONF_REFRESH_TOKEN: REFRESH_TOKEN}


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Atomberg"
    assert result["data"] == {
        **USER_INPUT,
        CONF_DEVICE_IDS: ["a4cf12123456", "a4cf12abcdef"],
    }
    assert result["result"].unique_id == API_KEY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AtombergAuthError, "invalid_auth"),
        (AtombergConnectionError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_flow_errors_then_recovery(
    hass: HomeAssistant, mock_client: AsyncMock, exception: type[Exception], error: str
) -> None:
    """Test errors are shown and the flow can then succeed."""
    mock_client.async_get_devices.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.async_get_devices.side_effect = None
    mock_client.async_get_devices.return_value = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_duplicate_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same API key cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_account_after_api_key_rotation(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same account cannot be added again with a rotated API key."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "rotated-key", CONF_REFRESH_TOKEN: "rotated-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_duplicate_account_when_setup_never_completed(
    hass: HomeAssistant,
) -> None:
    """Test a rotated key is detected from the saved IDs, without registered devices."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "old-key",
            CONF_REFRESH_TOKEN: "old-token",
            CONF_DEVICE_IDS: ["a4cf12abcdef"],
        },
        unique_id="old-key",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "rotated-key", CONF_REFRESH_TOKEN: "rotated-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
