"""Test the for the BMW Connected Drive config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.bmw_connected_drive.config_flow import DOMAIN
from homeassistant.components.bmw_connected_drive.const import (
    CONF_READ_ONLY,
    CONF_USE_LOCATION,
)
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "user@domain.com",
    CONF_PASSWORD: "p4ssw0rd",
    CONF_REGION: "rest_of_world",
}
FIXTURE_COMPLETE_ENTRY = FIXTURE_USER_INPUT.copy()
FIXTURE_IMPORT_ENTRY = FIXTURE_USER_INPUT.copy()

FIXTURE_CONFIG_ENTRY = {
    "entry_id": "1",
    "domain": DOMAIN,
    "title": FIXTURE_USER_INPUT[CONF_USERNAME],
    "data": {
        CONF_USERNAME: FIXTURE_USER_INPUT[CONF_USERNAME],
        CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD],
        CONF_REGION: FIXTURE_USER_INPUT[CONF_REGION],
    },
    "options": {CONF_READ_ONLY: False, CONF_USE_LOCATION: False},
    "system_options": {"disable_new_entities": False},
    "source": "user",
    "connection_class": config_entries.CONN_CLASS_CLOUD_POLL,
    "unique_id": f"{FIXTURE_USER_INPUT[CONF_REGION]}-{FIXTURE_USER_INPUT[CONF_REGION]}",
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass):
    """Test we show user form on BMW connected drive connection error."""

    def _mock_get_oauth_token(*args, **kwargs):
        pass

    with patch(
        "bimmer_connected.account.ConnectedDriveAccount._get_oauth_token",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_full_user_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    with patch(
        "bimmer_connected.account.ConnectedDriveAccount._get_vehicles",
        return_value=[],
    ), patch(
        "homeassistant.components.bmw_connected_drive.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.bmw_connected_drive.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )
        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result2["title"] == FIXTURE_COMPLETE_ENTRY[CONF_USERNAME]
        assert result2["data"] == FIXTURE_COMPLETE_ENTRY

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_full_config_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    with patch(
        "bimmer_connected.account.ConnectedDriveAccount._get_vehicles",
        return_value=[],
    ), patch(
        "homeassistant.components.bmw_connected_drive.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.bmw_connected_drive.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=FIXTURE_USER_INPUT,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == FIXTURE_IMPORT_ENTRY[CONF_USERNAME]
        assert result["data"] == FIXTURE_IMPORT_ENTRY

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow_implementation(hass):
    """Test config flow options."""
    with patch(
        "bimmer_connected.account.ConnectedDriveAccount._get_vehicles",
        return_value=[],
    ), patch(
        "homeassistant.components.bmw_connected_drive.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.bmw_connected_drive.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "account_options"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_READ_ONLY: False, CONF_USE_LOCATION: False},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_READ_ONLY: False,
            CONF_USE_LOCATION: False,
        }

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1
