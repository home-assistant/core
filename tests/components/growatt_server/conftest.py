"""Fixtures for Growatt Server tests."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.growatt_server.number import (
    GrowattNumber,
    GrowattNumberEntityDescription,
)
from homeassistant.components.growatt_server.switch import (
    GrowattSwitch,
    GrowattSwitchEntityDescription,
)
from homeassistant.const import PERCENTAGE


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.device_id = "ABC123MIN456"
    coordinator.device_type = "min"
    coordinator.api_version = "v1"
    coordinator.data = {}
    coordinator.api = MagicMock()

    # Mock get_value to return data from coordinator.data
    def get_value(entity_description):
        return coordinator.data.get(entity_description.api_key)

    coordinator.get_value = get_value

    # Mock set_value to update coordinator.data
    def set_value(entity_description, value):
        coordinator.data[entity_description.api_key] = value

    coordinator.set_value = set_value

    return coordinator


@pytest.fixture
def mock_number_entity(mock_coordinator: MagicMock) -> GrowattNumber:
    """Create a mock number entity."""
    description = GrowattNumberEntityDescription(
        key="charge_power",
        translation_key="charge_power",
        api_key="chargePowerCommand",
        write_key="charge_power",
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    )

    entity = GrowattNumber(coordinator=mock_coordinator, description=description)
    entity.hass = MagicMock()

    # Mock async_add_executor_job to return a coroutine
    async def async_executor_job(func, *args):
        return func(*args)

    entity.hass.async_add_executor_job = async_executor_job
    entity.async_write_ha_state = MagicMock()

    return entity


@pytest.fixture
def mock_switch_entity(mock_coordinator: MagicMock) -> GrowattSwitch:
    """Create a mock switch entity."""
    description = GrowattSwitchEntityDescription(
        key="ac_charge",
        translation_key="ac_charge",
        api_key="acChargeEnable",
        write_key="ac_charge",
    )

    entity = GrowattSwitch(coordinator=mock_coordinator, description=description)
    entity.hass = MagicMock()

    # Mock async_add_executor_job to return a coroutine
    async def async_executor_job(func, *args):
        return func(*args)

    entity.hass.async_add_executor_job = async_executor_job
    entity.async_write_ha_state = MagicMock()

    return entity


def create_mock_number_entity(coordinator: MagicMock) -> GrowattNumber:
    """Create a mock number entity with a given coordinator."""
    description = GrowattNumberEntityDescription(
        key="charge_power",
        translation_key="charge_power",
        api_key="chargePowerCommand",
        write_key="charge_power",
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
    )
    return GrowattNumber(coordinator=coordinator, description=description)


def create_mock_switch_entity(coordinator: MagicMock) -> GrowattSwitch:
    """Create a mock switch entity with a given coordinator."""
    description = GrowattSwitchEntityDescription(
        key="ac_charge",
        translation_key="ac_charge",
        api_key="acChargeEnable",
        write_key="ac_charge",
    )
    return GrowattSwitch(coordinator=coordinator, description=description)
