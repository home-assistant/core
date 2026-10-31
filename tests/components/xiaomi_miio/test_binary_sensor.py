"""Tests for Xiaomi Miio binary sensors (humidifier)."""

from unittest.mock import MagicMock, patch

from homeassistant.components.binary_sensor import DOMAIN as BINARY_DOMAIN
from homeassistant.components.xiaomi_miio import UPDATE_INTERVAL
from homeassistant.components.xiaomi_miio.const import CONF_FLOW_TYPE, DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import TEST_MAC

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_humidifier_binary_sensors(hass: HomeAssistant) -> None:
    """Test that binary sensors for JSQS humidifier are created and update."""

    model = "deerma.humidifier.jsqs"

    mock_device = MagicMock()
    status = MagicMock()

    status.tank_filed = True
    status.water_shortage_fault = False
    mock_device.status.return_value = status

    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[BINARY_DOMAIN],
        ),
        patch(
            "homeassistant.components.xiaomi_miio.AirHumidifierJsqs",
            return_value=mock_device,
        ),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="123456",
            title="test_humidifier",
            data={
                CONF_FLOW_TYPE: CONF_DEVICE,
                CONF_HOST: "192.168.1.100",
                CONF_TOKEN: "token",
                CONF_MODEL: model,
                CONF_MAC: TEST_MAC,
            },
        )

        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        binary_ids = hass.states.async_entity_ids(BINARY_DOMAIN)

        tank_entity = next(
            entity_id
            for entity_id in binary_ids
            if ("tank_filed" in entity_id or "water_tank" in entity_id)
        )
        water_shortage = next(
            entity_id for entity_id in binary_ids if "water_shortage_fault" in entity_id
        )

        state_tank = hass.states.get(tank_entity)
        state_water_shortage = hass.states.get(water_shortage)
        assert state_tank is not None
        assert state_water_shortage is not None
        assert state_tank.state == "off"
        assert state_water_shortage.state == "off"

        status.tank_filed = False
        status.water_shortage_fault = True

        async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state_tank_updated = hass.states.get(tank_entity)
        state_water_shortage_updated = hass.states.get(water_shortage)
        assert state_tank_updated.state == "on"
        assert state_water_shortage_updated.state == "on"
