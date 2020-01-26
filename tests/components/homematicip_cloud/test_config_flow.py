"""Tests for HomematicIP Cloud config flow."""
from asynctest import patch

from homeassistant.components.homematicip_cloud import const

from tests.common import MockConfigEntry


async def test_flow_works(hass):
    """Test config flow."""
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": "user"}, data=config
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "press_the_button"}

    flow = next(
        (
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
    )
    assert flow["context"]["unique_id"] == "ABC123"

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_register",
        return_value=True,
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
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": "user"}, data=config
        )

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_flow_link_connection_error(hass):
    """Test config flow client registration connection error."""
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_register",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": "user"}, data=config
        )

    assert result["type"] == "abort"
    assert result["reason"] == "connection_aborted"


async def test_flow_link_press_button(hass):
    """Test config flow ask for pressing the blue button."""
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
        return_value=False,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": "user"}, data=config
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "press_the_button"}


async def test_init_flow_show_form(hass):
    """Test config flow shows up with a form."""

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_init_already_configured(hass):
    """Test accesspoint is already configured."""
    MockConfigEntry(domain=const.DOMAIN, unique_id="ABC123").add_to_hass(hass)
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": "user"}, data=config
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import_config(hass):
    """Test importing a host with an existing config file."""
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_AUTHTOKEN: "123",
        const.HMIPC_NAME: "hmip",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_register",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": "import"}, data=config
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "ABC123"
    assert result["data"] == {"authtoken": "123", "hapid": "ABC123", "name": "hmip"}
    assert result["result"].unique_id == "ABC123"


async def test_import_existing_config(hass):
    """Test abort of an existing accesspoint from config."""
    MockConfigEntry(domain=const.DOMAIN, unique_id="ABC123").add_to_hass(hass)
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_AUTHTOKEN: "123",
        const.HMIPC_NAME: "hmip",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_checkbutton",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipAuth.async_register",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": "import"}, data=config
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
