"""Tests for the pvpc_hourly_pricing sensor component."""
from datetime import datetime, timedelta
import logging

from freezegun import freeze_time

from homeassistant.components.pvpc_hourly_pricing import (
    ATTR_POWER,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    DOMAIN,
    TARIFFS,
)
from homeassistant.const import CONF_NAME

from .conftest import check_valid_state

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    date_util,
    mock_registry,
)
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_multi_sensor_migration(
    hass, caplog, pvpc_aioclient_mock: AiohttpClientMocker
):
    """Test tariff migration when there are >1 old sensors."""
    entity_reg = mock_registry(hass)
    hass.config.set_time_zone("Europe/Madrid")
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

    mock_data = {"return_time": datetime(2021, 6, 1, 21, tzinfo=date_util.UTC)}

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        with freeze_time(mock_data["return_time"]):
            assert await hass.config_entries.async_setup(config_entry_1.entry_id)
            assert any("Migrating PVPC" in message for message in caplog.messages)
            assert any(
                "Old PVPC Sensor sensor.test_pvpc_2 is removed" in message
                for message in caplog.messages
            )

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

            # check state and availability
            state = hass.states.get("sensor.test_pvpc_1")
            check_valid_state(state, tariff=TARIFFS[0], value=0.1565)

        with freeze_time(mock_data["return_time"] + timedelta(minutes=60)):
            async_fire_time_changed(hass, mock_data["return_time"])
            await list(hass.data[DOMAIN].values())[0].async_refresh()
            await hass.async_block_till_done()
            state = hass.states.get("sensor.test_pvpc_1")
            check_valid_state(state, tariff=TARIFFS[0], value="unavailable")
            assert pvpc_aioclient_mock.call_count == 3
