"""Tests for 1-Wire config flow."""
from unittest.mock import patch

from pyownet import protocol

from homeassistant.components.onewire.const import (
    CONF_MOUNT_DIR,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import setup_onewire_owserver_integration, setup_onewire_sysbus_integration


async def test_user_owserver(hass):
    """Test OWServer user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: CONF_TYPE_OWSERVER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "owserver"
    assert not result["errors"]

    # Invalid server
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
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
    with patch("homeassistant.components.onewire.onewirehub.protocol.proxy",), patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_owserver_duplicate(hass):
    """Test OWServer flow."""
    with patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await setup_onewire_owserver_integration(hass)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: CONF_TYPE_OWSERVER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "owserver"
    assert not result["errors"]

    # Duplicate server
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_sysbus(hass):
    """Test SysBus flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: CONF_TYPE_SYSBUS},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "mount_dir"
    assert not result["errors"]

    # Invalid path
    with patch(
        "homeassistant.components.onewire.onewirehub.os.path.isdir",
        return_value=False,
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
        "homeassistant.components.onewire.onewirehub.os.path.isdir",
        return_value=True,
    ), patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MOUNT_DIR: "/sys/bus/directory"},
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "/sys/bus/directory"
    assert result["data"] == {
        CONF_TYPE: CONF_TYPE_SYSBUS,
        CONF_MOUNT_DIR: "/sys/bus/directory",
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_sysbus_duplicate(hass):
    """Test SysBus duplicate flow."""
    with patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await setup_onewire_sysbus_integration(hass)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: CONF_TYPE_SYSBUS},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "mount_dir"
    assert not result["errors"]

    # Valid path
    with patch(
        "homeassistant.components.onewire.onewirehub.os.path.isdir",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MOUNT_DIR: DEFAULT_SYSBUS_MOUNT_DIR},
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_sysbus(hass):
    """Test import step."""

    with patch(
        "homeassistant.components.onewire.onewirehub.os.path.isdir",
        return_value=True,
    ), patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_TYPE: CONF_TYPE_SYSBUS},
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_SYSBUS_MOUNT_DIR
    assert result["data"] == {
        CONF_TYPE: CONF_TYPE_SYSBUS,
        CONF_MOUNT_DIR: DEFAULT_SYSBUS_MOUNT_DIR,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_sysbus_with_mount_dir(hass):
    """Test import step."""

    with patch(
        "homeassistant.components.onewire.onewirehub.os.path.isdir",
        return_value=True,
    ), patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_TYPE: CONF_TYPE_SYSBUS,
                CONF_MOUNT_DIR: DEFAULT_SYSBUS_MOUNT_DIR,
            },
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_SYSBUS_MOUNT_DIR
    assert result["data"] == {
        CONF_TYPE: CONF_TYPE_SYSBUS,
        CONF_MOUNT_DIR: DEFAULT_SYSBUS_MOUNT_DIR,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_owserver(hass):
    """Test import step."""

    with patch("homeassistant.components.onewire.onewirehub.protocol.proxy",), patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_TYPE: CONF_TYPE_OWSERVER,
                CONF_HOST: "1.2.3.4",
            },
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_TYPE: CONF_TYPE_OWSERVER,
        CONF_HOST: "1.2.3.4",
        CONF_PORT: DEFAULT_OWSERVER_PORT,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_owserver_with_port(hass):
    """Test import step."""

    with patch("homeassistant.components.onewire.onewirehub.protocol.proxy",), patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_TYPE: CONF_TYPE_OWSERVER,
                CONF_HOST: "1.2.3.4",
                CONF_PORT: 1234,
            },
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_TYPE: CONF_TYPE_OWSERVER,
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 1234,
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_owserver_duplicate(hass):
    """Test OWServer flow."""
    # Initialise with single entry
    with patch(
        "homeassistant.components.onewire.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await setup_onewire_owserver_integration(hass)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    # Import duplicate entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
        },
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
