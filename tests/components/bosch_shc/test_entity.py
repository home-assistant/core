"""Tests for the Bosch SHC entity base classes."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import BatteryLevelService
import pytest

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import battery_only_device, setup_integration

from tests.common import MockConfigEntry

HUB_IDENTIFIER = (DOMAIN, "test-mac")


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the binary_sensor platform."""
    with patch(
        "homeassistant.components.bosch_shc.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.fixture
def motion_device(mock_session: MagicMock) -> MagicMock:
    """The mock device backing the motion detector's battery sensor."""
    return mock_session.device_helper.motion_detectors[0]


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [battery_only_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shc_entity_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    motion_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """SHCEntity links its device to the SHC hub via via_device_id."""
    await setup_integration(hass, mock_config_entry)

    hub_device = device_registry.async_get_device_by_identifier(
        HUB_IDENTIFIER, mock_config_entry.entry_id
    )
    assert hub_device is not None

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, motion_device.id), mock_config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == hub_device.id


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [battery_only_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shc_entity_via_device_id_mismatch(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    motion_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setup does not crash and skips the link when the hub identifier does not match.

    boschshcpy may render the hub identifier and a device's root_device_id
    differently, so the lookup can miss.
    """
    motion_device.root_device_id = "root-serial-mismatch"

    await setup_integration(hass, mock_config_entry)

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, motion_device.id), mock_config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id is None


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors": [battery_only_device(device_services=[MagicMock()])]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_callbacks_after_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    motion_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Callbacks keep working across an entity_id change and are removed on unload."""
    await setup_integration(hass, mock_config_entry)
    service = motion_device.device_services[0]
    key = motion_device.subscribe_callback.call_args.args[0]
    service.subscribe_callback.assert_called_once()
    assert service.subscribe_callback.call_args.args[0] == key

    entity_registry.async_update_entity(
        "binary_sensor.motion_battery", new_entity_id="binary_sensor.renamed_battery"
    )
    await hass.async_block_till_done()

    motion_device.batterylevel = BatteryLevelService.State.LOW_BATTERY
    motion_device.subscribe_callback.call_args.args[1]()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.renamed_battery").state == STATE_ON

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    motion_device.subscribe_callback.assert_called_once()
    motion_device.unsubscribe_callback.assert_called_once_with(key)
    service.unsubscribe_callback.assert_called_once_with(key)
