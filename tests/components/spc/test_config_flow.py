"""Test the SPC config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.spc.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (ClientError(), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (Exception(), "cannot_connect"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant, mock_client: AsyncMock, side_effect: Exception, error_key: str
) -> None:
    """Test we handle errors."""
    mock_client.return_value.async_load_parameters.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_CONFIG
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": error_key}


async def test_form(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.spc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "SPC4000 - 111111"
    assert result2["data"] == TEST_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test we handle invalid auth."""
    client = mock_client.return_value
    client.async_load_parameters.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG,
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test we handle cannot connect error."""

    client = mock_client.return_value
    client.async_load_parameters.side_effect = ClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONFIG,
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_flow_user_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test user initialized flow with duplicate server."""

    config = {
        "api_url": "http://example.com/api",
        "ws_url": "ws://example.com/ws",
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        unique_id=config["api_url"],
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_flow_import(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test user initialized flow."""
    config = {
        "api_url": "http://example.com/api",
        "ws_url": "ws://example.com/ws",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=config,
        context={"source": config_entries.SOURCE_IMPORT},
    )

    assert result["type"] == "create_entry"
    assert result["data"] == config


async def test_flow_import_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test user initialized flow with duplicate server."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
        unique_id=TEST_CONFIG["api_url"],
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=TEST_CONFIG,
        context={"source": config_entries.SOURCE_IMPORT},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_flow_import_cannot_connect(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test user initialized flow with duplicate server."""

    client = mock_client.return_value
    client.async_load_parameters.side_effect = ClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=TEST_CONFIG,
        context={"source": config_entries.SOURCE_IMPORT},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"
