"""Tests for the Rituals Perfume Genie switch platform."""

import logging

import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import (
    init_integration,
    mock_config_entry,
    mock_diffuser,
    mock_diffuser_v1_battery_cartridge,
)


async def test_switch_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the creation and values of the Rituals Perfume Genie diffuser switch."""
    config_entry = mock_config_entry(unique_id="id_123_switch_test")
    diffuser = mock_diffuser_v1_battery_cartridge()
    await init_integration(hass, config_entry, [diffuser])

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON

    entry = entity_registry.async_get("switch.genie")
    assert entry
    assert entry.unique_id == f"{diffuser.hublot}-is_on"


async def test_switch_handle_coordinator_update(hass: HomeAssistant) -> None:
    """Test handling a coordinator update."""
    config_entry = mock_config_entry(unique_id="switch_handle_coordinator_update_test")
    diffuser = mock_diffuser_v1_battery_cartridge()
    await init_integration(hass, config_entry, [diffuser])
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    coordinator = config_entry.runtime_data["lot123v1"]
    diffuser.is_on = False

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON

    call_count_before_update = diffuser.update_data.call_count

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["switch.genie"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_OFF

    assert coordinator.last_update_success
    assert diffuser.update_data.call_count == call_count_before_update + 1


async def test_device_info_sw_version_dict(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that sw_version is a string even when the library returns a dict."""
    diffuser = mock_diffuser(
        hublot="lot123dict",
        version={"id": 1, "title": "5.2-rc15", "icon": ""},
    )
    config_entry = mock_config_entry(unique_id="id_123_version_dict_test")
    with caplog.at_level(logging.WARNING, logger="homeassistant.helpers.frame"):
        await init_integration(hass, config_entry, [diffuser])

    device_entry = device_registry.async_get_device(
        identifiers={("rituals_perfume_genie", "lot123dict")}
    )
    assert device_entry
    assert device_entry.sw_version == "5.2-rc15"
    assert "non-string value" not in caplog.text


async def test_set_switch_state(hass: HomeAssistant) -> None:
    """Test changing the diffuser switch entity state."""
    config_entry = mock_config_entry(unique_id="id_123_switch_set_state_test")
    await init_integration(hass, config_entry, [mock_diffuser_v1_battery_cartridge()])

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.genie"},
        blocking=True,
    )

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.genie"},
        blocking=True,
    )

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON
