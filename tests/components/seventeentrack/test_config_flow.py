"""Define tests for the 17Track config flow."""

from unittest.mock import AsyncMock

from py17track.errors import SeventeenTrackError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.seventeentrack import DOMAIN
from homeassistant.components.seventeentrack.const import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_USERNAME: "someemail@gmail.com",
    CONF_PASSWORD: "edc3eee7330e4fdda04489e3fbc283d0",
}

VALID_CONFIG_OLD = {
    CONF_USERNAME: "someemail@gmail.com",
    CONF_PASSWORD: "edc3eee7330e4fdda04489e3fbc283d0",
}


async def test_create_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_seventeentrack: AsyncMock
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "someemail@gmail.com"
    assert result2["data"] == {
        CONF_PASSWORD: "edc3eee7330e4fdda04489e3fbc283d0",
        CONF_USERNAME: "someemail@gmail.com",
    }


async def test_invalid_cred_error(
    hass: HomeAssistant, mock_seventeentrack: AsyncMock
) -> None:
    """Test that the user step fails."""
    mock_seventeentrack.return_value.profile.login.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["errors"] == {"base": "invalid_credentials"}


async def test_cannot_connect_error(
    hass: HomeAssistant, mock_seventeentrack: AsyncMock
) -> None:
    """Test that the user step fails."""
    mock_seventeentrack.return_value.profile.login.side_effect = SeventeenTrackError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_import_flow(hass: HomeAssistant, mock_seventeentrack: AsyncMock) -> None:
    """Test the import configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=VALID_CONFIG_OLD,
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "someemail@gmail.com"
    assert result["data"][CONF_USERNAME] == "someemail@gmail.com"
    assert result["data"][CONF_PASSWORD] == "edc3eee7330e4fdda04489e3fbc283d0"


async def test_import_flow_cannot_connect_error(
    hass: HomeAssistant, mock_seventeentrack: AsyncMock
) -> None:
    """Test the import configuration flow with cannot_connect error."""
    mock_seventeentrack.return_value.profile.login.side_effect = SeventeenTrackError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=VALID_CONFIG_OLD,
    )

    assert result["reason"] == "cannot_connect"


async def test_import_flow_invalid_cred_error(
    hass: HomeAssistant, mock_seventeentrack: AsyncMock
) -> None:
    """Test the import configuration flow with cannot_connect error."""
    mock_seventeentrack.return_value.profile.login.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=VALID_CONFIG_OLD,
    )

    assert result["reason"] == "invalid_credentials"


async def test_option_flow(hass: HomeAssistant, mock_seventeentrack: AsyncMock) -> None:
    """Test option flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    entry.add_to_hass(hass)

    assert not entry.options

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        data=None,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SHOW_ARCHIVED: True, CONF_SHOW_DELIVERED: False},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SHOW_ARCHIVED]
    assert not result["data"][CONF_SHOW_DELIVERED]
