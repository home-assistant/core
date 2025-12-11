"""tests relating to sensor setup for Powersensor's home assistant integration."""

import logging
from unittest.mock import AsyncMock, Mock

from powersensor_local import VirtualHousehold
import pytest

from homeassistant.components.powersensor import RT_DISPATCHER
from homeassistant.components.powersensor.const import (
    CREATE_SENSOR_SIGNAL,
    DOMAIN,
    ROLE_UPDATE_SIGNAL,
    RT_VHH,
    UPDATE_VHH_SIGNAL,
)
from homeassistant.components.powersensor.sensor import async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from tests.common import MockConfigEntry

logging.getLogger().setLevel(logging.CRITICAL)
MAC = "a4cf1218f158"
OTHER_MAC = "a4cf1218f159"


@pytest.fixture
def config_entry():
    """Return a mock config entry with populated runtime data.

    This fixture provides a basic config entry setup, including an empty dispatcher and sensor queue.
    It's intended to be used as a starting point for more specific setups in tests.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    runtime_data = {RT_VHH: VirtualHousehold(False), RT_DISPATCHER: AsyncMock()}
    runtime_data[RT_DISPATCHER].plugs = {}
    runtime_data[RT_DISPATCHER].on_start_sensor_queue = {}
    entry.runtime_data = runtime_data
    return entry


@pytest.mark.asyncio
async def test_setup_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test setup of an existing Powersensor config entry.

    This test verifies that:
    - The `async_setup_entry` function calls `update_entry` with the correct arguments.
    - The dispatcher sends a signal to update the VHH roles.
    - The signal handler is called correctly.
    """
    entry = config_entry
    async_update_entry = Mock()
    monkeypatch.setattr(hass.config_entries, "async_update_entry", async_update_entry)
    entities = []

    def callback(new_entities, *args, **kwargs):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, callback)
    mock_handler = Mock()
    async_dispatcher_connect(hass, UPDATE_VHH_SIGNAL, mock_handler)
    await hass.async_block_till_done()

    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(4):
        await hass.async_block_till_done()

    mock_handler.assert_called_once_with()


@pytest.mark.asyncio
async def test_discovered_sensor(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test discovery and creation of Powersensor entities.

    This test verifies that:
    - The correct number of entities are created when discovering a sensor.
    - Additional entities are correctly added for subsequent discoveries.
    """
    entry = config_entry
    async_update_entry = Mock()
    monkeypatch.setattr(hass.config_entries, "async_update_entry", async_update_entry)
    entities = []

    def callback(new_entities, *args, **kwargs):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, callback)
    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, "house-net")
    for _ in range(10):
        await hass.async_block_till_done()

    # check that the right number of entities have been added
    assert len(entities) == 5
    # @todo: check that the correct entities are created

    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, OTHER_MAC, "solar")
    await hass.async_block_till_done()
    # check that the right number of additional entities have been added
    assert len(entities) == 10


@pytest.mark.asyncio
async def test_initially_known_plugs_and_sensors(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test setup of PowerSensor config entry with pre-existing plugs and sensors.

    This test verifies that:
    - The correct number of entities are created based on the existing configuration.
    """
    entry = config_entry
    entry.runtime_data[RT_DISPATCHER].plugs[MAC] = None
    entry.runtime_data[RT_DISPATCHER].on_start_sensor_queue[OTHER_MAC] = "house-net"
    async_update_entry = Mock()
    monkeypatch.setattr(hass.config_entries, "async_update_entry", async_update_entry)
    entities = []

    def callback(new_entities, *args, **kwargs):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, callback)

    assert len(entities) == 12
