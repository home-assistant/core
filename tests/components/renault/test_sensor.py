"""Tests for Renault sensors."""

from collections.abc import Generator
import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from renault_api.kamereon.exceptions import QuotaLimitException
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import check_device_registry, check_entities_unavailable
from .conftest import _get_fixtures, patch_get_vehicle_data
from .const import MOCK_VEHICLES

from tests.common import async_fire_time_changed

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("fixtures_with_data")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for Renault sensors."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure devices are correctly registered
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert device_entries == snapshot

    # Ensure entities are correctly registered
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    # Some entities are disabled, enable them and reload before checking states
    for ent in entity_entries:
        entity_registry.async_update_entity(ent.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entity states are correct
    states = [hass.states.get(ent.entity_id) for ent in entity_entries]
    assert states == snapshot


@pytest.mark.usefixtures("fixtures_with_no_data", "entity_registry_enabled_by_default")
async def test_sensor_empty(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for Renault sensors with empty data from Renault."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure devices are correctly registered
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert device_entries == snapshot

    # Ensure entities are correctly registered
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    # Ensure entity states are correct
    states = [hass.states.get(ent.entity_id) for ent in entity_entries]
    assert states == snapshot


@pytest.mark.usefixtures(
    "fixtures_with_invalid_upstream_exception", "entity_registry_enabled_by_default"
)
async def test_sensor_errors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault sensors with temporary failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[Platform.SENSOR]
    assert len(entity_registry.entities) == len(expected_entities)

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities_unavailable(hass, entity_registry, expected_entities)


@pytest.mark.usefixtures("fixtures_with_access_denied_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_access_denied(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault sensors with access denied failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    assert len(entity_registry.entities) == 0


@pytest.mark.usefixtures("fixtures_with_not_supported_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_not_supported(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault sensors with access denied failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    assert len(entity_registry.entities) == 0


@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_throttling_during_setup(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for Renault sensors with a throttling error during setup."""
    mock_fixtures = _get_fixtures(vehicle_type)
    with patch_get_vehicle_data() as patches:
        for key, get_data_mock in patches.items():
            get_data_mock.return_value = mock_fixtures[key]
            get_data_mock.side_effect = QuotaLimitException(
                "err.func.wired.overloaded", "You have reached your quota limit"
            )
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial state
    entity_id = "sensor.reg_number_battery"
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Test QuotaLimitException recovery, with new battery level
    for get_data_mock in patches.values():
        get_data_mock.side_effect = None
    patches["battery_status"].return_value.batteryLevel = 55
    freezer.tick(datetime.timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "55"


@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_throttling_after_init(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for Renault sensors with a throttling error during setup."""
    mock_fixtures = _get_fixtures(vehicle_type)
    with patch_get_vehicle_data() as patches:
        for key, get_data_mock in patches.items():
            get_data_mock.return_value = mock_fixtures[key]
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial state
    entity_id = "sensor.reg_number_battery"
    assert hass.states.get(entity_id).state == "60"
    assert not hass.states.get(entity_id).attributes.get(ATTR_ASSUMED_STATE)
    assert "Renault API throttled: scan skipped" not in caplog.text

    # Test QuotaLimitException state
    caplog.clear()
    for get_data_mock in patches.values():
        get_data_mock.side_effect = QuotaLimitException(
            "err.func.wired.overloaded", "You have reached your quota limit"
        )
    freezer.tick(datetime.timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "60"
    assert hass.states.get(entity_id).attributes.get(ATTR_ASSUMED_STATE)
    assert "Renault API throttled" in caplog.text
    assert "Renault hub currently throttled: scan skipped" in caplog.text

    # Test QuotaLimitException recovery, with new battery level
    caplog.clear()
    for get_data_mock in patches.values():
        get_data_mock.side_effect = None
    patches["battery_status"].return_value.batteryLevel = 55
    freezer.tick(datetime.timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "55"
    assert not hass.states.get(entity_id).attributes.get(ATTR_ASSUMED_STATE)
    assert "Renault API throttled" not in caplog.text
    assert "Renault hub currently throttled: scan skipped" not in caplog.text
