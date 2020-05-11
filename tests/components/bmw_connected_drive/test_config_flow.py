"""Test the for the BMW Connected Drive config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.bmw_connected_drive.config_flow import DOMAIN
from homeassistant.components.bmw_connected_drive.const import CONF_REGION
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "user@domain.com",
    CONF_PASSWORD: "p4ssw0rd",
    CONF_REGION: "rest_of_world",
}
FIXTURE_COMPLETE_ENTRY = FIXTURE_USER_INPUT.copy()
FIXTURE_IMPORT_ENTRY = FIXTURE_USER_INPUT.copy()


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass):
    """Test we show user form on Atag connection error."""

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
    assert result["errors"] == {"base": "invalid_auth"}


async def test_full_user_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    with patch(
        "bimmer_connected.account.ConnectedDriveAccount._get_vehicles", return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == FIXTURE_COMPLETE_ENTRY[CONF_USERNAME]
        assert result["data"] == FIXTURE_COMPLETE_ENTRY


async def test_full_config_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    with patch(
        "bimmer_connected.account.ConnectedDriveAccount._get_vehicles", return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=FIXTURE_USER_INPUT,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert (
            result["title"]
            == FIXTURE_IMPORT_ENTRY[CONF_USERNAME] + " (configuration.yaml)"
        )
        assert result["data"] == FIXTURE_IMPORT_ENTRY
