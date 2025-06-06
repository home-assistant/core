"""Test the Nobø Ecohub climate entity."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    ClimateEntityFeature,
)
from homeassistant.components.nobo_hub.climate import NoboZone


async def test_supported_features() -> None:
    """Test that supported entity features are set correctly."""
    mock_hub = MagicMock()
    mock_hub.components = {
        "device_1": {
            "zone_id": "zone_1",
            "model": MagicMock(supports_comfort=True, supports_eco=True),
        },
        "device_2": {
            "zone_id": "zone_1",
            "model": MagicMock(supports_comfort=False, supports_eco=True),
        },
    }

    # Both comfort and eco supported
    zone = NoboZone("zone_1", mock_hub, "override_type")
    assert zone._attr_supported_features == (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )

    # Only comfort supported
    mock_hub.components["device_1"]["model"].supports_eco = False
    mock_hub.components["device_2"]["model"].supports_eco = False
    zone = NoboZone("zone_1", mock_hub, "override_type")
    assert zone._attr_supported_features == (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    # Only eco supported
    mock_hub.components["device_1"]["model"].supports_comfort = False
    mock_hub.components["device_1"]["model"].supports_eco = True
    zone = NoboZone("zone_1", mock_hub, "override_type")
    assert zone._attr_supported_features == (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    # Neither comfort nor eco supported
    mock_hub.components["device_1"]["model"].supports_comfort = False
    mock_hub.components["device_1"]["model"].supports_eco = False
    zone = NoboZone("zone_1", mock_hub, "override_type")
    assert zone._attr_supported_features == ClimateEntityFeature.PRESET_MODE


async def test_async_set_temperature_single_temperature() -> None:
    """Test setting a single temperature."""
    mock_hub = MagicMock()
    mock_hub.async_update_zone = AsyncMock()

    # Zone supports comfort
    zone = NoboZone("zone_1", mock_hub, "override_type")
    zone._supports_comfort = True
    zone._supports_eco = False

    await zone.async_set_temperature(**{ATTR_TEMPERATURE: 22})

    mock_hub.async_update_zone.assert_awaited_once_with("zone_1", temp_comfort_c=22)


async def test_async_set_temperature_range() -> None:
    """Test setting a temperature range."""
    mock_hub = MagicMock()
    mock_hub.async_update_zone = AsyncMock()

    # Zone supports both comfort and eco
    zone = NoboZone("zone_1", mock_hub, "override_type")
    zone._supports_comfort = True
    zone._supports_eco = True

    await zone.async_set_temperature(
        **{ATTR_TARGET_TEMP_LOW: 18, ATTR_TARGET_TEMP_HIGH: 24}
    )

    mock_hub.async_update_zone.assert_awaited_once_with(
        "zone_1", temp_comfort_c=24, temp_eco_c=18
    )


async def test_async_set_temperature_no_action() -> None:
    """Test no action when no valid arguments are provided."""
    mock_hub = MagicMock()
    mock_hub.async_update_zone = AsyncMock()

    # Zone supports comfort
    zone = NoboZone("zone_1", mock_hub, "override_type")
    zone._supports_comfort = True
    zone._supports_eco = False

    await zone.async_set_temperature()

    mock_hub.async_update_zone.assert_not_awaited()


async def test_async_set_temperature_eco_only() -> None:
    """Test setting temperature for eco-only zones."""
    mock_hub = MagicMock()
    mock_hub.async_update_zone = AsyncMock()

    # Zone supports eco only
    zone = NoboZone("zone_1", mock_hub, "override_type")
    zone._supports_comfort = False
    zone._supports_eco = True

    await zone.async_set_temperature(**{ATTR_TEMPERATURE: 20})

    mock_hub.async_update_zone.assert_awaited_once_with("zone_1", temp_eco_c=20)
