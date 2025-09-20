"""Test the Dali Center light platform."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import snapshot_platform

from tests.common import MockConfigEntry, SnapshotAssertion


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.LIGHT]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dali_gateway: MagicMock,
    mock_devices: list[MagicMock],
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.dali_center._PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 3

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id is not None


async def test_turn_on_light(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test turning on a light."""
    entity_id = "light.dimmer_0000_02_light"

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_devices[0].turn_on.assert_called_once()


async def test_turn_off_light(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test turning off a light."""
    entity_id = "light.dimmer_0000_02_light"

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_devices[0].turn_off.assert_called_once()


async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test turning on light with brightness."""
    entity_id = "light.dimmer_0000_02_light"

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness": 128},
        blocking=True,
    )

    mock_devices[0].turn_on.assert_called_once_with(
        brightness=128,
        color_temp_kelvin=None,
        hs_color=None,
        rgbw_color=None,
    )


async def test_dispatcher_connection(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test that dispatcher signals are properly connected."""
    entity_id = "light.dimmer_0000_02_light"

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None

    status_update: dict[str, Any] = {"is_on": True, "brightness": 128}

    async_dispatcher_send(
        hass, "dali_center_update_01010000026A242121110E", status_update
    )
    await hass.async_block_till_done()

    state_after = hass.states.get(entity_id)
    assert state_after is not None


async def test_color_temp_status_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test status update with color temperature for CCT device."""
    status_update = {"color_temp_kelvin": 3000}
    async_dispatcher_send(
        hass, "dali_center_update_01020000036A242121110E", status_update
    )
    await hass.async_block_till_done()


async def test_hs_color_status_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test status update with HS color for HS device."""
    status_update = {"hs_color": (120.0, 50.0)}
    async_dispatcher_send(
        hass, "dali_center_update_01030000046A242121110E", status_update
    )
    await hass.async_block_till_done()


async def test_rgbw_status_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test status update with RGBW color and white level."""
    status_update1 = {"rgbw_color": (255, 128, 64, 32)}
    async_dispatcher_send(
        hass, "dali_center_update_01040000056A242121110E", status_update1
    )
    await hass.async_block_till_done()

    status_update2 = {"white_level": 200}
    async_dispatcher_send(
        hass, "dali_center_update_01040000056A242121110E", status_update2
    )
    await hass.async_block_till_done()
