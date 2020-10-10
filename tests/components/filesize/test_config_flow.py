"""Test the filesize config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.filesize.config_flow import InvalidPath, NotAFile
from homeassistant.components.filesize.const import DOMAIN
from homeassistant.const import CONF_FILE_PATH, CONF_UNIT_OF_MEASUREMENT

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    hass.config.allowlist_external_dirs = "/home/philip/.homeassistant/"

    with patch(
        "homeassistant.components.filesize.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.filesize.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILE_PATH: "/home/philip/.homeassistant/home-assistant_v2.db",
                CONF_UNIT_OF_MEASUREMENT: "GB",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "/home/philip/.homeassistant/home-assistant_v2.db (GB)"
    assert result2["data"] == {
        CONF_FILE_PATH: "/home/philip/.homeassistant/home-assistant_v2.db",
        CONF_UNIT_OF_MEASUREMENT: "GB",
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
            {CONF_FILE_PATH: "/root/test"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_FILE_PATH: "invalid_path"}


async def test_form_not_a_file(hass):
    """Test we handle invalid path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.filesize.config_flow.validate_input",
        side_effect=NotAFile,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FILE_PATH: "./does_not_exist.txt"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_FILE_PATH: "not_a_file"}
