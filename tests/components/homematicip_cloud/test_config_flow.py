"""Tests for spencermaticIP Cloud config flow."""
from unittest.mock import patch

from spencerassistant import config_entries
from spencerassistant.components.spencermaticip_cloud.const import (
    DOMAIN as HMIPC_DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
    HMIPC_PIN,
)

from tests.common import MockConfigEntry

DEFAULT_CONFIG = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}

IMPORT_CONFIG = {HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "123", HMIPC_NAME: "hmip"}


async def test_flow_works(hass, simple_mock_spencer):
    """Test config flow."""

    with patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_checkbutton",
        return_value=False,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.get_auth",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "press_the_button"}

    flow = next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert flow["context"]["unique_id"] == "ABC123"

    with patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_checkbutton",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_setup",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_register",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipHAP.async_connect",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "ABC123"
    assert result["data"] == {"hapid": "ABC123", "authtoken": True, "name": "hmip"}
    assert result["result"].unique_id == "ABC123"


async def test_flow_init_connection_error(hass):
    """Test config flow with accesspoint connection error."""
    with patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_setup",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_flow_link_connection_error(hass):
    """Test config flow client registration connection error."""
    with patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_checkbutton",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_setup",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_register",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "connection_aborted"


async def test_flow_link_press_button(hass):
    """Test config flow ask for pressing the blue button."""
    with patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_checkbutton",
        return_value=False,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_setup",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "press_the_button"}


async def test_init_flow_show_form(hass):
    """Test config flow shows up with a form."""

    result = await hass.config_entries.flow.async_init(
        HMIPC_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_init_already_configured(hass):
    """Test accesspoint is already configured."""
    MockConfigEntry(domain=HMIPC_DOMAIN, unique_id="ABC123").add_to_hass(hass)
    with patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_checkbutton",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import_config(hass, simple_mock_spencer):
    """Test importing a host with an existing config file."""
    with patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_checkbutton",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_setup",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_register",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipHAP.async_connect",
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=IMPORT_CONFIG,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "ABC123"
    assert result["data"] == {"authtoken": "123", "hapid": "ABC123", "name": "hmip"}
    assert result["result"].unique_id == "ABC123"


async def test_import_existing_config(hass):
    """Test abort of an existing accesspoint from config."""
    MockConfigEntry(domain=HMIPC_DOMAIN, unique_id="ABC123").add_to_hass(hass)
    with patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_checkbutton",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_setup",
        return_value=True,
    ), patch(
        "spencerassistant.components.spencermaticip_cloud.hap.spencermaticipAuth.async_register",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=IMPORT_CONFIG,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
