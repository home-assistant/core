"""Tests for Transmission config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from transmission_rpc.error import (
    TransmissionAuthError,
    TransmissionConnectError,
    TransmissionError,
)

from homeassistant import config_entries
from homeassistant.components import transmission
from homeassistant.components.transmission.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG_DATA, setup_integration

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )

    assert len(mock_setup_entry.mock_calls) == 1
    assert result["title"] == "Transmission"
    assert result["data"] == MOCK_CONFIG_DATA
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_device_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting if the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    await hass.async_block_till_done()

    assert result["reason"] == "already_configured"
    assert result["type"] is FlowResultType.ABORT


async def test_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=transmission.DOMAIN,
        data=MOCK_CONFIG_DATA,
        options={"limit": 10, "order": "oldest_first"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.transmission.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"limit": 20}
    )

    assert result["data"]["limit"] == 20
    assert result["data"]["order"] == "oldest_first"
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_error_on_wrong_credentials(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
) -> None:
    """Test we handle invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_transmission_client.side_effect = TransmissionAuthError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "username": "invalid_auth",
        "password": "invalid_auth",
    }

    mock_transmission_client.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TransmissionError, "cannot_connect"),
        (TransmissionConnectError, "cannot_connect"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_transmission_client.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_transmission_client.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_success(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can reauth."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "username": "user",
        "name": "Transmission",
    }

    with patch(
        "homeassistant.components.transmission.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "password": "test-password",
            },
        )

    assert len(mock_setup_entry.mock_calls) == 1
    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.parametrize(
    ("exception", "field", "error"),
    [
        (TransmissionError, "base", "cannot_connect"),
        (TransmissionConnectError, "base", "cannot_connect"),
        (TransmissionAuthError, "password", "invalid_auth"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_transmission_client: AsyncMock,
    exception: Exception,
    field: str,
    error: str,
) -> None:
    """Test flow errors."""
    entry = MockConfigEntry(
        domain=transmission.DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "username": "user",
        "name": "Mock Title",
    }

    mock_transmission_client.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "password": "wrong-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error}

    mock_transmission_client.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "password": "correct-password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
