"""Test the Aladdin Connect Sensors."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.components.aladdin_connect.cover import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

YAML_CONFIG = {"username": "test-user", "password": "test-password"}
RELOAD_AFTER_UPDATE_DELAY = timedelta(seconds=31)


async def test_sensors(
    hass: HomeAssistant,
    mock_aladdinconnect_api: MagicMock,
) -> None:
    """Test Sensors for AladdinConnect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        registry = entity_registry.async_get(hass)
        entry = registry.async_get("sensor.home_battery_level")
        assert entry
        assert entry.disabled
        assert entry.disabled_by is entity_registry.RegistryEntryDisabler.INTEGRATION
        update_entry = registry.async_update_entity(
            entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert update_entry != entry
        assert update_entry.disabled is False
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()
        state = hass.states.get("sensor.home_battery_level")
        assert state

        entry = registry.async_get("sensor.home_wi_fi_rssi")
        await hass.async_block_till_done()
        assert entry
        assert entry.disabled
        assert entry.disabled_by is entity_registry.RegistryEntryDisabler.INTEGRATION
        update_entry = registry.async_update_entity(
            entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert update_entry != entry
        assert update_entry.disabled is False

        update_entry = registry.async_update_entity(
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
