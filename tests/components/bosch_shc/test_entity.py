"""Tests for the Bosch SHC base entity classes.

Exercised through the binary_sensor platform's BatterySensor (a real
SHCEntity subclass) wherever possible, rather than constructing SHCEntity
directly, so these tests fail if entity creation or registration through a
config entry breaks. SHCDomainEntity is the one exception: no ha-core
platform instantiates it today (see its class docstring), so there is no
config entry flow to route it through.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import BatteryLevelService
import pytest

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.components.bosch_shc.entity import SHCDomainEntity
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import battery_only_device, setup_integration

from tests.common import MockConfigEntry

BATTERY_ENTITY_ID = "binary_sensor.motion"
MOTION_IDENTIFIER = (DOMAIN, "hdm:HomeMaticIP:motion1")


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the binary_sensor platform."""
    with patch(
        "homeassistant.components.bosch_shc.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.fixture
def motion_device(mock_session: MagicMock) -> MagicMock:
    """The mock device backing binary_sensor.motion."""
    return mock_session.device_helper.motion_detectors[0]


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [battery_only_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_async_added_to_hass_subscribes_device_and_services(
    hass: HomeAssistant,
    motion_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """SHCEntity subscribes the device itself and every one of its services."""
    service_a = MagicMock()
    service_b = MagicMock()
    motion_device.device_services = [service_a, service_b]

    await setup_integration(hass, mock_config_entry)

    motion_device.subscribe_callback.assert_called_once_with(
        BATTERY_ENTITY_ID, motion_device.subscribe_callback.call_args.args[1]
    )
    service_a.subscribe_callback.assert_called_once_with(
        BATTERY_ENTITY_ID, service_a.subscribe_callback.call_args.args[1]
    )
    service_b.subscribe_callback.assert_called_once()

    motion_device.batterylevel = BatteryLevelService.State.LOW_BATTERY
    service_a_on_state_changed = service_a.subscribe_callback.call_args.args[1]
    service_a_on_state_changed()
    await hass.async_block_till_done()

    assert (state := hass.states.get(BATTERY_ENTITY_ID)) is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [battery_only_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_on_state_changed_updates_state(
    hass: HomeAssistant,
    motion_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The device-level callback refreshes the entity's state."""
    await setup_integration(hass, mock_config_entry)
    on_state_changed = motion_device.subscribe_callback.call_args.args[1]
    motion_device.batterylevel = BatteryLevelService.State.LOW_BATTERY

    on_state_changed()
    await hass.async_block_till_done()

    assert (state := hass.states.get(BATTERY_ENTITY_ID)) is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [battery_only_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_on_state_changed_removes_deleted_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    motion_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device reporting deleted=True is dropped from the device registry."""
    await setup_integration(hass, mock_config_entry)
    on_state_changed = motion_device.subscribe_callback.call_args.args[1]
    motion_device.deleted = True

    on_state_changed()
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={MOTION_IDENTIFIER}) is None


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [battery_only_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_async_will_remove_from_hass_unsubscribes_device_and_services(
    hass: HomeAssistant,
    motion_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unloading the entry unsubscribes the device and every one of its services."""
    service = MagicMock()
    motion_device.device_services = [service]
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    motion_device.unsubscribe_callback.assert_called_once_with(BATTERY_ENTITY_ID)
    service.unsubscribe_callback.assert_called_once_with(BATTERY_ENTITY_ID)


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [battery_only_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shc_entity_available_reflects_device_status(
    hass: HomeAssistant,
    motion_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The entity becomes unavailable once the device status is no longer AVAILABLE."""
    await setup_integration(hass, mock_config_entry)
    on_state_changed = motion_device.subscribe_callback.call_args.args[1]
    motion_device.status = "UNAVAILABLE"

    on_state_changed()
    await hass.async_block_till_done()

    assert (state := hass.states.get(BATTERY_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE


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
