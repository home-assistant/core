"""Tests for Transmission config flow."""

from unittest.mock import MagicMock, patch

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

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock an api."""
    with patch("transmission_rpc.Client") as api:
        yield api


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.transmission.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG_DATA,
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    assert result["title"] == "Transmission"
    assert result["data"] == MOCK_CONFIG_DATA
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_device_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test aborting if the device is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

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


async def test_options(hass: HomeAssistant) -> None:
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
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test we handle invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.side_effect = TransmissionAuthError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "username": "invalid_auth",
        "password": "invalid_auth",
    }

    mock_api.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TransmissionError, "cannot_connect"),
        (TransmissionConnectError, "invalid_auth"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_api: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_api.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(domain=transmission.DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "username": "user",
        "name": "Mock Title",
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
    mock_api: MagicMock,
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

    mock_api.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "password": "wrong-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error}

    mock_api.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "password": "correct-password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
