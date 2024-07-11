"""Tests for HomematicIP Cloud config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.homematicip_cloud.const import (
    DOMAIN as HMIPC_DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
    HMIPC_PIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DEFAULT_CONFIG = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}

IMPORT_CONFIG = {HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "123", HMIPC_NAME: "hmip"}


async def test_flow_works(hass: HomeAssistant, simple_mock_home) -> None:
    """Test config flow."""

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
            return_value=False,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.get_auth",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "press_the_button"}

    flow = next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert flow["context"]["unique_id"] == "ABC123"

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_register",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipHAP.async_connect",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ABC123"
    assert result["data"] == {"hapid": "ABC123", "authtoken": True, "name": "hmip"}
    assert result["result"].unique_id == "ABC123"


async def test_flow_init_connection_error(hass: HomeAssistant) -> None:
    """Test config flow with accesspoint connection error."""
    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_flow_link_connection_error(hass: HomeAssistant) -> None:
    """Test config flow client registration connection error."""
    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_register",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "connection_aborted"


async def test_flow_link_press_button(hass: HomeAssistant) -> None:
    """Test config flow ask for pressing the blue button."""
    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
            return_value=False,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "press_the_button"}


async def test_init_flow_show_form(hass: HomeAssistant) -> None:
    """Test config flow shows up with a form."""

    result = await hass.config_entries.flow.async_init(
        HMIPC_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_init_already_configured(hass: HomeAssistant) -> None:
    """Test accesspoint is already configured."""
    MockConfigEntry(domain=HMIPC_DOMAIN, unique_id="ABC123").add_to_hass(hass)
    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=DEFAULT_CONFIG,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_config(hass: HomeAssistant, simple_mock_home) -> None:
    """Test importing a host with an existing config file."""
    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_register",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipHAP.async_connect",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=IMPORT_CONFIG,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ABC123"
    assert result["data"] == {"authtoken": "123", "hapid": "ABC123", "name": "hmip"}
    assert result["result"].unique_id == "ABC123"


async def test_import_existing_config(hass: HomeAssistant) -> None:
    """Test abort of an existing accesspoint from config."""
    MockConfigEntry(domain=HMIPC_DOMAIN, unique_id="ABC123").add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_register",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            HMIPC_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=IMPORT_CONFIG,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
