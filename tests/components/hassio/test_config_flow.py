"""Test the Home Assistant Supervisor config flow."""

from unittest.mock import patch

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.hassio import DOMAIN
from homeassistant.components.hassio.const import (
    DATA_HASSIO_SUPERVISOR_USER,
    DATA_HASSIO_UPDATE_OPTIONS,
    DEFAULT_UPDATE_OPTIONS,
    ENTRY_DATA_USER,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with (
        patch(
            "homeassistant.components.hassio.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.hassio.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Supervisor"
        assert result["data"] == {}
        assert result["options"] == DEFAULT_UPDATE_OPTIONS
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_multiple_entries(hass: HomeAssistant) -> None:
    """Test creating multiple hassio entries."""
    await test_config_flow(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "system"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_config_flow_uses_bootstrap_user(hass: HomeAssistant) -> None:
    """Test config flow stores the bootstrap supervisor user in entry data."""
    user = await hass.auth.async_create_system_user(
        "Supervisor", group_ids=[GROUP_ID_ADMIN]
    )
    hass.data[DATA_HASSIO_SUPERVISOR_USER] = user

    with (
        patch("homeassistant.components.hassio.async_setup", return_value=True),
        patch("homeassistant.components.hassio.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {ENTRY_DATA_USER: user.id}
    assert result["options"] == DEFAULT_UPDATE_OPTIONS


async def test_config_flow_without_bootstrap_user(hass: HomeAssistant) -> None:
    """Test config flow still creates default options without bootstrap user."""
    with (
        patch("homeassistant.components.hassio.async_setup", return_value=True),
        patch("homeassistant.components.hassio.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == DEFAULT_UPDATE_OPTIONS


async def test_config_flow_uses_bootstrap_update_options(hass: HomeAssistant) -> None:
    """Test config flow prefers migrated update options from setup bootstrap."""
    legacy_options = {
        "add_on_backup_before_update": True,
        "add_on_backup_retain_copies": 3,
        "core_backup_before_update": True,
    }
    hass.data[DATA_HASSIO_UPDATE_OPTIONS] = legacy_options

    with (
        patch("homeassistant.components.hassio.async_setup", return_value=True),
        patch("homeassistant.components.hassio.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == legacy_options
