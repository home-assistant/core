"""Tests for the Rituals Perfume Genie switch platform."""

import pytest
from ritualsgenie import (
    RitualsGenieAuthenticationError,
    RitualsGenieConnectionError,
    RitualsGenieError,
    RitualsGenieRateLimitError,
)

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    client = await init_integration(hass, config_entry, [diffuser])
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    coordinator = config_entry.runtime_data.hubs
    diffuser.is_on = False

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON

    call_count_before_update = client.hubs.call_count

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
    assert client.hubs.call_count == call_count_before_update + 1


async def test_device_info(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the device info, with the model and firmware from Rituals."""
    diffuser = mock_diffuser(hublot="lot123device", model="Genie 3.0", version="7.1")
    config_entry = mock_config_entry(unique_id="id_123_device_info_test")
    await init_integration(hass, config_entry, [diffuser])

    device_entry = device_registry.async_get_device_by_identifier(
        ("rituals_perfume_genie", "lot123device"), config_entry.entry_id
    )
    assert device_entry
    assert device_entry.name == "Genie"
    assert device_entry.model == "Genie 3.0"
    assert device_entry.sw_version == "7.1"


async def test_set_switch_state(hass: HomeAssistant) -> None:
    """Test changing the diffuser switch entity state."""
    config_entry = mock_config_entry(unique_id="id_123_switch_set_state_test")
    diffuser = mock_diffuser_v1_battery_cartridge()
    client = await init_integration(hass, config_entry, [diffuser])

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
    client.turn_off.assert_awaited_once_with(diffuser.hub_hash)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.genie"},
        blocking=True,
    )

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON
    client.turn_on.assert_awaited_once_with(diffuser.hub_hash)


async def test_standby_led(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test turning the standby LED of a diffuser on and off."""
    config_entry = mock_config_entry(unique_id="id_123_standby_led")
    diffuser = mock_diffuser(hublot="lot123", standby_led=False)
    client = await init_integration(hass, config_entry, [diffuser])

    state = hass.states.get("switch.genie_standby_led")
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("switch.genie_standby_led")
    assert entry
    assert entry.unique_id == "lot123-standby_led"
    assert entry.entity_category is EntityCategory.CONFIG

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.genie_standby_led"},
        blocking=True,
    )

    client.set_standby_led.assert_called_once_with(diffuser.hub_hash, enabled=True)
    state = hass.states.get("switch.genie_standby_led")
    assert state
    assert state.state == STATE_ON

    client.set_standby_led.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.genie_standby_led"},
        blocking=True,
    )

    client.set_standby_led.assert_called_once_with(diffuser.hub_hash, enabled=False)
    state = hass.states.get("switch.genie_standby_led")
    assert state
    assert state.state == STATE_OFF


async def test_standby_led_unsupported(hass: HomeAssistant) -> None:
    """Test a diffuser without a standby LED setting gets no switch for it."""
    config_entry = mock_config_entry(unique_id="id_123_standby_led_unsupported")
    await init_integration(
        hass, config_entry, [mock_diffuser(hublot="lot123", standby_led=None)]
    )

    assert hass.states.get("switch.genie") is not None
    assert hass.states.get("switch.genie_standby_led") is None


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (RitualsGenieConnectionError, "communication_error"),
        (RitualsGenieRateLimitError("Slow down", retry_after=60), "rate_limited"),
        (RitualsGenieError("Something odd"), "unknown_error"),
    ],
)
async def test_switch_action_error(
    hass: HomeAssistant, exception: Exception, translation_key: str
) -> None:
    """Test a failing action raises a translated error."""
    config_entry = mock_config_entry(unique_id="id_123_switch_action_error")
    client = await init_integration(hass, config_entry, [mock_diffuser("lot123")])
    client.turn_off.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.genie"},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON


async def test_switch_action_authentication_error(hass: HomeAssistant) -> None:
    """Test rejected credentials during an action start a reauthentication."""
    config_entry = mock_config_entry(unique_id="id_123_switch_action_auth")
    client = await init_integration(hass, config_entry, [mock_diffuser("lot123")])
    client.turn_off.side_effect = RitualsGenieAuthenticationError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.genie"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert exc_info.value.translation_key == "authentication_failed"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
