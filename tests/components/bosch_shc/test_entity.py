"""Tests for the Bosch SHC base entity classes."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.components.bosch_shc.entity import SHCDomainEntity, SHCEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

ENTITY_ID = "binary_sensor.test"


@pytest.fixture
def shc_entity(mock_device: MagicMock) -> SHCEntity:
    """A bare SHCEntity wired up for lifecycle testing."""
    return SHCEntity(device=mock_device, parent_id="test-mac", entry_id="entry-id")


async def test_device_id_returns_device_id(shc_entity: SHCEntity) -> None:
    """device_id exposes the underlying device's id."""
    assert shc_entity.device_id == "hdm:HomeMaticIP:contact1"


async def test_async_added_to_hass_subscribes_callback(
    hass: HomeAssistant, shc_entity: SHCEntity, mock_device: MagicMock
) -> None:
    """async_added_to_hass registers a per-service callback with the device."""
    shc_entity.hass = hass
    shc_entity.entity_id = ENTITY_ID

    await shc_entity.async_added_to_hass()

    mock_device.subscribe_callback.assert_called_once()
    assert mock_device.subscribe_callback.call_args.args[0] == ENTITY_ID


async def test_async_will_remove_from_hass_unsubscribes(
    hass: HomeAssistant, shc_entity: SHCEntity, mock_device: MagicMock
) -> None:
    """async_will_remove_from_hass unsubscribes the device callback."""
    shc_entity.hass = hass
    shc_entity.entity_id = ENTITY_ID
    await shc_entity.async_added_to_hass()

    await shc_entity.async_will_remove_from_hass()

    mock_device.unsubscribe_callback.assert_called_once_with(ENTITY_ID)


async def test_on_state_changed_schedules_update(
    hass: HomeAssistant, shc_entity: SHCEntity, mock_device: MagicMock
) -> None:
    """The registered callback schedules a state update while the device exists."""
    shc_entity.hass = hass
    shc_entity.entity_id = ENTITY_ID
    await shc_entity.async_added_to_hass()
    on_state_changed = mock_device.subscribe_callback.call_args.args[1]

    with patch.object(shc_entity, "schedule_update_ha_state") as mock_schedule:
        on_state_changed()

    mock_schedule.assert_called_once_with()


async def test_on_state_changed_removes_deleted_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_device: MagicMock,
) -> None:
    """A device reporting deleted=True is dropped from this config entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, mock_device.id)},
    )
    entity = SHCEntity(
        device=mock_device, parent_id="test-mac", entry_id=entry.entry_id
    )
    entity.hass = hass
    entity.entity_id = ENTITY_ID
    await entity.async_added_to_hass()
    on_state_changed = mock_device.subscribe_callback.call_args.args[1]
    mock_device.deleted = True

    on_state_changed()
    await hass.async_block_till_done()

    assert device_registry.async_get(device_entry.id) is None


async def test_shc_entity_available_reflects_device_status(
    mock_device: MagicMock,
) -> None:
    """Available is true exactly when the device status is AVAILABLE."""
    entity = SHCEntity(device=mock_device, parent_id="test-mac", entry_id="entry-id")
    assert entity.available is True

    mock_device.status = "UNAVAILABLE"

    assert entity.available is False


async def test_shc_entity_subscribes_every_device_service(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """SHCEntity subscribes/unsubscribes each of the device's services."""
    service_a = MagicMock()
    service_b = MagicMock()
    mock_device.device_services = [service_a, service_b]
    entity = SHCEntity(device=mock_device, parent_id="test-mac", entry_id="entry-id")
    entity.hass = hass
    entity.entity_id = ENTITY_ID

    await entity.async_added_to_hass()

    service_a.subscribe_callback.assert_called_once()
    assert service_a.subscribe_callback.call_args.args[0] == ENTITY_ID
    service_b.subscribe_callback.assert_called_once()

    on_state_changed = service_a.subscribe_callback.call_args.args[1]
    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        on_state_changed()
    mock_schedule.assert_called_once_with()

    await entity.async_will_remove_from_hass()

    service_a.unsubscribe_callback.assert_called_once_with(ENTITY_ID)
    service_b.unsubscribe_callback.assert_called_once_with(ENTITY_ID)


async def test_shc_domain_entity_device_info(mock_intrusion_system: MagicMock) -> None:
    """SHCDomainEntity builds device info from the domain object."""
    entity = SHCDomainEntity(
        domain=mock_intrusion_system, parent_id="test-mac", entry_id="entry-id"
    )

    assert entity.unique_id == "intrusionSystem"
    assert entity.device_info is not None
    assert entity.device_info["identifiers"] == {(DOMAIN, "intrusionSystem")}
    assert entity.device_info["via_device"] == (DOMAIN, "test-mac")


async def test_shc_domain_entity_available_reflects_system_availability(
    mock_intrusion_system: MagicMock,
) -> None:
    """Available mirrors the intrusion system's system_availability flag."""
    entity = SHCDomainEntity(
        domain=mock_intrusion_system, parent_id="test-mac", entry_id="entry-id"
    )
    mock_intrusion_system.system_availability = True
    assert entity.available is True

    mock_intrusion_system.system_availability = False

    assert entity.available is False
