"""Tests for the Insteon entity base class."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components import insteon
from homeassistant.components.homeassistant import (
    DOMAIN as HOME_ASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.insteon import (
    DOMAIN,
    entity as insteon_entity,
    utils as insteon_utils,
)
from homeassistant.components.insteon.entity import InsteonEntity
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .const import MOCK_USER_INPUT_PLM
from .mock_connection import mock_successful_connection
from .mock_devices import MockDevices

from tests.common import MockConfigEntry

devices = MockDevices()


@pytest.fixture(autouse=True)
def lock_platform_only():
    """Only setup the lock and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.insteon.INSTEON_PLATFORMS",
        (Platform.LOCK,),
    ):
        yield


@pytest.fixture(autouse=True)
def patch_setup_and_devices():
    """Patch the Insteon setup process and devices."""
    with (
        patch.object(insteon, "async_connect", new=mock_successful_connection),
        patch.object(insteon, "async_close"),
        patch.object(insteon, "devices", devices),
        patch.object(insteon_utils, "devices", devices),
        patch.object(insteon_entity, "devices", devices),
    ):
        yield


async def test_async_update_requests_status_for_mains_powered_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test homeassistant.update_entity forwards the entity's group to async_status."""

    await async_setup_component(hass, HOME_ASSISTANT_DOMAIN, {})

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    try:
        lock = entity_registry.async_get("lock.device_55_55_55_55_55_55")

        # Setup's own async_get_device_config background task already polled
        # every non-battery device once (see homeassistant/components/insteon/
        # __init__.py); reset so the assertion below only covers the explicit
        # update_entity call this test is exercising.
        devices["55.55.55"].async_status.reset_mock()

        await hass.services.async_call(
            HOME_ASSISTANT_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: lock.entity_id},
            blocking=True,
        )
        devices["55.55.55"].async_status.assert_awaited_once_with(1)
    finally:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


async def test_async_update_skips_battery_powered_device() -> None:
    """Test async_update is a no-op for a battery-powered device.

    GeneralController_RemoteLinc devices (e.g. 22.22.22) have no entry in
    ipdb.DEVICE_PLATFORM and are never set up as a standard HA entity, so
    this exercises InsteonEntity.async_update directly against the device
    rather than through a full platform/service-call setup.
    """
    await devices.async_load()
    device = devices["22.22.22"]
    entity = InsteonEntity(device, 1)

    await entity.async_update()

    device.async_status.assert_not_awaited()


async def test_async_update_suppresses_attribute_error() -> None:
    """Test async_update doesn't raise for a device that lacks status support.

    Device 11.11.11 is a mains-powered SwitchLinc whose async_status is
    mocked to raise AttributeError (see mock_devices.py), modeling a real
    device type that doesn't support status requests. The startup pass in
    async_get_device_config suppresses this and treats it as a no-op; a
    forced refresh via async_update should do the same rather than let the
    exception surface as a failed update.
    """
    await devices.async_load()
    device = devices["11.11.11"]
    entity = InsteonEntity(device, 1)

    await entity.async_update()  # should not raise

    device.async_status.assert_awaited_once()


async def test_async_update_serializes_concurrent_status_requests() -> None:
    """Test concurrent async_update calls don't overlap status requests.

    homeassistant.update_entity gathers every selected entity's async_update
    concurrently, but Insteon's protocol requires status requests to run one
    at a time (see the sequential loop in async_get_device_config). This
    exercises two different devices directly, mirroring the battery-skip
    test above, rather than a full platform/service-call setup.
    """
    await devices.async_load()
    device_a = devices["33.33.33"]
    device_b = devices["44.44.44"]

    # Reset: an earlier test's setup already exercised these same mocks.
    device_a.async_status.reset_mock()
    device_b.async_status.reset_mock()

    active = 0
    max_active = 0

    async def fake_status(*args, **kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1

    device_a.async_status.side_effect = fake_status
    device_b.async_status.side_effect = fake_status

    entity_a = InsteonEntity(device_a, 1)
    entity_b = InsteonEntity(device_b, 1)

    await asyncio.gather(entity_a.async_update(), entity_b.async_update())

    assert max_active == 1
    device_a.async_status.assert_awaited_once()
    device_b.async_status.assert_awaited_once()
