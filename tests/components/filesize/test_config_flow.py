"""Test the filesize config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.filesize.config_flow import InvalidPath
from homeassistant.components.filesize.const import DOMAIN
from homeassistant.const import CONF_FILE_PATH, CONF_UNIT_OF_MEASUREMENT

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    hass.config.allowlist_external_dirs = "/home/pi/.homeassistant"

    with patch(
        "homeassistant.components.filesize.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.filesize.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILE_PATH: "/home/pi/.homeassistant/home-assistant_v2.db",
                CONF_UNIT_OF_MEASUREMENT: "MB",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "/home/pi/.homeassistant/home-assistant_v2.db_MB"
    assert result2["data"] == {
        CONF_FILE_PATH: "/home/pi/.homeassistant/home-assistant_v2.db",
        CONF_UNIT_OF_MEASUREMENT: "MB",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_path(hass):
    """Test we handle invalid path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.filesize.config_flow.validate_input",
        side_effect=InvalidPath,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FILE_PATH: "./does_not_exist.txt"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_path"}


# async def test_form_cannot_connect(hass):
#     """Test we handle cannot connect error."""
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     with patch(
#         "homeassistant.components.filesize.config_flow.PlaceholderHub.authenticate",
#         side_effect=CannotConnect,
#     ):
#         result2 = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             {
#                 "host": "1.1.1.1",
#                 "username": "test-username",
#                 "password": "test-password",
#             },
#         )

#     assert result2["type"] == "form"
#     assert result2["errors"] == {"base": "cannot_connect"}
