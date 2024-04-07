"""Test the Reolink init."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.reolink import FIRMWARE_UPDATE_INTERVAL, const
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import TEST_CAM_MODEL, TEST_HOST_MODEL, TEST_MAC, TEST_NVR_NAME

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("reolink_connect", "reolink_platforms")


@pytest.mark.parametrize(
    ("attr", "value", "expected"),
    [
        (
            "is_admin",
            False,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "get_host_data",
            AsyncMock(side_effect=ReolinkError("Test error")),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "get_host_data",
            AsyncMock(side_effect=ValueError("Test error")),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "get_states",
            AsyncMock(side_effect=ReolinkError("Test error")),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "supported",
            Mock(return_value=False),
            ConfigEntryState.LOADED,
        ),
    ],
)
async def test_failures_parametrized(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
    attr: str,
    value: Any,
    expected: ConfigEntryState,
) -> None:
    """Test outcomes when changing errors."""
    setattr(reolink_connect, attr, value)
    assert await hass.config_entries.async_setup(config_entry.entry_id) is (
        expected is ConfigEntryState.LOADED
    )
    await hass.async_block_till_done()

    assert config_entry.state == expected


async def test_firmware_error_twice(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test when the firmware update fails 2 times."""
    reolink_connect.check_new_firmware = AsyncMock(
        side_effect=ReolinkError("Test error")
    )
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.UPDATE}.{TEST_NVR_NAME}_firmware"
    assert hass.states.is_state(entity_id, STATE_OFF)

    async_fire_time_changed(
        hass, utcnow() + FIRMWARE_UPDATE_INTERVAL + timedelta(minutes=1)
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)


async def test_entry_reloading(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test the entry is reloaded correctly when settings change."""
    reolink_connect.is_nvr = False
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert reolink_connect.logout.call_count == 0
    assert config_entry.title == "test_reolink_name"

    hass.config_entries.async_update_entry(config_entry, title="New Name")
    await hass.async_block_till_done()

    assert reolink_connect.logout.call_count == 1
    assert config_entry.title == "New Name"


@pytest.mark.parametrize(
    ("attr", "value", "expected_models"),
    [
        (
            None,
            None,
            [TEST_HOST_MODEL, TEST_CAM_MODEL],
        ),
        ("channels", [], [TEST_HOST_MODEL]),
        (
            "camera_model",
            Mock(return_value="RLC-567"),
            [TEST_HOST_MODEL, "RLC-567"],
        ),
    ],
)
async def test_cleanup_disconnected_cams(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    attr: str | None,
    value: Any,
    expected_models: list[str],
) -> None:
    """Test device and entity registry are cleaned up when camera is disconnected from NVR."""
    reolink_connect.channels = [0]
    # setup CH 0 and NVR switch entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    device_models = [device.model for device in device_entries]
    assert sorted(device_models) == sorted([TEST_HOST_MODEL, TEST_CAM_MODEL])

    # reload integration after 'disconnecting' a camera.
    if attr is not None:
        setattr(reolink_connect, attr, value)
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_reload(config_entry.entry_id)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    device_models = [device.model for device in device_entries]
    assert sorted(device_models) == sorted(expected_models)


async def test_cleanup_deprecated_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test deprecated ir_lights light entity is cleaned."""
    reolink_connect.channels = [0]
    ir_id = f"{TEST_MAC}_0_ir_lights"

    entity_registry.async_get_or_create(
        domain=Platform.LIGHT,
        platform=const.DOMAIN,
        unique_id=ir_id,
        config_entry=config_entry,
        suggested_object_id=ir_id,
        disabled_by=None,
    )

    assert entity_registry.async_get_entity_id(Platform.LIGHT, const.DOMAIN, ir_id)
    assert (
        entity_registry.async_get_entity_id(Platform.SWITCH, const.DOMAIN, ir_id)
        is None
    )

    # setup CH 0 and NVR switch entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(Platform.LIGHT, const.DOMAIN, ir_id) is None
    )
    assert entity_registry.async_get_entity_id(Platform.SWITCH, const.DOMAIN, ir_id)


async def test_no_repair_issue(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test no repairs issue is raised when http local url is used."""
    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "http://test_homeassistant_address"}
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "https_webhook") not in issue_registry.issues
    assert (const.DOMAIN, "webhook_url") not in issue_registry.issues
    assert (const.DOMAIN, "enable_port") not in issue_registry.issues
    assert (const.DOMAIN, "firmware_update") not in issue_registry.issues
    assert (const.DOMAIN, "ssl") not in issue_registry.issues


async def test_https_repair_issue(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test repairs issue is raised when https local url is used."""
    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "https://test_homeassistant_address"}
    )

    with (
        patch("homeassistant.components.reolink.host.FIRST_ONVIF_TIMEOUT", new=0),
        patch(
            "homeassistant.components.reolink.host.FIRST_ONVIF_LONG_POLL_TIMEOUT", new=0
        ),
        patch(
            "homeassistant.components.reolink.host.ReolinkHost._async_long_polling",
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "https_webhook") in issue_registry.issues


async def test_ssl_repair_issue(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test repairs issue is raised when global ssl certificate is used."""
    assert await async_setup_component(hass, "webhook", {})
    hass.config.api.use_ssl = True

    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "http://test_homeassistant_address"}
    )

    with (
        patch("homeassistant.components.reolink.host.FIRST_ONVIF_TIMEOUT", new=0),
        patch(
            "homeassistant.components.reolink.host.FIRST_ONVIF_LONG_POLL_TIMEOUT", new=0
        ),
        patch(
            "homeassistant.components.reolink.host.ReolinkHost._async_long_polling",
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "ssl") in issue_registry.issues


@pytest.mark.parametrize("protocol", ["rtsp", "rtmp"])
async def test_port_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    protocol: str,
) -> None:
    """Test repairs issue is raised when auto enable of ports fails."""
    reolink_connect.set_net_port = AsyncMock(side_effect=ReolinkError("Test error"))
    reolink_connect.onvif_enabled = False
    reolink_connect.rtsp_enabled = False
    reolink_connect.rtmp_enabled = False
    reolink_connect.protocol = protocol
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "enable_port") in issue_registry.issues


async def test_webhook_repair_issue(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test repairs issue is raised when the webhook url is unreachable."""
    with (
        patch("homeassistant.components.reolink.host.FIRST_ONVIF_TIMEOUT", new=0),
        patch(
            "homeassistant.components.reolink.host.FIRST_ONVIF_LONG_POLL_TIMEOUT", new=0
        ),
        patch(
            "homeassistant.components.reolink.host.ReolinkHost._async_long_polling",
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "webhook_url") in issue_registry.issues


async def test_firmware_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test firmware issue is raised when too old firmware is used."""
    reolink_connect.sw_version_update_required = True
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "firmware_update") in issue_registry.issues
