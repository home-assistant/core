"""Test Scrape component setup process."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.scrape.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import MockRestData, return_integration_config

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
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


async def test_setup_config_no_configuration(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test setup from yaml missing configuration options."""
    config = {DOMAIN: None}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert entity_registry.entities == {}


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

    assert loaded_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test unload an entry."""

    assert loaded_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    loaded_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    entity = entity_registry.entities["sensor.current_version"]

    device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, loaded_entry.entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=loaded_entry.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )
    response = await client.remove_device(dead_device_entry.id, loaded_entry.entry_id)
    assert response["success"]


async def test_resource_template(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test resource_template is evaluated on each scan."""
    hass.states.async_set("sensor.input_sensor", "localhost")
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        text="<h1>First</h1>",
    )
    aioclient_mock.get(
        "http://localhost2",
        status=HTTPStatus.OK,
        text="<h1>Second</h1>",
    )

    config = {
        DOMAIN: {
            "resource_template": "http://{{ states.sensor.input_sensor.state }}",
            "verify_ssl": True,
            "sensor": [{"select": "h1", "name": "template sensor"}],
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("sensor.template_sensor")
    assert state.state == "First"

    hass.states.async_set("sensor.input_sensor", "localhost2")
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("sensor.template_sensor")
    assert state.state == "Second"
