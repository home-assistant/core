"""Define tests for the Airzone config flow."""

from unittest.mock import MagicMock, patch

from aiohttp.client_exceptions import ClientConnectorError, ClientResponseError

from homeassistant import data_entry_flow
from homeassistant.components.airzone.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .util import CONFIG, HVAC_MOCK

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form is served with valid input."""

    with patch(
        "homeassistant.components.airzone.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
        side_effect=ClientResponseError(MagicMock(), MagicMock()),
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
        side_effect=ClientResponseError(MagicMock(), MagicMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.LOADED

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == f"Airzone {CONFIG[CONF_HOST]}:{CONFIG[CONF_PORT]}"
        assert result["data"][CONF_HOST] == CONFIG[CONF_HOST]
        assert result["data"][CONF_PORT] == CONFIG[CONF_PORT]

        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicated_id(hass: HomeAssistant) -> None:
    """Test setting up duplicated entry."""

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_connection_error(hass: HomeAssistant):
    """Test connection to host error."""

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.validate_airzone",
        side_effect=ClientConnectorError(MagicMock(), MagicMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "cannot_connect"}
