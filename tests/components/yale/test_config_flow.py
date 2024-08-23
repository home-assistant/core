"""Test the Yale config flow."""

from unittest.mock import patch

from yalexs.manager.exceptions import CannotConnect, InvalidAuth

from homeassistant import config_entries
from homeassistant.components.yale.const import (
    CONF_ACCESS_TOKEN_CACHE_FILE,
    CONF_BRAND,
    CONF_INSTALL_ID,
    CONF_LOGIN_METHOD,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.yale.config_flow.YaleGateway.async_authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.yale.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: "yale_home",
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "my@email.tld"
    assert result2["data"] == {
        CONF_BRAND: "yale_home",
        CONF_LOGIN_METHOD: "email",
        CONF_USERNAME: "my@email.tld",
        CONF_INSTALL_ID: None,
        CONF_ACCESS_TOKEN_CACHE_FILE: ".my@email.tld.august.conf",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yale.config_flow.YaleGateway.async_authenticate",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: "yale_home",
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle an unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yale.config_flow.YaleGateway.async_authenticate",
        side_effect=ValueError("something exploded"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: "yale_home",
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unhandled"}
    assert result2["description_placeholders"] == {"error": "something exploded"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yale.config_flow.YaleGateway.async_authenticate",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_reauth(hass: HomeAssistant) -> None:
    """Test reauthenticate."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOGIN_METHOD: "email",
            CONF_USERNAME: "my@email.tld",
            CONF_PASSWORD: "test-password",
            CONF_INSTALL_ID: None,
            CONF_TIMEOUT: 10,
            CONF_ACCESS_TOKEN_CACHE_FILE: ".my@email.tld.august.conf",
        },
        unique_id="my@email.tld",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=entry.data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.yale.config_flow.YaleGateway.async_authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.yale.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1
