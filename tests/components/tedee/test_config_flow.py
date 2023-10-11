"""Test the Tedee config flow."""
from unittest.mock import patch

from pytedee_async import TedeeAuthException, TedeeLocalAuthException

from homeassistant import config_entries
from homeassistant.components.tedee.const import (
    CONF_HOME_ASSISTANT_ACCESS_TOKEN,
    CONF_LOCAL_ACCESS_TOKEN,
    CONF_UNLOCK_PULLS_LATCH,
    CONF_USE_CLOUD,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FLOW_UNIQUE_ID = "112233445566778899"
ACCESS_TOKEN = "api_token"
LOCAL_ACCESS_TOKEN = "api_token"


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_flow(hass: HomeAssistant) -> None:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.tedee.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.62",
                CONF_LOCAL_ACCESS_TOKEN: "token",
                CONF_USE_CLOUD: False,
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: "192.168.1.62",
        CONF_LOCAL_ACCESS_TOKEN: "token",
        CONF_USE_CLOUD: False,
    }

    with patch(
        "homeassistant.components.tedee.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.62",
                CONF_LOCAL_ACCESS_TOKEN: "token",
                CONF_USE_CLOUD: True,
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "configure_cloud"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {CONF_ACCESS_TOKEN: "token"}
        )

        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["data"] == {
            CONF_HOST: "192.168.1.62",
            CONF_LOCAL_ACCESS_TOKEN: "token",
            CONF_USE_CLOUD: True,
            CONF_ACCESS_TOKEN: "token",
        }


async def config_flow_errors(hass: HomeAssistant) -> None:
    """Test the config flow errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCAL_ACCESS_TOKEN: "token"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.42"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key"}

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=TedeeLocalAuthException("Invalid token"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.42",
                CONF_LOCAL_ACCESS_TOKEN: "wrong_token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key"}

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.x",
                CONF_LOCAL_ACCESS_TOKEN: "token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "invalid_host"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_CLOUD: True}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "configure_cloud"

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=TedeeAuthException("invalid_api_key"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ACCESS_TOKEN: "invalid_token",
            },
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {CONF_ACCESS_TOKEN: "invalid_api_key"}

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=Exception(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ACCESS_TOKEN: "token",
            },
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_show_reauth(hass: HomeAssistant) -> None:
    """Test that the reauth form shows."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
        unique_id=FLOW_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test that the reauth flow works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
        unique_id=FLOW_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    # Trigger reauth
    with patch(
        "homeassistant.components.tedee.async_setup_entry",
        return_value=True,
    ):
        reauth_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "unique_id": entry.unique_id,
                "entry_id": entry.entry_id,
            },
            data={
                CONF_ACCESS_TOKEN: ACCESS_TOKEN,
                CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
            },
        )
    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            reauth_result["flow_id"],
            {
                CONF_ACCESS_TOKEN: ACCESS_TOKEN,
                CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
            },
        )
        assert result["type"] == FlowResultType.ABORT
        await hass.async_block_till_done()
        assert result["reason"] == "reauth_successful"


async def test_reauth_flow_errors(hass: HomeAssistant) -> None:
    """Test that the reauth flow errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
        unique_id=FLOW_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data={
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_LOCAL_ACCESS_TOKEN: LOCAL_ACCESS_TOKEN,
        },
    )

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=TedeeLocalAuthException("Invalid Auth"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_TOKEN: "wrong_token",
                CONF_LOCAL_ACCESS_TOKEN: "wrong_token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {
        CONF_ACCESS_TOKEN: "invalid_api_key",
        CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key",
    }

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCESS_TOKEN: "token",
                CONF_LOCAL_ACCESS_TOKEN: "token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id=FLOW_UNIQUE_ID,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LOCAL_ACCESS_TOKEN: "token"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "invalid_host"}

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.42"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key"}

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=TedeeLocalAuthException("Invalid Auth"),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.42",
                CONF_LOCAL_ACCESS_TOKEN: "wrong_token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_LOCAL_ACCESS_TOKEN: "invalid_api_key"}

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.x",
                CONF_LOCAL_ACCESS_TOKEN: "wrong_token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "invalid_host"}

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=TedeeAuthException("invalid auth"),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ACCESS_TOKEN: "wrong_token"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_ACCESS_TOKEN: "invalid_api_key"}

    with patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ACCESS_TOKEN: "token"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.tedee.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.tedee.config_flow.TedeeClient.get_locks",
        return_value=True,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.42",
                CONF_LOCAL_ACCESS_TOKEN: "token1",
                CONF_ACCESS_TOKEN: "token2",
                CONF_HOME_ASSISTANT_ACCESS_TOKEN: "token3",
                CONF_UNLOCK_PULLS_LATCH: False,
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: "192.168.1.42",
        CONF_LOCAL_ACCESS_TOKEN: "token1",
        CONF_ACCESS_TOKEN: "token2",
        CONF_HOME_ASSISTANT_ACCESS_TOKEN: "token3",
        CONF_UNLOCK_PULLS_LATCH: False,
    }
