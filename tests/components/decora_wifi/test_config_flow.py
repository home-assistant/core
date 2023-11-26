"""Test the decora_wifi config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.decora_wifi.config_flow import CannotConnect
from homeassistant.components.decora_wifi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]
    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "bad-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "bad-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that it disallows creating w/ same "username."""
    CONFIG = {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test-username", data=CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        return_value=True,
    ):
        await entry.async_setup(hass)
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=CONFIG
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


# async def test_async_step_import_success(hass: HomeAssistant) -> None:
#     """Test import step success."""
#     with patch("pyvera.VeraController") as vera_controller_class_mock:
#         controller = MagicMock()
#         controller.refresh_data = MagicMock()
#         controller.serial_number = "serial_number_1"
#         vera_controller_class_mock.return_value = controller

#         result = await hass.config_entries.flow.async_init(
#             DOMAIN,
#             context={"source": config_entries.SOURCE_IMPORT},
#             data={CONF_CONTROLLER: "http://127.0.0.1:123/"},
#         )

#         assert result["type"] == FlowResultType.CREATE_ENTRY
#         assert result["title"] == "http://127.0.0.1:123"
#         assert result["data"] == {
#             CONF_CONTROLLER: "http://127.0.0.1:123",
#             CONF_SOURCE: config_entries.SOURCE_IMPORT,
#             CONF_LEGACY_UNIQUE_ID: False,
#         }
#         assert result["result"].unique_id == controller.serial_number
