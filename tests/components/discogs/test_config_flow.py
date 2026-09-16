"""Test Discogs config flow."""

from unittest.mock import MagicMock

import discogs_client
import pytest
import requests

from homeassistant.components.discogs.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_TOKEN, MOCK_USER_ID, MOCK_USERNAME

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_user_flow(
    hass: HomeAssistant, mock_discogs_client: MagicMock
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TOKEN: MOCK_TOKEN},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"] == {CONF_TOKEN: MOCK_TOKEN}
    assert result["result"].unique_id == str(MOCK_USER_ID)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (discogs_client.exceptions.HTTPError("Unauthorized", 401), "invalid_auth"),
        (discogs_client.exceptions.HTTPError("Rate Limited", 429), "cannot_connect"),
        (requests.ConnectionError("Connection refused"), "cannot_connect"),
        (requests.Timeout("Request timed out"), "cannot_connect"),
        (RuntimeError("Something went wrong"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors_then_success(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    error: Exception,
    message: str,
) -> None:
    """Test that errors can be recovered from."""
    mock_discogs_client.identity.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TOKEN: "bad_token"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == message

    mock_discogs_client.identity.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TOKEN: MOCK_TOKEN},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_already_configured(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test flow aborts when account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TOKEN: MOCK_TOKEN},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow(hass: HomeAssistant, mock_discogs_client: MagicMock) -> None:
    """Test YAML import creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_TOKEN: MOCK_TOKEN},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"] == {CONF_TOKEN: MOCK_TOKEN}
    assert result["result"].unique_id == str(MOCK_USER_ID)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_with_name(
    hass: HomeAssistant, mock_discogs_client: MagicMock
) -> None:
    """Test YAML import preserves custom name as entry title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_TOKEN: MOCK_TOKEN, "name": "My Vinyl"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Vinyl"
    assert result["data"] == {CONF_TOKEN: MOCK_TOKEN}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test YAML import aborts when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_TOKEN: MOCK_TOKEN},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
