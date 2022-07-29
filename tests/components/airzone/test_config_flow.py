"""Define tests for the Airzone config flow."""

from unittest.mock import patch

from aioairzone.const import API_SYSTEMS
from aioairzone.exceptions import (
    AirzoneError,
    InvalidMethod,
    InvalidSystem,
    SystemOutOfRange,
)

from homeassistant import data_entry_flow
from homeassistant.components.airzone.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT
from homeassistant.core import HomeAssistant

from .util import CONFIG, CONFIG_ID1, HVAC_MOCK, HVAC_WEBSERVER_MOCK

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
        side_effect=SystemOutOfRange,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
        return_value=HVAC_WEBSERVER_MOCK,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.LOADED

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Airzone {CONFIG[CONF_HOST]}:{CONFIG[CONF_PORT]}"
        assert result["data"][CONF_HOST] == CONFIG[CONF_HOST]
        assert result["data"][CONF_PORT] == CONFIG[CONF_PORT]
        assert CONF_ID not in result["data"]

        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_system_id(hass: HomeAssistant) -> None:
    """Test Invalid System ID 0."""

    with patch(
        "homeassistant.components.airzone.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        side_effect=InvalidSystem,
    ) as mock_hvac, patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
        side_effect=SystemOutOfRange,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
        side_effect=InvalidMethod,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {CONF_ID: "invalid_system_id"}

        mock_hvac.return_value = HVAC_MOCK[API_SYSTEMS][0]
        mock_hvac.side_effect = None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_ID1
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.LOADED

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert (
            result["title"]
            == f"Airzone {CONFIG_ID1[CONF_HOST]}:{CONFIG_ID1[CONF_PORT]}"
        )
        assert result["data"][CONF_HOST] == CONFIG_ID1[CONF_HOST]
        assert result["data"][CONF_PORT] == CONFIG_ID1[CONF_PORT]
        assert result["data"][CONF_ID] == CONFIG_ID1[CONF_ID]

        mock_setup_entry.assert_called_once()


async def test_form_duplicated_id(hass: HomeAssistant) -> None:
    """Test setting up duplicated entry."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
        unique_id="airzone_unique_id",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_connection_error(hass: HomeAssistant):
    """Test connection to host error."""

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.validate",
        side_effect=AirzoneError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "cannot_connect"}
