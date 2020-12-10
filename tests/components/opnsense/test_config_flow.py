"""Tests for the OPNsense config flow."""
from pyopnsense.exceptions import APIException

from homeassistant import data_entry_flow
from homeassistant.components.opnsense.const import CONF_TRACKER_INTERFACE, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY

from . import CONFIG_DATA, CONFIG_DATA_IMPORT, TITLE, setup_mock_diagnostics

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_import(hass):
    """Test import step."""
    with patch(
        "homeassistant.components.opnsense.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.opnsense.config_flow.diagnostics"
    ) as mock_diagnostics:
        setup_mock_diagnostics(mock_diagnostics)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONFIG_DATA_IMPORT,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["result"].unique_id == CONFIG_DATA[CONF_API_KEY]
        assert result["title"] == TITLE

        assert len(mock_setup_entry.mock_calls) == 1


async def test_user(hass):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.opnsense.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.opnsense.config_flow.diagnostics"
    ) as mock_diagnostics:
        setup_mock_diagnostics(mock_diagnostics)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["result"].unique_id == CONFIG_DATA[CONF_API_KEY]
        assert result["title"] == TITLE

        assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_setup(hass):
    """Test we abort if component is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=CONFIG_DATA[CONF_API_KEY],
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=CONFIG_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_on_api_error(hass):
    """Test when we have errors connecting the router."""
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics.InterfaceClient.get_arp",
        side_effect=APIException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_on_invalid_interface(hass):
    """Test when we have invalid interface(s)."""
    config_data = CONFIG_DATA.copy()
    config_data[CONF_TRACKER_INTERFACE] = "WRONG"

    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics"
    ) as mock_diagnostics:
        setup_mock_diagnostics(mock_diagnostics)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=config_data,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_interface"}


async def test_on_unknown_error(hass):
    """Test when we have unknown errors."""
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics.InterfaceClient.get_arp",
        side_effect=TypeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}
