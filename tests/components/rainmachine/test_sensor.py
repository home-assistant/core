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


async def test_zone_entities_disabled_by_default(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Register zone diagnostics without enabling their states."""
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch(
            "homeassistant.components.rainmachine.PLATFORMS",
            [Platform.BINARY_SENSOR, Platform.SENSOR],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    for entity_id in (
        "binary_sensor.12345_landscaping_restrictions",
        "sensor.12345_landscaping_soil_type",
        "sensor.12345_landscaping_status",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id) is None

    status = entity_registry.async_get("sensor.12345_landscaping_status")
    assert status is not None
    assert status.entity_category is None


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

    assert hass.states.get("sensor.12345_landscaping_soil_type").state == "clay_loam"
    status = hass.states.get("sensor.12345_landscaping_status")
    assert status is not None
    assert status.state == "queued"
    assert "state_class" not in status.attributes


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
