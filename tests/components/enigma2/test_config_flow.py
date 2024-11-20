"""Test the Enigma2 config flow."""

from typing import Any
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
from openwebif.error import InvalidAuthError
import pytest

from homeassistant import config_entries
from homeassistant.components.enigma2.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_FULL, TEST_REQUIRED, MockDevice

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
    hass: HomeAssistant, user_flow: str, test_config: dict[str, Any]
) -> None:
    """Test a successful user initiated flow."""
    with (
        patch(
            "openwebif.api.OpenWebIfDevice.__new__",
            return_value=MockDevice(),
        ),
        patch(
            "homeassistant.components.enigma2.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, test_config)
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == test_config[CONF_HOST]
    assert result["data"] == test_config

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (InvalidAuthError, "invalid_auth"),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_user_errors(
    hass: HomeAssistant, user_flow, exception: Exception, error_type: str
) -> None:
    """Test we handle errors."""
    with patch(
        "homeassistant.components.enigma2.config_flow.OpenWebIfDevice.__new__",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_FULL)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER
    assert result["errors"] == {"base": error_type}


async def test_options_flow(hass: HomeAssistant, user_flow: str) -> None:
    """Test the form options."""

    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ):
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
