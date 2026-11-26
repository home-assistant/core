"""Tests for Daikin climate commands that fail."""

from aiohttp import ServerDisconnectedError
from pydaikin.exceptions import DaikinException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    HVACMode,
)
from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ZoneDevice


async def _async_setup(hass: HomeAssistant, zone_device: ZoneDevice) -> None:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=zone_device.mac,
        data={CONF_HOST: "127.0.0.1", KEY_MAC: zone_device.mac},
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (ServerDisconnectedError(), "Server disconnected"),
        (DaikinException("rejected"), "rejected"),
        (TimeoutError(), "TimeoutError"),
    ],
)
async def test_set_hvac_mode_raises_a_clear_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    error: Exception,
    message: str,
) -> None:
    """A command the device doesn't take raises a translated error, not a crash."""
    await _async_setup(hass, zone_device)
    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, zone_device.mac
    )
    assert entity_id is not None
    zone_device.set.side_effect = error

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "error_communicating"
    assert err.value.translation_placeholders == {"error": message}


async def test_switch_command_raises_a_clear_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Switches report a failed command the same way."""
    await _async_setup(hass, zone_device)
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{zone_device.mac}-zone0"
    )
    assert entity_id is not None
    zone_device.set_zone.side_effect = ServerDisconnectedError()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert err.value.translation_key == "error_communicating"
