"""Tests for the Insteon entity base class."""

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
