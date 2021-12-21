"""Tests for the pvpc_hourly_pricing sensor component."""
from datetime import datetime, timedelta
import logging
from unittest.mock import patch

from homeassistant.components.pvpc_hourly_pricing import (
    ATTR_POWER,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    DOMAIN,
    TARIFFS,
)
from homeassistant.const import CONF_NAME
from homeassistant.util import dt as dt_util

from .conftest import check_valid_state

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    date_util,
    mock_registry,
)
from tests.test_util.aiohttp import AiohttpClientMocker


async def _process_time_step(
    hass, mock_data, key_state=None, value=None, tariff=TARIFFS[0], delta_min=60
):
    await list(hass.data[DOMAIN].values())[0].async_refresh()
    state = hass.states.get("sensor.test_dst")
    check_valid_state(state, tariff=tariff, value=value, key_attr=key_state)

    mock_data["return_time"] += timedelta(minutes=delta_min)
    async_fire_time_changed(hass, mock_data["return_time"])
    await hass.async_block_till_done()
    return state


async def test_sensor_availability(
    hass, caplog, legacy_patchable_time, pvpc_aioclient_mock: AiohttpClientMocker
):
    """Test sensor availability and handling of cloud access."""
    hass.config.time_zone = dt_util.get_time_zone("Europe/Madrid")
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "test_dst", ATTR_TARIFF: "discrimination"}
    )
    config_entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    mock_data = {"return_time": datetime(2021, 10, 31, 20, 0, 0, tzinfo=date_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        # check migration
        current_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(current_entries) == 1
        migrated_entry = current_entries[0]
        assert migrated_entry.version == 1
        assert migrated_entry.data[ATTR_POWER] == migrated_entry.data[ATTR_POWER_P3]
        assert migrated_entry.data[ATTR_TARIFF] == TARIFFS[0]

        await hass.async_block_till_done()
        caplog.clear()
        assert pvpc_aioclient_mock.call_count == 2

        await _process_time_step(hass, mock_data, "price_21h", 0.16554)
        await _process_time_step(hass, mock_data, "price_22h", 0.15239)
        assert pvpc_aioclient_mock.call_count == 4
        await _process_time_step(hass, mock_data, "price_23h", 0.14612)
        assert pvpc_aioclient_mock.call_count == 5

        # sensor has no more prices, state is "unavailable" from now on
        await _process_time_step(hass, mock_data, value="unavailable")
        num_errors = sum(
            1
            for x in caplog.records
            if x.levelno == logging.ERROR and "unknown job listener" not in x.msg
        )
        assert num_errors == 1
        # check that it is silent until it becomes available again
        caplog.clear()
        with caplog.at_level(logging.INFO):
            # silent mode
            for _ in range(23):
                await _process_time_step(hass, mock_data, value="unavailable")
            assert pvpc_aioclient_mock.call_count == 29
            assert len(caplog.messages) == 0

            # working ok again
            await _process_time_step(hass, mock_data, "price_00h", value=0.13104)
            assert pvpc_aioclient_mock.call_count == 30
            assert len(caplog.messages) == 1
            assert caplog.records[0].levelno == logging.INFO
            await _process_time_step(hass, mock_data, "price_01h", value=0.12055)
            assert pvpc_aioclient_mock.call_count == 30


async def test_multi_sensor_migration(
    hass, caplog, legacy_patchable_time, pvpc_aioclient_mock: AiohttpClientMocker
):
    """Test tariff migration when there are >1 old sensors."""
    entity_reg = mock_registry(hass)
    hass.config.time_zone = dt_util.get_time_zone("Europe/Madrid")
    uid_1 = "discrimination"
    uid_2 = "normal"
    old_conf_1 = {CONF_NAME: "test_pvpc_1", ATTR_TARIFF: uid_1}
    old_conf_2 = {CONF_NAME: "test_pvpc_2", ATTR_TARIFF: uid_2}

    config_entry_1 = MockConfigEntry(domain=DOMAIN, data=old_conf_1, unique_id=uid_1)
    config_entry_1.add_to_hass(hass)
    entity1 = entity_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=uid_1,
        config_entry=config_entry_1,
        suggested_object_id="test_pvpc_1",
    )

    config_entry_2 = MockConfigEntry(domain=DOMAIN, data=old_conf_2, unique_id=uid_2)
    config_entry_2.add_to_hass(hass)
    entity2 = entity_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=uid_2,
        config_entry=config_entry_2,
        suggested_object_id="test_pvpc_2",
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert len(entity_reg.entities) == 2

    mock_data = {"return_time": datetime(2021, 10, 30, 20, tzinfo=date_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        with patch("homeassistant.util.dt.utcnow", new=mock_now):
            assert await hass.config_entries.async_setup(config_entry_1.entry_id)
            assert len(caplog.messages) == 2

            # check migration with removal of extra sensors
            assert len(entity_reg.entities) == 1
            assert entity1.entity_id in entity_reg.entities
            assert entity2.entity_id not in entity_reg.entities

            current_entries = hass.config_entries.async_entries(DOMAIN)
            assert len(current_entries) == 1
            migrated_entry = current_entries[0]
            assert migrated_entry.version == 1
            assert migrated_entry.data[ATTR_POWER] == migrated_entry.data[ATTR_POWER_P3]
            assert migrated_entry.data[ATTR_TARIFF] == TARIFFS[0]

            await hass.async_block_till_done()
            assert pvpc_aioclient_mock.call_count == 2
