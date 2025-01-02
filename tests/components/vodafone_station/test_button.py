"""Tests for Vodafone Station button platform."""

from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import DEVICE_DATA_QUERY, MOCK_USER_DATA, SENSOR_DATA_QUERY, SERIAL

from tests.common import MockConfigEntry


async def test_button(hass: HomeAssistant, entity_registry: EntityRegistry) -> None:
    """Test device restart button."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch("aiovodafone.api.VodafoneStationSercommApi.login"),
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_devices_data",
            return_value=DEVICE_DATA_QUERY,
        ),
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_sensor_data",
            return_value=SENSOR_DATA_QUERY,
        ),
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.restart_router",
        ) as mock_router_restart,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = f"button.vodafone_station_{SERIAL}_restart"

        # restart button
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN

        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == f"{SERIAL}_reboot"

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        assert mock_router_restart.call_count == 1
