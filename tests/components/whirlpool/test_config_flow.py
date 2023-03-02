"""Test the Whirlpool Sixth Sense config flow."""
import asyncio
from unittest.mock import patch

import aiohttp
from aiohttp.client_exceptions import ClientConnectionError

from homeassistant import config_entries
from homeassistant.components.whirlpool.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG_INPUT = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def test_form(
    hass: HomeAssistant,
    region,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch("homeassistant.components.whirlpool.config_flow.Auth.do_auth"), patch(
        "homeassistant.components.whirlpool.config_flow.Auth.is_access_token_valid",
        return_value=True,
    ), patch(
        "homeassistant.components.whirlpool.config_flow.BackendSelector"
    ) as mock_backend_selector, patch(
        "homeassistant.components.whirlpool.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.whirlpool.config_flow.AppliancesManager.aircons",
        return_value=["test"],
    ), patch(
        "homeassistant.components.whirlpool.config_flow.AppliancesManager.fetch_appliances",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_INPUT | {"region": region[0]},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "region": region[0],
    }
    assert len(mock_setup_entry.mock_calls) == 1
    mock_backend_selector.assert_called_once_with(region[2], region[1])


async def test_form_invalid_auth(hass: HomeAssistant, region) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch("homeassistant.components.whirlpool.config_flow.Auth.do_auth"), patch(
        "homeassistant.components.whirlpool.config_flow.Auth.is_access_token_valid",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_INPUT
            | {
                "region": region[0],
            },
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant, region) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.whirlpool.config_flow.Auth.do_auth",
        side_effect=aiohttp.ClientConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_INPUT
            | {
                "region": region[0],
            },
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_auth_timeout(hass: HomeAssistant, region) -> None:
    """Test we handle auth timeout error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.whirlpool.config_flow.Auth.do_auth",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_INPUT
            | {
                "region": region[0],
            },
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_generic_auth_exception(hass: HomeAssistant, region) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.whirlpool.config_flow.Auth.do_auth",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_INPUT
            | {
                "region": region[0],
            },
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant, region) -> None:
    """Test we handle cannot connect error."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {"region": region[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch("homeassistant.components.whirlpool.config_flow.Auth.do_auth"), patch(
        "homeassistant.components.whirlpool.config_flow.Auth.is_access_token_valid",
        return_value=True,
    ), patch(
        "homeassistant.components.whirlpool.config_flow.AppliancesManager.aircons",
        return_value=["test"],
    ), patch(
        "homeassistant.components.whirlpool.config_flow.AppliancesManager.fetch_appliances",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_INPUT
            | {
                "region": region[0],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_no_appliances_flow(hass: HomeAssistant, region) -> None:
    """Test we get and error with no appliances."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch("homeassistant.components.whirlpool.config_flow.Auth.do_auth"), patch(
        "homeassistant.components.whirlpool.config_flow.Auth.is_access_token_valid",
        return_value=True,
    ), patch(
        "homeassistant.components.whirlpool.config_flow.AppliancesManager.fetch_appliances",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_INPUT | {"region": region[0]},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "no_appliances"}


async def test_reauth_flow(hass: HomeAssistant, region) -> None:
    """Test a successful reauth flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {"region": region[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=CONFIG_INPUT | {"region": region[0]},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.whirlpool.async_setup_entry",
        return_value=True,
    ), patch("homeassistant.components.whirlpool.config_flow.Auth.do_auth"), patch(
        "homeassistant.components.whirlpool.config_flow.Auth.is_access_token_valid",
        return_value=True,
    ), patch(
        "homeassistant.components.whirlpool.config_flow.AppliancesManager.aircons",
        return_value=["test"],
    ), patch(
        "homeassistant.components.whirlpool.config_flow.AppliancesManager.fetch_appliances",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "new-password",
        "region": region[0],
    }


async def test_reauth_flow_auth_error(hass: HomeAssistant, region) -> None:
    """Test an authorization error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {"region": region[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "new-password",
            "region": region[0],
        },
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.whirlpool.async_setup_entry",
        return_value=True,
    ), patch("homeassistant.components.whirlpool.config_flow.Auth.do_auth"), patch(
        "homeassistant.components.whirlpool.config_flow.Auth.is_access_token_valid",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_connnection_error(hass: HomeAssistant, region) -> None:
    """Test a connection error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT | {"region": region[0]},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=CONFIG_INPUT | {"region": region[0]},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.whirlpool.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.whirlpool.config_flow.Auth.do_auth",
        side_effect=ClientConnectionError,
    ), patch(
        "homeassistant.components.whirlpool.config_flow.Auth.is_access_token_valid",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
