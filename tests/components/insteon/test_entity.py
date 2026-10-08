"""Tests for the Insteon base entity."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from pyinsteon.address import Address
from pyinsteon.constants import ResponseStatus
from pyinsteon.device_types.ipdb import ClimateControl_Thermostat
import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon import (
    DOMAIN,
    entity as insteon_entity,
    utils as insteon_utils,
)
from homeassistant.components.insteon.entity import InsteonEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

from tests.common import MockConfigEntry

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
