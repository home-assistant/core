"""Tests for the Insteon base entity."""

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from pyinsteon.address import Address
from pyinsteon.constants import ResponseStatus
from pyinsteon.device_types.ipdb import ClimateControl_Thermostat
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import insteon
from homeassistant.components.homeassistant import (
    DOMAIN as HOME_ASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.insteon import (
    DOMAIN,
    entity as insteon_entity,
    services as insteon_services,
    utils as insteon_utils,
)
from homeassistant.components.insteon.entity import InsteonEntity
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

THERMOSTAT_ADDRESS = "66.66.66"


class _MockDevicesWithThermostat(MockDevices):
    """Mock devices including a thermostat."""

    async def async_load(self, *args: Any, **kwargs: Any) -> None:
        """Load the mock devices and a thermostat."""
        await super().async_load(*args, **kwargs)
        address = Address(THERMOSTAT_ADDRESS)
        thermostat = ClimateControl_Thermostat(
            address, 0x05, 0x0B, 0x00, "Device 66.66.66", "6"
        )
        thermostat.aldb.async_load = AsyncMock()
        thermostat.async_read_op_flags = AsyncMock(return_value=ResponseStatus.SUCCESS)
        self._devices[address] = thermostat


devices = _MockDevicesWithThermostat()


@pytest.fixture(autouse=True)
def patch_setup_and_devices() -> Generator[None]:
    """Patch the Insteon setup process and devices."""
    with (
        patch.object(insteon, "async_connect", new=mock_connection),
        patch.object(insteon, "async_close"),
        patch.object(insteon, "devices", devices),
        patch.object(insteon_utils, "devices", devices),
        patch.object(insteon_entity, "devices", devices),
        patch.object(insteon_services, "devices", devices),
    ):
        yield


async def mock_connection(*args: Any, **kwargs: Any) -> bool:
    """Return a successful connection."""
    return True


@pytest.mark.parametrize(
    ("platform", "address", "old_entity_id", "new_entity_id"),
    [
        pytest.param(
            Platform.LOCK,
            "55.55.55",
            "lock.device_55_55_55_55_55_55",
            "lock.renamed",
            id="lock",
        ),
        pytest.param(
            Platform.CLIMATE,
            THERMOSTAT_ADDRESS,
            "climate.device_66_66_66_66_66_66_group_1",
            "climate.renamed",
            id="climate",
        ),
    ],
)
@pytest.mark.parametrize(
    "service", ["load_all_link_database", "print_all_link_database"]
)
async def test_aldb_services_after_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: Platform,
    address: str,
    old_entity_id: str,
    new_entity_id: str,
    service: str,
) -> None:
    """Test the ALDB services target the new entity_id after a rename."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.insteon.INSTEON_PLATFORMS", (platform,)):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with patch.object(
        InsteonEntity,
        "async_will_remove_from_hass",
        autospec=True,
        side_effect=InsteonEntity.async_will_remove_from_hass,
    ) as mock_will_remove:
        entity_registry.async_update_entity(old_entity_id, new_entity_id=new_entity_id)
        await hass.async_block_till_done()

    # The entity_id is changed in place, the entity is not removed and re-added
    mock_will_remove.assert_not_called()

    try:
        with patch.object(insteon_entity, "print_aldb_to_log") as mock_print:
            await hass.services.async_call(
                DOMAIN, service, {"entity_id": old_entity_id}, blocking=True
            )
            await hass.async_block_till_done()
            mock_print.assert_not_called()

            await hass.services.async_call(
                DOMAIN, service, {"entity_id": new_entity_id}, blocking=True
            )
            await hass.async_block_till_done()
            mock_print.assert_called_once_with(devices[address].aldb)
    finally:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


async def test_async_update_requests_status_for_mains_powered_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test homeassistant.update_entity forwards the entity's group to async_status."""
    await async_setup_component(hass, HOME_ASSISTANT_DOMAIN, {})

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    # The thermostat's real async_status never returns without a modem, which
    # would keep the setup status pass holding the shared status lock
    with (
        patch("homeassistant.components.insteon.INSTEON_PLATFORMS", (Platform.LOCK,)),
        patch.object(ClimateControl_Thermostat, "async_status", new=AsyncMock()),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    try:
        lock = entity_registry.async_get("lock.device_55_55_55_55_55_55")

        # Setup already polled every non-battery device once
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


async def test_async_update_skips_battery_powered_device(hass: HomeAssistant) -> None:
    """Test async_update is a no-op for a battery-powered device."""
    await devices.async_load()
    device = devices["22.22.22"]
    device.async_status.reset_mock()
    entity = InsteonEntity(device, 1)
    entity.hass = hass

    await entity.async_update()

    device.async_status.assert_not_awaited()


async def test_async_update_suppresses_attribute_error(hass: HomeAssistant) -> None:
    """Test async_update doesn't raise for a device that lacks status support."""
    await devices.async_load()
    device = devices["11.11.11"]
    device.async_status.reset_mock()
    entity = InsteonEntity(device, 1)
    entity.hass = hass

    await entity.async_update()

    device.async_status.assert_awaited_once()


async def test_async_update_serializes_concurrent_status_requests(
    hass: HomeAssistant,
) -> None:
    """Test concurrent async_update calls don't overlap status requests."""
    await devices.async_load()
    device_a = devices["33.33.33"]
    device_b = devices["44.44.44"]
    device_a.async_status.reset_mock()
    device_b.async_status.reset_mock()

    active = 0
    max_active = 0

    async def fake_status(*args: Any, **kwargs: Any) -> None:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1

    device_a.async_status.side_effect = fake_status
    device_b.async_status.side_effect = fake_status

    entity_a = InsteonEntity(device_a, 1)
    entity_b = InsteonEntity(device_b, 1)
    entity_a.hass = hass
    entity_b.hass = hass

    try:
        await asyncio.gather(entity_a.async_update(), entity_b.async_update())

        assert max_active == 1
        device_a.async_status.assert_awaited_once()
        device_b.async_status.assert_awaited_once()
    finally:
        device_a.async_status.side_effect = None
        device_b.async_status.side_effect = None
