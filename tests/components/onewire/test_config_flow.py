"""Tests for 1-Wire config flow."""
from pyownet import protocol

from homeassistant.components.onewire.const import (
    CONF_MOUNT_DIR,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.async_mock import patch


async def test_config_flow_owserver(hass):
    """Test OWServer flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: CONF_TYPE_OWSERVER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "owserver"
    assert result["errors"] == {}

    # Invalid server
    with patch(
        "homeassistant.components.onewire.config_flow.protocol.proxy",
        side_effect=protocol.ConnError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "owserver"
        assert result["errors"] == {"base": "cannot_connect"}

    # Valid server
    with patch(
        "homeassistant.components.onewire.config_flow.protocol.proxy",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "1.2.3.4"
        assert result["data"] == {
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
        }


async def test_config_flow_sysbus(hass):
    """Test SysBus flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: CONF_TYPE_SYSBUS},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "mount_dir"
    assert result["errors"] == {}

    # Invalid path
    with patch(
        "homeassistant.components.onewire.config_flow.os.path.isdir", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MOUNT_DIR: "/sys/bus/invalid_directory"},
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "mount_dir"
    assert result["errors"] == {"base": "invalid_path"}

    # Valid path
    with patch(
        "homeassistant.components.onewire.config_flow.os.path.isdir", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MOUNT_DIR: "/sys/bus/directory"},
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == CONF_TYPE_SYSBUS
    assert result["data"] == {
        CONF_TYPE: CONF_TYPE_SYSBUS,
        CONF_MOUNT_DIR: "/sys/bus/directory",
    }
