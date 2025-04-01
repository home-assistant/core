"""Tests for Renault sensors."""

from collections.abc import Generator
import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from renault_api.kamereon.exceptions import (
    KamereonResponseException,
    QuotaLimitException,
)
from renault_api.kamereon.models import KamereonVehicleBatteryStatusData
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

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


@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_throttling_during_setup(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault sensors with a throttling error during setup."""
    # Set initial time

    battery = None

    # Mock successful data update with a proper async function
    async def _return_battery_data(self):
        if "battery" in self.name and battery is not None:
            return battery
        raise KamereonResponseException("unknown", "unknown")

    with (
        patch(
            "homeassistant.components.renault.coordinator.RenaultDataUpdateCoordinator._call_update_method",
            new=_return_battery_data,
        ),
        patch(
            "homeassistant.components.renault.renault_hub.RenaultHub._get_now",
            return_value=0,
        ),
    ):
        # Patch the update method to raise QuotaLimitException during setup
        async def _raise_quota_exception(*args, **kwargs):
            raise QuotaLimitException(
                "err.func.wired.overloaded", "err.func.wired.overloaded"
            )

        with patch(
            "homeassistant.components.renault.coordinator.RenaultDataUpdateCoordinator._call_update_method",
            side_effect=_raise_quota_exception,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        # Check that devices are registered but sensor has None state
        mock_vehicle = MOCK_VEHICLES[vehicle_type]
        check_device_registry(device_registry, mock_vehicle["expected_device"])

        # Enable all entities for testing
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        assert len(entity_entries) > 0, "No entities were registered"

        battery_entity = None
        for ent in entity_entries:
            entity_registry.async_update_entity(ent.entity_id, disabled_by=None)
            # Find the battery entity
            if ent.entity_id[-len("_battery") :] == "_battery":
                battery_entity = ent

        assert battery_entity is not None, "Battery level entity not found"

        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify the sensor state is None/unavailable
        sensor_state = hass.states.get(battery_entity.entity_id)
        assert sensor_state is not None, (
            f"Entity {battery_entity.entity_id} not found in hass states"
        )
        assert sensor_state.state in ["unavailable", "unknown"]

        # Get coordinator from entity
        entity = hass.data[DATA_INSTANCES]["sensor"].get_entity(
            battery_entity.entity_id
        )
        assert entity is not None, "Could not find entity object"
        coordinator = entity.coordinator

        # Move time forward 10 minutes (cooldown still active)
        with patch(
            "homeassistant.components.renault.renault_hub.RenaultHub._get_now",
            return_value=10 * 60,
        ):
            # Trigger data update directly on the coordinator
            battery = None  # will throw an exception, that shouldn't be raised at all as we are in cooldowns
            call_to_update = 0
            try:
                await coordinator.async_refresh()
            except (KamereonResponseException, QuotaLimitException):
                call_to_update = 1

            assert call_to_update == 0, "Exception should not be raised during cooldown"

            # Sensor should still be unavailable
            sensor_state = hass.states.get(battery_entity.entity_id)
            assert sensor_state is not None
            assert sensor_state.state in ["unavailable", "unknown"]

        battery = KamereonVehicleBatteryStatusData(
            timestamp=None,
            batteryLevel=50,
            batteryTemperature=None,
            batteryAutonomy=None,
            batteryCapacity=None,
            batteryAvailableEnergy=None,
            plugStatus=None,
            chargingStatus=None,
            chargingRemainingTime=None,
            chargingInstantaneousPower=None,
            raw_data={},
        )

        # Move time forward to 30 minutes (cooldown expired)
        with patch(
            "homeassistant.components.renault.renault_hub.RenaultHub._get_now",
            return_value=30 * 60,
        ):
            # Trigger data update directly on the coordinator
            await coordinator.async_refresh()

            # Sensor should now have data
            sensor_state = hass.states.get(battery_entity.entity_id)
            assert sensor_state is not None
            assert sensor_state.state == "50"


@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_throttling_after_init(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault sensors with a throttling error after initialization."""
    # Set initial time

    batteryLevel75 = KamereonVehicleBatteryStatusData(
        timestamp=None,
        batteryLevel=75,
        batteryTemperature=None,
        batteryAutonomy=None,
        batteryCapacity=None,
        batteryAvailableEnergy=None,
        plugStatus=None,
        chargingStatus=None,
        chargingRemainingTime=None,
        chargingInstantaneousPower=None,
        raw_data={},
    )

    batteryLevel60 = KamereonVehicleBatteryStatusData(
        timestamp=None,
        batteryLevel=60,
        batteryTemperature=None,
        batteryAutonomy=None,
        batteryCapacity=None,
        batteryAvailableEnergy=None,
        plugStatus=None,
        chargingStatus=None,
        chargingRemainingTime=None,
        chargingInstantaneousPower=None,
        raw_data={},
    )

    battery = batteryLevel75

    async def _return_updated_battery(self, *args, **kwargs):
        if "battery" in self.name and battery is not None:
            return battery
        raise KamereonResponseException("unknown", "unknown")

    with patch(
        "homeassistant.components.renault.coordinator.RenaultDataUpdateCoordinator._call_update_method",
        new=_return_updated_battery,
    ):
        with patch(
            "homeassistant.components.renault.renault_hub.RenaultHub._get_now",
            return_value=0,
        ):
            # Normal setup with successful data update using async function
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

            # Check that devices are registered and sensor has correct state
            mock_vehicle = MOCK_VEHICLES[vehicle_type]
            check_device_registry(device_registry, mock_vehicle["expected_device"])

            # Enable all entities for testing
            entity_entries = er.async_entries_for_config_entry(
                entity_registry, config_entry.entry_id
            )
            assert len(entity_entries) > 0, "No entities were registered"

            battery_entity = None
            for ent in entity_entries:
                entity_registry.async_update_entity(ent.entity_id, disabled_by=None)
                # Find the battery entity
                if ent.entity_id[-len("_battery") :] == "_battery":
                    battery_entity = ent

            assert battery_entity is not None, "Battery level entity not found"

            await hass.config_entries.async_reload(config_entry.entry_id)
            await hass.async_block_till_done()

            # Get coordinator from entity
            entity = hass.data[DATA_INSTANCES]["sensor"].get_entity(
                battery_entity.entity_id
            )
            assert entity is not None, "Could not find entity object"
            coordinator = entity.coordinator

            # Verify the sensor has initial value
            sensor_state = hass.states.get(battery_entity.entity_id)
            assert sensor_state is not None, (
                f"Entity {battery_entity.entity_id} not found in hass states"
            )
            assert sensor_state.state == "75"

        # Move time forward 10 minutes and trigger quota limit exception
        with patch(
            "homeassistant.components.renault.renault_hub.RenaultHub._get_now",
            return_value=10 * 60,
        ):

            async def _return_quota_exception(self, *args, **kwargs):
                raise QuotaLimitException(
                    "err.func.wired.overloaded", "err.func.wired.overloaded"
                )

            # Mock update attempt during cooldown
            with patch(
                "homeassistant.components.renault.coordinator.RenaultDataUpdateCoordinator._call_update_method",
                new=_return_quota_exception,
            ):
                # Trigger data update directly on the coordinator
                await coordinator.async_refresh()

                # Sensor should keep the old value despite error
                sensor_state = hass.states.get(battery_entity.entity_id)
                assert sensor_state is not None
                assert sensor_state.state == "75"

        # Move time forward to 20 minutes (cooldown still active)
        with patch(
            "homeassistant.components.renault.renault_hub.RenaultHub._get_now",
            return_value=20 * 60,
        ):
            # Mock update attempt during cooldown
            battery = None  # will throw an exception, that shouldn't be raised at all as we are in cooldowns
            call_to_update = 0
            try:
                await coordinator.async_refresh()
            except (KamereonResponseException, QuotaLimitException):
                call_to_update = 1

            assert call_to_update == 0, "Exception should not be raised during cooldown"

            # Sensor should still have old value due to cooldown
            sensor_state = hass.states.get(battery_entity.entity_id)
            assert sensor_state is not None
            assert sensor_state.state == "75"

        # Move time forward to 30 minutes (cooldown expired)
        with patch(
            "homeassistant.components.renault.renault_hub.RenaultHub._get_now",
            return_value=30 * 60,
        ):
            # Mock successful data update with new value using async function
            battery = batteryLevel60

            # Trigger data update directly on the coordinator
            await coordinator.async_refresh()

            # Sensor should now have updated data
            sensor_state = hass.states.get(battery_entity.entity_id)
            assert sensor_state is not None
            assert sensor_state.state == "60"


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
    freezer.tick(datetime.timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "55"


@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_throttling_after_init(
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
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial state
    entity_id = "sensor.reg_number_battery"
    assert hass.states.get(entity_id).state == "60"

    # Test QuotaLimitException state
    for get_data_mock in patches.values():
        get_data_mock.side_effect = QuotaLimitException(
            "err.func.wired.overloaded", "You have reached your quota limit"
        )
    freezer.tick(datetime.timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Test QuotaLimitException recovery, with new battery level
    for get_data_mock in patches.values():
        get_data_mock.side_effect = None
    patches["battery_status"].return_value.batteryLevel = 55
    freezer.tick(datetime.timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "55"
