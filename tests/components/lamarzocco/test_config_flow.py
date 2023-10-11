"""Test the La Marzocco config flow."""
from unittest.mock import patch

from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant import config_entries
from homeassistant.components.lamarzocco.const import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_PORT_CLOUD,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MACHINE_NAME = "MyMachine"

DEFAULT_CONF = {
    "client_id": DEFAULT_CLIENT_ID,
    "client_secret": DEFAULT_CLIENT_SECRET,
    "machine_name": MACHINE_NAME,
    "port": DEFAULT_PORT_CLOUD,
    "title": MACHINE_NAME,
}

USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_HOST: "192.168.1.42",
}


def _mock_lamarzocco_get_machine_info_success():
    return {
        "machine_name": MACHINE_NAME,
    }


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lamarzocco.lm_client.LaMarzoccoClient._connect",
        return_value=None,
    ), patch(
        "homeassistant.components.lamarzocco.lm_client.LaMarzoccoClient._get_machine_info",
        return_value=_mock_lamarzocco_get_machine_info_success(),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result2["title"] == _mock_lamarzocco_get_machine_info_success()["machine_name"]
    )
    assert result2["data"] == USER_INPUT | DEFAULT_CONF
    assert len(mock_setup_entry.mock_calls) == 2


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth error."""
    with patch(
        "homeassistant.components.lamarzocco.lm_client.LaMarzoccoClient._connect",
        side_effect=AuthFail("Invalid auth"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test cannot connect error."""
    with patch(
        "homeassistant.components.lamarzocco.lm_client.LaMarzoccoClient._connect",
        side_effect=RequestNotSuccessful(""),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


# async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN,
#         context={"source": config_entries.SOURCE_BLUETOOTH},
#         data={"address": "11:22:33:44:55", "name": MACHINE_NAME},
#     )

#     assert result["type"] == FlowResultType.FORM
