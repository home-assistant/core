"""Test opentherm_gw switches."""

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from homeassistant.components.opentherm_gw import DOMAIN as OPENTHERM_DOMAIN
from homeassistant.components.opentherm_gw.const import OpenThermDeviceIdentifier
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "entity_key", ["central_heating_1_override", "central_heating_2_override"]
)
async def test_switch_added_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
    entity_key: str,
) -> None:
    """Test switch gets added in disabled state."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        switch_entity_id := entity_registry.async_get_entity_id(
            SWITCH_DOMAIN,
            OPENTHERM_DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-{entity_key}",
        )
    ) is not None

    assert (entity_entry := entity_registry.async_get(switch_entity_id)) is not None
    assert entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_key", "target_func"),
    [
        ("central_heating_1_override", "set_ch_enable_bit"),
        ("central_heating_2_override", "set_ch2_enable_bit"),
    ],
)
async def test_ch_override_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
    entity_key: str,
    target_func: str,
) -> None:
    """Test central heating override switch."""

    setattr(mock_pyotgw.return_value, target_func, AsyncMock(side_effect=[0, 1]))
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        switch_entity_id := entity_registry.async_get_entity_id(
            SWITCH_DOMAIN,
            OPENTHERM_DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-{entity_key}",
        )
    ) is not None
    assert hass.states.get(switch_entity_id).state == STATE_UNKNOWN

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: switch_entity_id,
        },
        blocking=True,
    )
    assert hass.states.get(switch_entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: switch_entity_id,
        },
        blocking=True,
    )
    assert hass.states.get(switch_entity_id).state == STATE_ON

    mock_func = getattr(mock_pyotgw.return_value, target_func)
    assert mock_func.await_count == 2
    mock_func.assert_has_awaits([call(0), call(1)])
