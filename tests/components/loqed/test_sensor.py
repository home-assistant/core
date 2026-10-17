"""Tests the LOQED sensors."""

from typing import Any
from unittest.mock import patch

from loqedAPI import loqed
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.loqed.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)

BATTERY_ENTITY_ID = "sensor.home_battery"
BLE_STRENGTH_ENTITY_ID = "sensor.home_bluetooth_signal"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    lock: loqed.Lock,
) -> None:
    """Test the sensor entities and their initial states."""
    config: dict[str, Any] = {DOMAIN: {CONF_API_TOKEN: ""}}
    config_entry.add_to_hass(hass)
    lock_status = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)

    with (
        patch("homeassistant.components.loqed.PLATFORMS", [Platform.SENSOR]),
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
        ),
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "attribute", "value"),
    [
        pytest.param(BATTERY_ENTITY_ID, "battery_percentage", 55, id="battery"),
        pytest.param(BLE_STRENGTH_ENTITY_ID, "ble_strength", -80, id="ble_strength"),
    ],
)
async def test_sensor_responds_to_updates(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    lock: loqed.Lock,
    entity_id: str,
    attribute: str,
    value: int,
) -> None:
    """Test the sensors follow the lock when the coordinator notifies listeners."""
    setattr(lock, attribute, value)
    integration.runtime_data.async_update_listeners()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == str(value)


async def test_ble_strength_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    integration: MockConfigEntry,
) -> None:
    """Test the diagnostic BLE strength sensor is disabled by default."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "Foo_ble_strength"
    )
    assert entity_id == BLE_STRENGTH_ENTITY_ID

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None

    assert hass.states.get(BATTERY_ENTITY_ID)
