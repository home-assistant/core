"""Test the Seventeentrack config flow."""
from unittest.mock import AsyncMock

from py17track.errors import SeventeenTrackError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.seventeentrack.const import CONF_SHOW_ARCHIVED, DOMAIN
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    CONF_NAME: "Seventeentrack",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}
MOCK_OPTIONS = {CONF_SCAN_INTERVAL: 10, CONF_SHOW_ARCHIVED: True}


async def test_flow_works(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Seventeentrack"
    assert result["data"] == MOCK_CONFIG


async def test_options(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options=MOCK_OPTIONS,
        unique_id="email@email.com",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 30, CONF_SHOW_ARCHIVED: True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 30,
        CONF_SHOW_ARCHIVED: True,
    }


async def test_form_invalid_auth(hass: HomeAssistant, mock_api) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.return_value.login = AsyncMock(return_value=False)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_unknwon_error(hass: HomeAssistant, mock_api) -> None:
    """Test we handle SeventeenTrackError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api.side_effect = SeventeenTrackError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="email@email.com",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-password",
        },
    )

    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failed(hass: HomeAssistant, mock_api) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="email@email.com",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    mock_api.return_value.login = AsyncMock(return_value=False)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-password",
        },
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
