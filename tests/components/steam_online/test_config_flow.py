"""Test Steam config flow."""
from unittest.mock import patch

from steam.api import HTTPError, HTTPTimeoutError
from steam.user import ProfileNotFoundError

from homeassistant import data_entry_flow
from homeassistant.components.steam_online.const import CONF_ACCOUNTS, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    ACCOUNT_1,
    ACCOUNT_2,
    CONF_DATA,
    CONF_OPTIONS,
    CONF_OPTIONS_2,
    create_entry,
    patch_coordinator_interface,
    patch_interface,
)


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    with patch(
        "homeassistant.components.steam_online.async_setup_entry",
        return_value=True,
    ), patch_interface():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Steam"
        assert result["data"] == CONF_DATA
        assert result["options"] == CONF_OPTIONS
        assert result["result"].unique_id == ACCOUNT_1


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with patch_interface() as servicemock:
        servicemock.side_effect = HTTPTimeoutError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "cannot_connect"


async def test_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid authentication."""
    with patch_interface() as servicemock:
        servicemock.side_effect = HTTPError("403")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "invalid_auth"


async def test_flow_user_invalid_account(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid account ID."""
    with patch_interface() as servicemock:
        servicemock.side_effect = ProfileNotFoundError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "invalid_account"


async def test_flow_user_unknown(hass: HomeAssistant) -> None:
    """Test user initialized flow with unknown error."""
    with patch_interface() as servicemock:
        servicemock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "unknown"


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate account."""
    create_entry(hass)
    with patch_interface():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_reauth(hass: HomeAssistant) -> None:
    """Test reauth step."""
    entry = create_entry(hass)
    with patch_interface():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                CONF_SOURCE: SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
            data=CONF_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        new_conf = CONF_DATA | {CONF_API_KEY: "1234567890"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=new_conf,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data == new_conf


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = create_entry(hass)
    with patch_interface(), patch_coordinator_interface():
        await hass.config_entries.async_setup(entry.entry_id)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ACCOUNTS: [ACCOUNT_1, ACCOUNT_2]},
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == CONF_OPTIONS_2
    assert len(dr.async_get(hass).devices) == 2
    assert len(er.async_get(hass).entities) == 10

    with patch_interface(), patch_coordinator_interface():
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ACCOUNTS: [ACCOUNT_1, ACCOUNT_2]},
        )

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ACCOUNTS: [ACCOUNT_1]},
        )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == CONF_OPTIONS
    assert len(dr.async_get(hass).devices) == 1
    assert len(er.async_get(hass).entities) == 5


async def test_options_flow_unauthorized_or_timed_out(hass: HomeAssistant) -> None:
    """Test updating options when user's friends list is not public or connection timed out."""
    entry = create_entry(hass)
    with patch_interface() as servicemock:
        servicemock.side_effect = HTTPError
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"]["base"] == "problem"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ACCOUNTS: [ACCOUNT_1]},
        )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == CONF_OPTIONS
