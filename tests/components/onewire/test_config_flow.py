"""Tests for 1-Wire config flow."""
from unittest.mock import AsyncMock, patch

from pyownet import protocol
import pytest

from homeassistant.components.onewire.const import (
    CONF_MOUNT_DIR,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


@pytest.fixture(autouse=True, name="mock_setup_entry")
def override_async_setup_entry() -> AsyncMock:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.onewire.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_user_owserver(hass: HomeAssistant, mock_setup_entry: AsyncMock):
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
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
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
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_owserver_duplicate(
    hass: HomeAssistant, config_entry: ConfigEntry, mock_setup_entry: AsyncMock
):
    """Test OWServer flow."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
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


async def test_user_sysbus(hass: HomeAssistant, mock_setup_entry: AsyncMock):
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
    ):
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


async def test_user_sysbus_duplicate(
    hass: HomeAssistant, sysbus_config_entry: ConfigEntry, mock_setup_entry: AsyncMock
):
    """Test SysBus duplicate flow."""
    await hass.config_entries.async_setup(sysbus_config_entry.entry_id)
    await hass.async_block_till_done()
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
