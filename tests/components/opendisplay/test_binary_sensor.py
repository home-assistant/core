"""Test the OpenDisplay binary sensor platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import VALID_SERVICE_INFO

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info

ENTITY_ID = "binary_sensor.opendisplay_1234_connectivity"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the binary_sensor platform."""
    return [Platform.BINARY_SENSOR]


async def test_connectivity_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    setup_entry: Callable[[], Awaitable[None]],
) -> None:
    """Test the connectivity binary sensor entity registry entry and state."""
    await setup_entry()
    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("is_flex", [True, False])
async def test_connectivity_created_for_all_device_types(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
    setup_entry: Callable[[], Awaitable[None]],
    is_flex: bool,
) -> None:
    """Connectivity sensor is created for both Flex and non-Flex devices."""
    mock_opendisplay_device.is_flex = is_flex
    await setup_entry()

    assert hass.states.get(ENTITY_ID) is not None


async def test_connectivity_off_before_first_advertisement(
    hass: HomeAssistant,
    setup_entry: Callable[[], Awaitable[None]],
) -> None:
    """Connectivity is off before any advertisement is received."""
    await setup_entry()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_connectivity_on_after_advertisement(
    hass: HomeAssistant,
    setup_entry: Callable[[], Awaitable[None]],
) -> None:
    """Connectivity turns on after the device starts advertising."""
    await setup_entry()

    inject_bluetooth_service_info(hass, VALID_SERVICE_INFO)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON
