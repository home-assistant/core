"""Test BirdNET-Go sensors."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_birdnet_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test states and attributes of BirdNET-Go sensors."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # 1. Today Detections
    state = hass.states.get("sensor.birdnet_go_192_168_1_100_8080_today_detections")
    assert state is not None
    assert state.state == "138"

    # 2. Lifetime Species
    state = hass.states.get("sensor.birdnet_go_192_168_1_100_8080_lifetime_species")
    assert state is not None
    assert state.state == "42"

    # 3. Detection Streak
    state = hass.states.get("sensor.birdnet_go_192_168_1_100_8080_detection_streak")
    assert state is not None
    assert state.state == "17"
    assert state.attributes.get("unit_of_measurement") == "d"

    # 4. Best Day Count
    state = hass.states.get("sensor.birdnet_go_192_168_1_100_8080_best_day_detections")
    assert state is not None
    assert state.state == "420"

    # Entity registry check
    entry = entity_registry.async_get(
        "sensor.birdnet_go_192_168_1_100_8080_today_detections"
    )
    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.entry_id}_today_detections"

    # Device registry check
    device = device_registry.async_get_device_by_identifier(
        ("birdnet_go", mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "BirdNET-Go (192.168.1.100:8080)"
    assert device.manufacturer == "BirdNET-Go"
    assert device.entry_type == dr.DeviceEntryType.SERVICE
    assert device.configuration_url == "http://192.168.1.100:8080"
