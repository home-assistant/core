"""Test the Nobø Ecohub climate entity."""

from unittest.mock import MagicMock

from homeassistant.components.climate import ClimateEntityFeature
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
