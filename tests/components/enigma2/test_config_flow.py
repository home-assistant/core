"""Test the Enigma2 config flow."""

from typing import Any
from unittest.mock import AsyncMock

from aiohttp.client_exceptions import ClientError
from openwebif.error import InvalidAuthError
import pytest

from homeassistant.components.enigma2.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_FULL, TEST_REQUIRED

from tests.common import MockConfigEntry


@pytest.fixture
async def user_flow(hass: HomeAssistant) -> str:
    """Return a user-initiated flow after filling in host info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    return result["flow_id"]


@pytest.mark.usefixtures("openwebif_device_mock")
@pytest.mark.parametrize(
    ("test_config"),
    [(TEST_FULL), (TEST_REQUIRED)],
)
async def test_form_user(hass: HomeAssistant, test_config: dict[str, Any]) -> None:
    """Test a successful user initiated flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], test_config
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == test_config[CONF_HOST]
    assert result["data"] == test_config


@pytest.mark.parametrize(
    ("side_effect", "error_value"),
    [
        (InvalidAuthError, "invalid_auth"),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_user_errors(
    hass: HomeAssistant,
    openwebif_device_mock: AsyncMock,
    side_effect: Exception,
    error_value: str,
) -> None:
    """Test we handle errors."""

    openwebif_device_mock.get_about.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_FULL
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": error_value}

    openwebif_device_mock.get_about.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_FULL,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_FULL[CONF_HOST]
    assert result["data"] == TEST_FULL
    assert result["result"].unique_id == openwebif_device_mock.mac_address


@pytest.mark.usefixtures("openwebif_device_mock")
async def test_duplicate_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a duplicate host aborts the config flow."""
    mock_config_entry.add_to_hass(hass)

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], TEST_FULL
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.usefixtures("openwebif_device_mock")
async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the form options."""

    entry = MockConfigEntry(domain=DOMAIN, data=TEST_FULL, options={}, entry_id="1")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"source_bouquet": "Favourites (TV)"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"source_bouquet": "Favourites (TV)"}

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
