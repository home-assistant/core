"""Tests of basic model and api interaction."""

from copy import copy
from unittest.mock import AsyncMock, Mock

from homeassistant.components.sunsynkweb import DOMAIN
from homeassistant.components.sunsynkweb.coordinator import PlantUpdateCoordinator
from homeassistant.components.sunsynkweb.sensor import async_setup_entry

from tests.common import MockConfigEntry


async def test_sensors(hass, basicdata):
    """Check end-to-end update to sensors works as expected."""
    config = MockConfigEntry(data={"username": "testuser", "password": "testpass"})
    coordinator = PlantUpdateCoordinator(hass, config)
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config.entry_id] = coordinator
    coordinator.session = AsyncMock()
    mockedjson_return = AsyncMock()
    mockedjson_return.name = "mocked_json_return"
    coordinator.session.get.return_value = mockedjson_return
    coordinator.session.post.return_value = mockedjson_return
    mockedjson_return.json.side_effect = basicdata
    await coordinator._async_update_data()
    async_add_entities = Mock()
    await async_setup_entry(hass, config, async_add_entities)
    sensors = async_add_entities.call_args[0][0]
    bpg, lpg, gpg, soc, pvg, pvea, lac, gexp, gimp, batch, batd = sensors
    assert bpg.native_value is None

    mockedjson_return.json.side_effect = basicdata[4:]
    await coordinator._async_update_data()
    for sensor in sensors:
        sensor.async_write_ha_state = Mock()
        sensor._handle_coordinator_update()
    assert bpg.native_value == -2
    return coordinator, lac, mockedjson_return


async def test_invalid_auth_in_update(hass, basicdata):
    "Check we cope with expired token in steady state."
    coordinator, lac, mockedjson = await test_sensors(hass, copy(basicdata))
    mockedjson = AsyncMock()
    mockedjson.json.side_effect = [
        {"code": 401, "msg": "expired token"},
        {"code": 401, "msg": "expired token"},
    ]

    coordinator.session.get.return_value = mockedjson
    coordinator.session.post.return_value = mockedjson
    assert lac.native_value == 12
    await coordinator._async_update_data()
    assert coordinator.bearer is None
    assert lac.native_value == 12
    mockedjson = AsyncMock()
    basicdata[-1]["data"]["totalUsed"] = 12
    del basicdata[3]
    del basicdata[2]
    del basicdata[1]
    coordinator.session.get.return_value = mockedjson
    coordinator.session.post.return_value = mockedjson
    mockedjson.json.side_effect = basicdata
    await coordinator._async_update_data()
    lac.async_write_ha_state = Mock()
    lac._handle_coordinator_update()
    assert lac.native_value == 18


async def test_emptysensors(hass, basicdata):
    """Check we run ok with empty sensors."""
    config = MockConfigEntry(data={"username": "testuser", "password": "testpass"})
    coordinator = PlantUpdateCoordinator(hass, config)
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config.entry_id] = coordinator
    coordinator.session = AsyncMock()
    mockedjson_return = AsyncMock()
    mockedjson_return.name = "mocked_json_return"
    coordinator.session.get.return_value = mockedjson_return
    coordinator.session.post.return_value = mockedjson_return
    mockedjson_return.json.side_effect = basicdata
    async_add_entities = Mock()
    await async_setup_entry(hass, config, async_add_entities)
    sensors = async_add_entities.call_args[0][0]
    bpg, lpg, gpg, soc, pvg, pvea, lac, gexp, gimp, batch, batd = sensors
    assert bpg.native_value is None
    for sensor in sensors:
        sensor.async_write_ha_state = Mock()
        sensor._handle_coordinator_update()
    assert bpg.native_value is None
