"""Test the Aladdin Connect Sensors."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.components.aladdin_connect.cover import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

DEVICE_CONFIG_MODEL_01 = {
    "device_id": 533255,
    "door_number": 1,
    "name": "home",
    "status": "closed",
    "link_status": "Connected",
    "serial": "12345",
    "model": "01",
}


CONFIG = {"username": "test-user", "password": "test-password"}
RELOAD_AFTER_UPDATE_DELAY = timedelta(seconds=31)


async def test_sensors(
    hass: HomeAssistant,
    mock_aladdinconnect_api: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Sensors for AladdinConnect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)

    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entry = entity_registry.async_get("sensor.home_battery_level")
        assert entry
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        update_entry = entity_registry.async_update_entity(
            entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert update_entry != entry
        assert update_entry.disabled is False
        state = hass.states.get("sensor.home_battery_level")
        assert state is None

        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()
        state = hass.states.get("sensor.home_battery_level")
        assert state

        entry = entity_registry.async_get("sensor.home_wi_fi_rssi")
        await hass.async_block_till_done()
        assert entry
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        update_entry = entity_registry.async_update_entity(
            entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert update_entry != entry
        assert update_entry.disabled is False
        state = hass.states.get("sensor.home_wi_fi_rssi")
        assert state is None

        update_entry = entity_registry.async_update_entity(
            entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_wi_fi_rssi")
        assert state


async def test_sensors_model_01(
    hass: HomeAssistant,
    mock_aladdinconnect_api: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Sensors for AladdinConnect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)

    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        mock_aladdinconnect_api.get_doors = AsyncMock(
            return_value=[DEVICE_CONFIG_MODEL_01]
        )
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entry = entity_registry.async_get("sensor.home_battery_level")
        assert entry
        assert entry.disabled is False
        assert entry.disabled_by is None
        state = hass.states.get("sensor.home_battery_level")
        assert state

        entry = entity_registry.async_get("sensor.home_wi_fi_rssi")
        await hass.async_block_till_done()
        assert entry
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        update_entry = entity_registry.async_update_entity(
            entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert update_entry != entry
        assert update_entry.disabled is False
        state = hass.states.get("sensor.home_wi_fi_rssi")
        assert state is None

        update_entry = entity_registry.async_update_entity(
            entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_wi_fi_rssi")
        assert state

        entry = entity_registry.async_get("sensor.home_ble_strength")
        await hass.async_block_till_done()
        assert entry
        assert entry.disabled is False
        assert entry.disabled_by is None
        state = hass.states.get("sensor.home_ble_strength")
        assert state
