"""Test for the LCN services."""

from unittest.mock import patch

import pypck
import pytest

from homeassistant.components.lcn import DOMAIN
from homeassistant.components.lcn.const import (
    CONF_KEYS,
    CONF_LED,
    CONF_OUTPUT,
    CONF_PCK,
    CONF_RELVARREF,
    CONF_ROW,
    CONF_SETPOINT,
    CONF_TABLE,
    CONF_TEXT,
    CONF_TIME,
    CONF_TIME_UNIT,
    CONF_TRANSITION,
    CONF_VALUE,
    CONF_VARIABLE,
)
from homeassistant.components.lcn.services import LcnService
from homeassistant.const import (
    CONF_BRIGHTNESS,
    CONF_DEVICE_ID,
    CONF_STATE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    MockConfigEntry,
    MockModuleConnection,
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

    with patch.object(MockModuleConnection, "dim_output") as dim_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_ABS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_OUTPUT: "output1",
                CONF_BRIGHTNESS: 100,
                CONF_TRANSITION: 5,
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

    with patch.object(MockModuleConnection, "rel_output") as rel_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_REL,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_OUTPUT: "output1",
                CONF_BRIGHTNESS: 25,
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

    with patch.object(MockModuleConnection, "toggle_output") as toggle_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_TOGGLE,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_OUTPUT: "output1",
                CONF_TRANSITION: 5,
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

    with patch.object(MockModuleConnection, "control_relays") as control_relays:
        await hass.services.async_call(
            DOMAIN,
            LcnService.RELAYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_STATE: "0011TT--",
            },
            blocking=True,
        )

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    relay_states = [pypck.lcn_defs.RelayStateModifier[state] for state in states]

    control_relays.assert_awaited_with(relay_states)


async def test_service_led(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test led service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "control_led") as control_led:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LED,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_LED: "led6",
                CONF_STATE: "blink",
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

    with patch.object(MockModuleConnection, "var_abs") as var_abs:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_ABS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_VARIABLE: "var1",
                CONF_VALUE: 75,
                CONF_UNIT_OF_MEASUREMENT: "%",
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

    with patch.object(MockModuleConnection, "var_rel") as var_rel:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_REL,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_VARIABLE: "var1",
                CONF_VALUE: 10,
                CONF_UNIT_OF_MEASUREMENT: "%",
                CONF_RELVARREF: "current",
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

    with patch.object(MockModuleConnection, "var_reset") as var_reset:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_RESET,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_VARIABLE: "var1",
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

    with patch.object(MockModuleConnection, "lock_regulator") as lock_regulator:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_REGULATOR,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_SETPOINT: "r1varsetpoint",
                CONF_STATE: True,
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

    with patch.object(MockModuleConnection, "send_keys") as send_keys:
        await hass.services.async_call(
            DOMAIN,
            LcnService.SEND_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_KEYS: "a1a5d8",
                CONF_STATE: "hit",
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
        MockModuleConnection, "send_keys_hit_deferred"
    ) as send_keys_hit_deferred:
        await hass.services.async_call(
            DOMAIN,
            LcnService.SEND_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_KEYS: "a1a5d8",
                CONF_TIME: 5,
                CONF_TIME_UNIT: "s",
            },
            blocking=True,
        )

    send_keys_hit_deferred.assert_awaited_with(
        keys, 5, pypck.lcn_defs.TimeUnit.parse("S")
    )

    # wrong key action
    with (
        patch.object(
            MockModuleConnection, "send_keys_hit_deferred"
        ) as send_keys_hit_deferred,
        pytest.raises(ValueError),
    ):
        await hass.services.async_call(
            DOMAIN,
            LcnService.SEND_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_KEYS: "a1a5d8",
                CONF_STATE: "make",
                CONF_TIME: 5,
                CONF_TIME_UNIT: "s",
            },
            blocking=True,
        )


async def test_service_lock_keys(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test lock_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_keys") as lock_keys:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_TABLE: "a",
                CONF_STATE: "0011TT--",
            },
            blocking=True,
        )

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    lock_states = [pypck.lcn_defs.KeyLockStateModifier[state] for state in states]

    lock_keys.assert_awaited_with(0, lock_states)


async def test_service_lock_keys_tab_a_temporary(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test lock_keys (tab_a_temporary) service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    # success
    with patch.object(
        MockModuleConnection, "lock_keys_tab_a_temporary"
    ) as lock_keys_tab_a_temporary:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_STATE: "0011TT--",
                CONF_TIME: 10,
                CONF_TIME_UNIT: "s",
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
            MockModuleConnection, "lock_keys_tab_a_temporary"
        ) as lock_keys_tab_a_temporary,
        pytest.raises(ValueError),
    ):
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_KEYS,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_TABLE: "b",
                CONF_STATE: "0011TT--",
                CONF_TIME: 10,
                CONF_TIME_UNIT: "s",
            },
            blocking=True,
        )


async def test_service_dyn_text(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test dyn_text service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "dyn_text") as dyn_text:
        await hass.services.async_call(
            DOMAIN,
            LcnService.DYN_TEXT,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_ROW: 1,
                CONF_TEXT: "text in row 1",
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

    with patch.object(MockModuleConnection, "pck") as pck:
        await hass.services.async_call(
            DOMAIN,
            LcnService.PCK,
            {
                CONF_DEVICE_ID: get_device(hass, entry, (0, 7, False)).id,
                CONF_PCK: "PIN4",
            },
            blocking=True,
        )

    pck.assert_awaited_with("PIN4")
