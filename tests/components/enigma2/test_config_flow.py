"""Test the Enigma2 config flow."""

from typing import Any
from unittest.mock import AsyncMock

from aiohttp.client_exceptions import ClientError
from openwebif.error import InvalidAuthError
import pytest

from homeassistant import config_entries
from homeassistant.components.enigma2.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_FULL, TEST_REQUIRED

from tests.common import MockConfigEntry


@pytest.fixture
async def user_flow(hass: HomeAssistant) -> str:
    """Return a user-initiated flow after filling in host info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    return result["flow_id"]


@pytest.mark.parametrize(
    ("test_config"),
    [(TEST_FULL), (TEST_REQUIRED)],
)
async def test_form_user(
    hass: HomeAssistant, openwebifdevice_mock: AsyncMock, test_config: dict[str, Any]
) -> None:
    """Test a successful user initiated flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], test_config
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == test_config[CONF_HOST]
    assert result["data"] == test_config
    assert result["result"].unique_id == openwebifdevice_mock.return_value.mac_address


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
    openwebifdevice_mock: AsyncMock,
    side_effect: Exception,
    error_value: str,
) -> None:
    """Test we handle errors."""

    openwebifdevice_mock.return_value.get_about.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_FULL
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER
    assert result["errors"] == {"base": error_value}

    openwebifdevice_mock.return_value.get_about.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_FULL,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_FULL[CONF_HOST]
    assert result["data"] == TEST_FULL
    assert result["result"].unique_id == openwebifdevice_mock.return_value.mac_address


async def test_options_flow(
    hass: HomeAssistant, openwebifdevice_mock: AsyncMock
) -> None:
    """Test the form options."""

    entry = MockConfigEntry(domain=DOMAIN, data=TEST_FULL, options={}, entry_id="1")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"source_bouquet": "Favourites (TV)"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"source_bouquet": "Favourites (TV)"}

    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED
