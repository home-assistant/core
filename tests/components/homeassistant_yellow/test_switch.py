"""Test the Home Assistant Yellow switch platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_yellow import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, MockModule, mock_integration

API_DATA = {"disk_led": True, "heartbeat_led": True, "power_led": True}


@pytest.mark.parametrize(
    ("key", "name"),
    (
        ("disk_led", "Disk LED"),
        ("heartbeat_led", "Heartbeat LED"),
        ("power_led", "Power LED"),
    ),
)
async def test_switch_platform(hass: HomeAssistant, addon_store_info, key, name):
    """Test switch platform."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.homeassistant_yellow.get_os_info",
        return_value={"board": "yellow"},
    ), patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=True
    ), patch(
        "homeassistant.components.homeassistant_yellow.async_get_yellow_settings",
        return_value=API_DATA,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, DOMAIN)}
    )
    assert device is not None
    assert device.name == "Yellow"
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, key)
    assert entity_id is not None
    entity = entity_registry.async_get(entity_id)
    assert entity.has_entity_name is True
    assert entity.original_name == name

    state = hass.states.get(entity_id)
    assert state.state == "on"
    assert state.attributes == {
        "device_class": "switch",
        "friendly_name": f"Yellow {name}",
    }

    with patch(
        "homeassistant.components.homeassistant_yellow.switch.async_set_yellow_settings",
        return_value=API_DATA,
    ) as mock_set_yellow_settings:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        expected_params = {**API_DATA, key: False}
        mock_set_yellow_settings.assert_awaited_once_with(hass, expected_params)

    with patch(
        "homeassistant.components.homeassistant_yellow.switch.async_set_yellow_settings",
        return_value=API_DATA,
    ) as mock_set_yellow_settings:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        expected_params = {**API_DATA, key: True}
        mock_set_yellow_settings.assert_awaited_once_with(hass, expected_params)
