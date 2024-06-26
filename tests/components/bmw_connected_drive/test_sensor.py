"""Test BMW sensors."""

from unittest.mock import patch

from bimmer_connected.models import StrEnum
from bimmer_connected.vehicle import fuel_and_battery
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bmw_connected_drive import DOMAIN as BMW_DOMAIN
from homeassistant.components.bmw_connected_drive.const import SCAN_INTERVALS
from homeassistant.components.bmw_connected_drive.sensor import SENSOR_TYPES
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util.unit_system import (
    METRIC_SYSTEM as METRIC,
    US_CUSTOMARY_SYSTEM as IMPERIAL,
    UnitSystem,
)

from . import setup_mocked_integration

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.mark.freeze_time("2023-06-22 10:30:00+00:00")
@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state_attrs(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor options and values.."""

    # Setup component
    with patch(
        "homeassistant.components.bmw_connected_drive.PLATFORMS", [Platform.SENSOR]
    ):
        mock_config_entry = await setup_mocked_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.parametrize(
    ("entity_id", "unit_system", "value", "unit_of_measurement"),
    [
        ("sensor.i3_rex_remaining_range_total", METRIC, "279", "km"),
        ("sensor.i3_rex_remaining_range_total", IMPERIAL, "173.362562634216", "mi"),
        ("sensor.i3_rex_mileage", METRIC, "137009", "km"),
        ("sensor.i3_rex_mileage", IMPERIAL, "85133.4456772449", "mi"),
        ("sensor.i3_rex_remaining_battery_percent", METRIC, "82", "%"),
        ("sensor.i3_rex_remaining_battery_percent", IMPERIAL, "82", "%"),
        ("sensor.i3_rex_remaining_range_electric", METRIC, "174", "km"),
        ("sensor.i3_rex_remaining_range_electric", IMPERIAL, "108.118587449296", "mi"),
        ("sensor.i3_rex_remaining_fuel", METRIC, "6", "L"),
        ("sensor.i3_rex_remaining_fuel", IMPERIAL, "1.58503231414889", "gal"),
        ("sensor.i3_rex_remaining_range_fuel", METRIC, "105", "km"),
        ("sensor.i3_rex_remaining_range_fuel", IMPERIAL, "65.2439751849201", "mi"),
        ("sensor.m340i_xdrive_remaining_fuel_percent", METRIC, "80", "%"),
        ("sensor.m340i_xdrive_remaining_fuel_percent", IMPERIAL, "80", "%"),
    ],
)
async def test_unit_conversion(
    hass: HomeAssistant,
    entity_id: str,
    unit_system: UnitSystem,
    value: str,
    unit_of_measurement: str,
) -> None:
    """Test conversion between metric and imperial units for sensors."""

    # Set unit system
    hass.config.units = unit_system

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    entity = hass.states.get(entity_id)
    assert entity.state == value
    assert entity.attributes.get("unit_of_measurement") == unit_of_measurement


@pytest.mark.usefixtures("bmw_fixture")
async def test_entity_option_translations(
    hass: HomeAssistant,
) -> None:
    """Ensure all enum sensor values are translated."""

    # Setup component to load translations
    assert await setup_mocked_integration(hass)

    prefix = f"component.{BMW_DOMAIN}.entity.{Platform.SENSOR.value}"

    translations = await async_get_translations(hass, "en", "entity", [BMW_DOMAIN])
    translation_states = {
        k for k in translations if k.startswith(prefix) and ".state." in k
    }

    sensor_options = {
        f"{prefix}.{entity_description.translation_key}.state.{option}"
        for entity_description in SENSOR_TYPES
        if entity_description.device_class == SensorDeviceClass.ENUM
        for option in entity_description.options
    }

    assert sensor_options == translation_states


@pytest.mark.usefixtures("bmw_fixture")
async def test_enum_sensor_unknown(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, freezer: FrozenDateTimeFactory
) -> None:
    """Test conversion handling of enum sensors."""

    # Setup component
    assert await setup_mocked_integration(hass)

    entity_id = "sensor.i4_edrive40_charging_status"

    # Check normal state
    entity = hass.states.get(entity_id)
    assert entity.state == "not_charging"

    class ChargingStateUnkown(StrEnum):
        """Charging state of electric vehicle."""

        UNKNOWN = "UNKNOWN"

    # Setup enum returning only UNKNOWN
    monkeypatch.setattr(
        fuel_and_battery,
        "ChargingState",
        ChargingStateUnkown,
    )

    freezer.tick(SCAN_INTERVALS["rest_of_world"])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check normal state
    entity = hass.states.get("sensor.i4_edrive40_charging_status")
    assert entity.state == STATE_UNAVAILABLE
