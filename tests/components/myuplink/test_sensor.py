"""Tests for myuplink sensor module."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.myuplink.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor state."""

    with patch("homeassistant.components.myuplink.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_myuplink_client")
@pytest.mark.parametrize(
    "load_device_points_file",
    ["device_points_nibe_smo20.json"],
)
async def test_sensor_smo20_extra_parameters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that SMO 20 exposes average outdoor temp and degree minutes."""

    with patch("homeassistant.components.myuplink.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    prefix = "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff"
    outdoor_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{prefix}-40067"
    )
    degree_minutes_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{prefix}-40941"
    )
    assert outdoor_id is not None
    assert degree_minutes_id is not None

    outdoor = hass.states.get(outdoor_id)
    assert outdoor.state == "9.7"
    assert outdoor.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert outdoor.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert outdoor.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    degree_minutes = hass.states.get(degree_minutes_id)
    assert degree_minutes.state == "-120"
    assert degree_minutes.attributes[ATTR_UNIT_OF_MEASUREMENT] == "DM"
    assert degree_minutes.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    degree_minutes_entry = entity_registry.async_get(degree_minutes_id)
    assert degree_minutes_entry.options["sensor"]["suggested_display_precision"] == 0
    assert degree_minutes_entry.translation_key == "degree_minutes"
    assert degree_minutes.attributes[ATTR_FRIENDLY_NAME].endswith("Degree minutes")
