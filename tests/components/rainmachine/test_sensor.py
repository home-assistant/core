"""Test RainMachine sensors."""

import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rainmachine.const import (
    CONF_USE_APP_RUN_TIMES,
    DATA_PROVISION_SETTINGS,
    DATA_ZONES,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
) -> None:
    """Test sensors."""
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    expected = {
        "sensor.12345_landscaping_area": "92.9",
        "sensor.12345_landscaping_field_capacity": "0.17",
        "sensor.12345_landscaping_precipitation_rate": "25.4",
        "sensor.12345_landscaping_id": "1",
        "sensor.12345_landscaping_current_cycle": "0",
        "sensor.12345_landscaping_number_of_cycles": "0",
        "sensor.12345_landscaping_slope": "Flat",
        "sensor.12345_landscaping_soil_type": "Sandy Loam",
        "sensor.12345_landscaping_sprinkler_head_type": "Bubblers Drip",
        "sensor.12345_landscaping_status": "Not Running",
        "sensor.12345_landscaping_sun_exposure": "Full Sun",
        "sensor.12345_landscaping_vegetation_type": "Flowers",
    }
    for entity_id, value in expected.items():
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == value


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_zone_metadata_updates(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
) -> None:
    """Update per-zone sensors with new values from the coordinator."""
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinators[DATA_ZONES]
    zones = {**coordinator.data}
    zones[1] = {**zones[1], "soil": 1, "state": 2}
    coordinator.async_set_updated_data(zones)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.12345_landscaping_soil_type").state == "Clay Loam"
    assert hass.states.get("sensor.12345_landscaping_status").state == "Queued"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_app_zone_run_time_sensor(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
) -> None:
    """Expose and refresh the app-configured zone run time."""
    hass.config_entries.async_update_entry(
        config_entry,
        options={**config_entry.options, CONF_USE_APP_RUN_TIMES: True},
    )
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    entity_id = "sensor.12345_landscaping_run_time_from_app"
    assert hass.states.get(entity_id).state == "300"

    coordinator = config_entry.runtime_data.coordinators[DATA_PROVISION_SETTINGS]
    provision_data = {**coordinator.data}
    provision_data["system"] = {
        **provision_data["system"],
        "zoneDuration": [120, *provision_data["system"]["zoneDuration"][1:]],
    }
    coordinator.async_set_updated_data(provision_data)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "120"


async def test_device_info_hw_version_is_string(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that hw_version is a string even when API returns int."""
    with (
        caplog.at_level(logging.WARNING, logger="homeassistant.helpers.frame"),
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff"), config_entry.entry_id
    )
    assert device_entry
    assert device_entry.hw_version == "3"
    assert "non-string value" not in caplog.text
