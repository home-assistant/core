"""Test opentherm_gw switches."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, call

from homeassistant.components.opentherm_gw import DOMAIN as OPENTHERM_DOMAIN
from homeassistant.components.opentherm_gw.const import OpenThermDeviceIdentifier
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_ch_override_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test central heating override switch."""

    mock_pyotgw.return_value.set_ch_enable_bit = AsyncMock(side_effect=[0, 1])
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        switch_entity_id := entity_registry.async_get_entity_id(
            SWITCH_DOMAIN,
            OPENTHERM_DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-central_heating_1_override",
        )
    ) is not None

    assert (entity_entry := entity_registry.async_get(switch_entity_id)) is not None
    assert entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    entity_registry.async_update_entity(switch_entity_id, disabled_by=None)

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()
    assert hass.states.get(switch_entity_id).state == STATE_UNKNOWN

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: switch_entity_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(switch_entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: switch_entity_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(switch_entity_id).state == STATE_ON

    assert mock_pyotgw.return_value.set_ch_enable_bit.await_count == 2
    mock_pyotgw.return_value.set_ch_enable_bit.assert_has_awaits([call(0), call(1)])


async def test_ch2_override_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test central heating 2 override switch."""

    mock_pyotgw.return_value.set_ch2_enable_bit = AsyncMock(side_effect=[0, 1])
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        switch_entity_id := entity_registry.async_get_entity_id(
            SWITCH_DOMAIN,
            OPENTHERM_DOMAIN,
            f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.GATEWAY}-central_heating_2_override",
        )
    ) is not None

    assert (entity_entry := entity_registry.async_get(switch_entity_id)) is not None
    assert entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    entity_registry.async_update_entity(switch_entity_id, disabled_by=None)

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

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
    await hass.async_block_till_done()
    assert hass.states.get(switch_entity_id).state == STATE_ON

    assert mock_pyotgw.return_value.set_ch2_enable_bit.await_count == 2
    mock_pyotgw.return_value.set_ch2_enable_bit.assert_has_awaits([call(0), call(1)])
