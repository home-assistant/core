"""Test the La Marzocco config flow."""
from unittest.mock import patch

from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant import config_entries
from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DEFAULT_CONF,
    LM_SERVICE_INFO,
    LOGIN_INFO,
    MACHINE_NAME,
    UNIQUE_ID,
    USER_INPUT,
    WRONG_LOGIN_INFO,
)

from tests.common import MockConfigEntry


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
        "homeassistant.components.lamarzocco.LaMarzoccoClient.try_connect",
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
    assert len(mock_setup_entry.mock_calls) == 1


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


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test bluetooth discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=LM_SERVICE_INFO,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_show_reauth(hass: HomeAssistant) -> None:
    """Test that the reauth form shows."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_CONF | USER_INPUT,
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test that the reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_CONF | USER_INPUT,
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "homeassistant.components.lamarzocco.LaMarzoccoClient.try_connect",
        return_value=_mock_lamarzocco_get_machine_info_success(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            LOGIN_INFO,
        )

    assert result2["type"] == FlowResultType.ABORT
    await hass.async_block_till_done()
    assert result2["reason"] == "reauth_successful"


async def test_reauth_errors(hass: HomeAssistant) -> None:
    """Test the reauth flow errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_CONF | USER_INPUT,
        unique_id=UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "homeassistant.components.lamarzocco.LaMarzoccoClient.try_connect",
        side_effect=AuthFail(""),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            WRONG_LOGIN_INFO,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.lamarzocco.LaMarzoccoClient.try_connect",
        side_effect=RequestNotSuccessful(""),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            LOGIN_INFO,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
