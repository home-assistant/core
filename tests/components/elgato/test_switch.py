"""Tests for the Elgato switch platform."""
from unittest.mock import MagicMock

from elgato import ElgatoError
import pytest

from homeassistant.components.elgato.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_OFF,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.parametrize("device_fixtures", ["key-light-mini"]),
    pytest.mark.usefixtures("device_fixtures", "init_integration"),
]


async def test_battery_bypass(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_elgato: MagicMock,
) -> None:
    """Test the Elgato battery bypass switch."""
    state = hass.states.get("switch.frenck_studio_mode")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck Studio mode"
    assert state.attributes.get(ATTR_ICON) == "mdi:battery-off-outline"
    assert not state.attributes.get(ATTR_DEVICE_CLASS)

    entry = entity_registry.async_get("switch.frenck_studio_mode")
    assert entry
    assert entry.unique_id == "GW24L1A02987_bypass"
    assert entry.entity_category == EntityCategory.CONFIG

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }
    assert device_entry.entry_type is None
    assert device_entry.identifiers == {(DOMAIN, "GW24L1A02987")}
    assert device_entry.manufacturer == "Elgato"
    assert device_entry.model == "Elgato Key Light Mini"
    assert device_entry.name == "Frenck"
    assert device_entry.sw_version == "1.0.4 (229)"
    assert device_entry.hw_version == "202"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.frenck_studio_mode"},
        blocking=True,
    )

    assert len(mock_elgato.battery_bypass.mock_calls) == 1
    mock_elgato.battery_bypass.assert_called_once_with(on=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.frenck_studio_mode"},
        blocking=True,
    )

    assert len(mock_elgato.battery_bypass.mock_calls) == 2
    mock_elgato.battery_bypass.assert_called_with(on=False)

    mock_elgato.battery_bypass.side_effect = ElgatoError

    with pytest.raises(
        HomeAssistantError, match="An error occurred while updating the Elgato Light"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.frenck_studio_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(mock_elgato.battery_bypass.mock_calls) == 3

    with pytest.raises(
        HomeAssistantError, match="An error occurred while updating the Elgato Light"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.frenck_studio_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(mock_elgato.battery_bypass.mock_calls) == 4


async def test_battery_energy_saving(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_elgato: MagicMock,
) -> None:
    """Test the Elgato energy saving switch."""
    state = hass.states.get("switch.frenck_energy_saving")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck Energy saving"
    assert state.attributes.get(ATTR_ICON) == "mdi:leaf"
    assert not state.attributes.get(ATTR_DEVICE_CLASS)

    entry = entity_registry.async_get("switch.frenck_energy_saving")
    assert entry
    assert entry.unique_id == "GW24L1A02987_energy_saving"
    assert entry.entity_category == EntityCategory.CONFIG

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.frenck_energy_saving"},
        blocking=True,
    )

    assert len(mock_elgato.energy_saving.mock_calls) == 1
    mock_elgato.energy_saving.assert_called_once_with(on=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.frenck_energy_saving"},
        blocking=True,
    )

    assert len(mock_elgato.energy_saving.mock_calls) == 2
    mock_elgato.energy_saving.assert_called_with(on=False)
