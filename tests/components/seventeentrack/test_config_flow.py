"""Define tests for the 17Track config flow."""
from unittest.mock import AsyncMock, patch

from py17track.errors import SeventeenTrackError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.seventeentrack import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
    DOMAIN,
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

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_create_entry(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "py17track.profile.Profile.login",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2["title"] == "17Track someemail@gmail.com"
        assert result2["data"] == {
            CONF_PASSWORD: "edc3eee7330e4fdda04489e3fbc283d0",
            CONF_USERNAME: "someemail@gmail.com",
        }


async def test_invalid_cred_error(hass: HomeAssistant) -> None:
    """Test that the user step fails."""
    with patch(
        "py17track.profile.Profile.login",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": "invalid_credentials"}


async def test_cannot_connect_error(hass: HomeAssistant) -> None:
    """Test that the user step fails."""
    with patch(
        "py17track.profile.Profile.login",
        side_effect=SeventeenTrackError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test the import configuration flow."""
    with patch(
        "py17track.profile.Profile.login",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=VALID_CONFIG_OLD,
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "17Track someemail@gmail.com"
        assert result["data"][CONF_USERNAME] == "someemail@gmail.com"
        assert result["data"][CONF_PASSWORD] == "edc3eee7330e4fdda04489e3fbc283d0"


async def test_option_flow(hass: HomeAssistant) -> None:
    """Test option flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    entry.add_to_hass(hass)

    assert not entry.options

    with patch(
        "py17track.profile.Profile.login",
        return_value=True,
    ):
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
