"""The tests for the Synology SRM device tracker platform."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun import freeze_time
import pytest

from homeassistant.components import device_tracker, synology_srm
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from . import (
    DEVICE_2_WIRELESS,
    DEVICE_2_WIRELESS_OFFLINE,
    DEVICE_3_NUMERIC_NAME,
    DEVICE_3_WIRELESS,
    DEVICE_DATA,
    GET_NETWORK_NSM_DEVICE,
    MOCK_DATA,
    MOCK_OPTIONS,
    setup_synology_srm_entry,
)

from tests.common import MockConfigEntry, async_fire_time_changed, patch


@pytest.fixture
def mock_device_registry_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Create device registry devices so the device tracker entities are enabled."""
    config_entry = MockConfigEntry(domain="something_else")
    config_entry.add_to_hass(hass)

    for idx, device in enumerate(
        (
            "00:00:00:00:00:01",
            "00:00:00:00:00:02",
            "00:00:00:00:00:03",
            "00:00:00:00:00:04",
            "00:00:00:00:01:01",
            "00:00:00:00:01:02",
            "00:00:00:00:01:03",
        )
    ):
        device_registry.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )


def mock_command(
    self, cmd: str, params: dict[str, Any] | None = None, suppress_errors: bool = False
) -> Any:
    """Mock the Synology SRM command method."""
    if cmd == GET_NETWORK_NSM_DEVICE:
        return DEVICE_DATA
    return {}


async def test_device_trackers(
    hass: HomeAssistant, mock_device_registry_devices
) -> None:
    """Test device_trackers created by Synology SRM."""

    # test devices one online, one offline
    await setup_synology_srm_entry(hass)

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == "home"
    assert device_1.attributes["ip"] == "0.0.0.1"
    assert device_1.attributes["mac"] == "00:00:00:00:00:01"
    assert device_1.attributes["host_name"] == "Device_1"

    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "not_home"

    device_1w = hass.states.get("device_tracker.device_1w")
    assert device_1w
    assert device_1w.state == "not_home"

    device_3 = hass.states.get("device_tracker.device_3")
    assert device_3 is None

    with patch.object(
        synology_srm.coordinator.SynologySRMData, "command", new=mock_command
    ):
        # test device_2w is added
        DEVICE_DATA.append(DEVICE_2_WIRELESS)
        DEVICE_DATA.append(DEVICE_3_WIRELESS)

        async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)

        device_2w = hass.states.get("device_tracker.device_2w")
        assert device_2w
        assert device_2w.state == "home"
        assert device_2w.attributes["ip"] == "0.0.1.2"
        assert device_2w.attributes["mac"] == "00:00:00:00:01:02"
        assert device_2w.attributes["host_name"] == "Device_2w"

        # test state remains home if last_seen within consider_home_interval
        del DEVICE_DATA[4]  # device 3 wireless is removed from list
        DEVICE_DATA[3].update(
            DEVICE_2_WIRELESS_OFFLINE
        )  # device 2w setting is_online: False

        with freeze_time(utcnow() + timedelta(minutes=4)):
            async_fire_time_changed(hass, utcnow() + timedelta(minutes=4))
            await hass.async_block_till_done(wait_background_tasks=True)

        device_2w = hass.states.get("device_tracker.device_2w")
        assert device_2w
        assert device_2w.state == "home"

        device_3w = hass.states.get("device_tracker.device_3w")
        assert device_3w
        assert device_3w.state == "home"

        # test state changes to away if last_seen past consider_home_interval
        with freeze_time(utcnow() + timedelta(minutes=6)):
            async_fire_time_changed(hass, utcnow() + timedelta(minutes=6))
            await hass.async_block_till_done(wait_background_tasks=True)

        device_2w = hass.states.get("device_tracker.device_2w")
        assert device_2w
        assert device_2w.state == "not_home"

        device_3w = hass.states.get("device_tracker.device_3w")
        assert device_3w
        assert device_3w.state == "not_home"


async def test_device_trackers_numerical_name(
    hass: HomeAssistant, mock_device_registry_devices
) -> None:
    """Test device_trackers created by Synology SRM with numerical device name."""

    await setup_synology_srm_entry(hass, device_data=[DEVICE_3_NUMERIC_NAME])

    device_3 = hass.states.get("device_tracker.123")
    assert device_3
    assert device_3.state == "home"
    assert device_3.attributes["friendly_name"] == "123"
    assert device_3.attributes["ip"] == "0.0.0.3"
    assert device_3.attributes["mac"] == "00:00:00:00:00:03"
    assert device_3.attributes["host_name"] == "123"


async def test_restoring_devices(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test restoring existing device_tracker entities if not detected on startup."""
    config_entry = MockConfigEntry(
        domain=synology_srm.DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS
    )
    config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        synology_srm.DOMAIN,
        "00:00:00:00:00:01",
        suggested_object_id="device_1",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        synology_srm.DOMAIN,
        "00:00:00:00:00:02",
        suggested_object_id="device_2",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        synology_srm.DOMAIN,
        "00:00:00:00:00:03",
        suggested_object_id="device_3",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        synology_srm.DOMAIN,
        "00:00:00:00:00:04",
        suggested_object_id="device_4",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        synology_srm.DOMAIN,
        "00:00:00:00:01:01",
        suggested_object_id="device_1w",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        synology_srm.DOMAIN,
        "00:00:00:00:01:02",
        suggested_object_id="device_2w",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        synology_srm.DOMAIN,
        "00:00:00:00:01:03",
        suggested_object_id="device_3w",
        config_entry=config_entry,
    )
    await setup_synology_srm_entry(hass)

    # test device_2 which is not in wireless list is restored
    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "home"
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2 is not None
    assert device_2.state == "not_home"
    # device_3 is not on the list so it won't be restored.
    device_3 = hass.states.get("device_tracker.device_3")
    assert device_3 is None
    device_1w = hass.states.get("device_tracker.device_1w")
    assert device_1w is not None
    device_2w = hass.states.get("device_tracker.device_2w")
    assert device_2w is not None
    device_3w = hass.states.get("device_tracker.device_3w")
    assert device_3w is None


async def test_update_failed(hass: HomeAssistant, mock_device_registry_devices) -> None:
    """Test failing to connect during update."""

    await setup_synology_srm_entry(hass)

    with patch.object(
        synology_srm.coordinator.SynologySRMData,
        "command",
        side_effect=synology_srm.errors.CannotConnect,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == STATE_UNAVAILABLE
