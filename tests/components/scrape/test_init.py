"""Test Scrape component setup process."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.scrape.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import MockRestData, return_integration_config

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


async def test_setup_config(hass: HomeAssistant) -> None:
    """Test setup from yaml."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[{"select": ".current-version h1", "name": "HA version"}]
            )
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ) as mock_setup:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state.state == "Current Version: 2021.12.10"

    assert len(mock_setup.mock_calls) == 1


async def test_setup_no_data_fails_with_recovery(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup entry no data fails and recovers."""
    config = {
        DOMAIN: [
            return_integration_config(
                sensors=[{"select": ".current-version h1", "name": "HA version"}]
            ),
        ]
    }

    mocker = MockRestData("test_scrape_sensor_no_data")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.ha_version")
        assert state is None

        assert "Platform scrape not ready yet" in caplog.text

        mocker.payload = "test_scrape_sensor"
        async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state.state == "Current Version: 2021.12.10"


async def test_setup_config_no_configuration(hass: HomeAssistant) -> None:
    """Test setup from yaml missing configuration options."""
    config = {DOMAIN: None}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    entities = er.async_get(hass)
    assert entities.entities == {}


async def test_setup_config_no_sensors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup from yaml with no configured sensors finalize properly."""
    config = {
        DOMAIN: [
            {
                "resource": "https://www.address.com",
                "verify_ssl": True,
            },
            {
                "resource": "https://www.address2.com",
                "verify_ssl": True,
                "sensor": None,
            },
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test setup entry."""

    assert loaded_entry.state == config_entries.ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test unload an entry."""

    assert loaded_entry.state == config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def remove_device(ws_client, device_id, config_entry_id):
    """Remove config entry from a device."""
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry_id,
            "device_id": device_id,
        }
    )
    response = await ws_client.receive_json()
    return response["success"]


async def test_device_remove_devices(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    registry: er.EntityRegistry = er.async_get(hass)
    entity = registry.entities["sensor.current_version"]

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(entity.device_id)
    assert (
        await remove_device(
            await hass_ws_client(hass), device_entry.id, loaded_entry.entry_id
        )
        is False
    )

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=loaded_entry.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )
    assert (
        await remove_device(
            await hass_ws_client(hass), dead_device_entry.id, loaded_entry.entry_id
        )
        is True
    )
