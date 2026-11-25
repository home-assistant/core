"""Test for the LCN services."""

from unittest.mock import patch

import pypck
import pytest

from homeassistant.components.lcn import DOMAIN
from homeassistant.components.lcn.services import LcnService, LcnServiceArgument
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from .conftest import (
    MockConfigEntry,
    MockDeviceConnection,
    get_device,
    init_integration,
)


async def test_service_output_abs(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test output_abs service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "dim_output") as dim_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_ABS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.OUTPUT: "output1",
                LcnServiceArgument.BRIGHTNESS: 100,
                LcnServiceArgument.TRANSITION: 5,
            },
            blocking=True,
        )

    dim_output.assert_awaited_with(0, 100, 9)


async def test_service_output_rel(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test output_rel service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "rel_output") as rel_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_REL,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.OUTPUT: "output1",
                LcnServiceArgument.BRIGHTNESS: 25,
            },
            blocking=True,
        )

    rel_output.assert_awaited_with(0, 25)


async def test_service_output_toggle(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test output_toggle service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "toggle_output") as toggle_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_TOGGLE,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.OUTPUT: "output1",
                LcnServiceArgument.TRANSITION: 5,
            },
            blocking=True,
        )

    toggle_output.assert_awaited_with(0, 9)


async def test_service_relays(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test relays service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "control_relays") as control_relays:
        await hass.services.async_call(
            DOMAIN,
            LcnService.RELAYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.STATE: "0011TT--",
            },
            blocking=True,
        )

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    relay_states = [pypck.lcn_defs.RelayStateModifier[state] for state in states]

    control_relays.assert_awaited_with(relay_states)

    # wrong states string
    with (
        patch.object(MockDeviceConnection, "control_relays") as control_relays,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            LcnService.RELAYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.STATE: "0011TT--00",
            },
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_length_of_states_string"


async def test_service_led(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test led service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "control_led") as control_led:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LED,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.LED: "led6",
                LcnServiceArgument.STATE: "blink",
            },
            blocking=True,
        )

    led = pypck.lcn_defs.LedPort["LED6"]
    led_state = pypck.lcn_defs.LedStatus["BLINK"]

    control_led.assert_awaited_with(led, led_state)


async def test_service_var_abs(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test var_abs service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "var_abs") as var_abs:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_ABS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.VARIABLE: "var1",
                LcnServiceArgument.VALUE: 75,
                LcnServiceArgument.UNIT_OF_MEASUREMENT: "%",
            },
            blocking=True,
        )

    var_abs.assert_awaited_with(
        pypck.lcn_defs.Var["VAR1"], 75, pypck.lcn_defs.VarUnit.parse("%")
    )


async def test_service_var_rel(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test var_rel service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "var_rel") as var_rel:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_REL,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.VARIABLE: "var1",
                LcnServiceArgument.VALUE: 10,
                LcnServiceArgument.UNIT_OF_MEASUREMENT: "%",
                LcnServiceArgument.VALUE_REFERENCE: "current",
            },
            blocking=True,
        )

    var_rel.assert_awaited_with(
        pypck.lcn_defs.Var["VAR1"],
        10,
        pypck.lcn_defs.VarUnit.parse("%"),
        pypck.lcn_defs.RelVarRef["CURRENT"],
    )


async def test_service_var_reset(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test var_reset service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "var_reset") as var_reset:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_RESET,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.VARIABLE: "var1",
            },
            blocking=True,
        )

    var_reset.assert_awaited_with(pypck.lcn_defs.Var["VAR1"])


async def test_service_lock_regulator(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test lock_regulator service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "lock_regulator") as lock_regulator:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_REGULATOR,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.SETPOINT: "r1varsetpoint",
                LcnServiceArgument.STATE: True,
            },
            blocking=True,
        )

    lock_regulator.assert_awaited_with(0, True)


async def test_service_send_keys(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test send_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "send_keys") as send_keys:
        await hass.services.async_call(
            DOMAIN,
            LcnService.SEND_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.KEYS: "a1a5d8",
                LcnServiceArgument.STATE: "hit",
            },
            blocking=True,
        )

    keys = [[False] * 8 for i in range(4)]
    keys[0][0] = True
    keys[0][4] = True
    keys[3][7] = True

    send_keys.assert_awaited_with(keys, pypck.lcn_defs.SendKeyCommand["HIT"])


async def test_service_send_keys_hit_deferred(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test send_keys (hit_deferred) service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    keys = [[False] * 8 for i in range(4)]
    keys[0][0] = True
    keys[0][4] = True
    keys[3][7] = True

    # success
    with patch.object(
        MockDeviceConnection, "send_keys_hit_deferred"
    ) as send_keys_hit_deferred:
        await hass.services.async_call(
            DOMAIN,
            LcnService.SEND_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.KEYS: "a1a5d8",
                LcnServiceArgument.TIME: 5,
                LcnServiceArgument.TIME_UNIT: "s",
            },
            blocking=True,
        )

    send_keys_hit_deferred.assert_awaited_with(
        keys, 5, pypck.lcn_defs.TimeUnit.parse("S")
    )

    # wrong key action
    with (
        patch.object(
            MockDeviceConnection, "send_keys_hit_deferred"
        ) as send_keys_hit_deferred,
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            LcnService.SEND_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.KEYS: "a1a5d8",
                LcnServiceArgument.STATE: "make",
                LcnServiceArgument.TIME: 5,
                LcnServiceArgument.TIME_UNIT: "s",
            },
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_send_keys_action"


async def test_service_lock_keys(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test lock_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "lock_keys") as lock_keys:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.TABLE: "a",
                LcnServiceArgument.STATE: "0011TT--",
            },
            blocking=True,
        )

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    lock_states = [pypck.lcn_defs.KeyLockStateModifier[state] for state in states]

    lock_keys.assert_awaited_with(0, lock_states)

    # wrong states string
    with (
        patch.object(MockDeviceConnection, "lock_keys") as lock_keys,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.TABLE: "a",
                LcnServiceArgument.STATE: "0011TT--00",
            },
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_length_of_states_string"


async def test_service_lock_keys_tab_a_temporary(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test lock_keys (tab_a_temporary) service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    # success
    with patch.object(
        MockDeviceConnection, "lock_keys_tab_a_temporary"
    ) as lock_keys_tab_a_temporary:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.STATE: "0011TT--",
                LcnServiceArgument.TIME: 10,
                LcnServiceArgument.TIME_UNIT: "s",
            },
            blocking=True,
        )

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    lock_states = [pypck.lcn_defs.KeyLockStateModifier[state] for state in states]

    lock_keys_tab_a_temporary.assert_awaited_with(
        10, pypck.lcn_defs.TimeUnit.parse("S"), lock_states
    )

    # wrong table
    with (
        patch.object(
            MockDeviceConnection, "lock_keys_tab_a_temporary"
        ) as lock_keys_tab_a_temporary,
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.TABLE: "b",
                LcnServiceArgument.STATE: "0011TT--",
                LcnServiceArgument.TIME: 10,
                LcnServiceArgument.TIME_UNIT: "s",
            },
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_lock_keys_table"


async def test_service_dyn_text(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test dyn_text service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "dyn_text") as dyn_text:
        await hass.services.async_call(
            DOMAIN,
            LcnService.DYN_TEXT,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.ROW: 1,
                LcnServiceArgument.TEXT: "text in row 1",
            },
            blocking=True,
        )

    dyn_text.assert_awaited_with(0, "text in row 1")


async def test_service_pck(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test pck service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockDeviceConnection, "pck") as pck:
        await hass.services.async_call(
            DOMAIN,
            LcnService.PCK,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                LcnServiceArgument.PCK: "PIN4",
            },
            blocking=True,
        )

    pck.assert_awaited_with("PIN4")


async def test_service_unknown_device_id(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test service call with an unknown device id raises."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            LcnService.PCK,
            {
                CONF_DEVICE_ID: "unknown_device_id",
                LcnServiceArgument.PCK: "PIN4",
            },
            blocking=True,
        )
    assert exc_info.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert exc_info.value.translation_key == "service_device_not_found"


async def test_service_unloaded_config_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test service call to a device of an unloaded config entry raises."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)
    device_id = get_device(hass, entry, (0, 7, False)).id
    assert await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            LcnService.PCK,
            {
                CONF_DEVICE_ID: device_id,
                LcnServiceArgument.PCK: "PIN4",
            },
            blocking=True,
        )
    assert exc_info.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert exc_info.value.translation_key == "service_config_entry_not_loaded"
