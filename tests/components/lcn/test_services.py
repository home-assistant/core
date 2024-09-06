"""Test for the LCN services."""

from unittest.mock import patch

import pypck
import pytest

from homeassistant.components.lcn import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MockModuleConnection, MockPchkConnectionManager, setup_component


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_output_abs(hass: HomeAssistant) -> None:
    """Test output_abs service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "dim_output") as dim_output:
        await hass.services.async_call(
            DOMAIN,
            "output_abs",
            {
                "address": "pchk.s0.m7",
                "output": "output1",
                "brightness": 100,
                "transition": 5,
            },
            blocking=True,
        )

    dim_output.assert_awaited_with(0, 100, 9)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_output_rel(hass: HomeAssistant) -> None:
    """Test output_rel service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "rel_output") as rel_output:
        await hass.services.async_call(
            DOMAIN,
            "output_rel",
            {
                "address": "pchk.s0.m7",
                "output": "output1",
                "brightness": 25,
            },
            blocking=True,
        )

    rel_output.assert_awaited_with(0, 25)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_output_toggle(hass: HomeAssistant) -> None:
    """Test output_toggle service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "toggle_output") as toggle_output:
        await hass.services.async_call(
            DOMAIN,
            "output_toggle",
            {
                "address": "pchk.s0.m7",
                "output": "output1",
                "transition": 5,
            },
            blocking=True,
        )

    toggle_output.assert_awaited_with(0, 9)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_relays(hass: HomeAssistant) -> None:
    """Test relays service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "control_relays") as control_relays:
        await hass.services.async_call(
            DOMAIN,
            "relays",
            {"address": "pchk.s0.m7", "state": "0011TT--"},
            blocking=True,
        )

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    relay_states = [pypck.lcn_defs.RelayStateModifier[state] for state in states]

    control_relays.assert_awaited_with(relay_states)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_led(hass: HomeAssistant) -> None:
    """Test led service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "control_led") as control_led:
        await hass.services.async_call(
            DOMAIN,
            "led",
            {"address": "pchk.s0.m7", "led": "led6", "state": "blink"},
            blocking=True,
        )

    led = pypck.lcn_defs.LedPort["LED6"]
    led_state = pypck.lcn_defs.LedStatus["BLINK"]

    control_led.assert_awaited_with(led, led_state)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_var_abs(hass: HomeAssistant) -> None:
    """Test var_abs service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "var_abs") as var_abs:
        await hass.services.async_call(
            DOMAIN,
            "var_abs",
            {
                "address": "pchk.s0.m7",
                "variable": "var1",
                "value": 75,
                "unit_of_measurement": "%",
            },
            blocking=True,
        )

    var_abs.assert_awaited_with(
        pypck.lcn_defs.Var["VAR1"], 75, pypck.lcn_defs.VarUnit.parse("%")
    )


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_var_rel(hass: HomeAssistant) -> None:
    """Test var_rel service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "var_rel") as var_rel:
        await hass.services.async_call(
            DOMAIN,
            "var_rel",
            {
                "address": "pchk.s0.m7",
                "variable": "var1",
                "value": 10,
                "unit_of_measurement": "%",
                "value_reference": "current",
            },
            blocking=True,
        )

    var_rel.assert_awaited_with(
        pypck.lcn_defs.Var["VAR1"],
        10,
        pypck.lcn_defs.VarUnit.parse("%"),
        pypck.lcn_defs.RelVarRef["CURRENT"],
    )


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_var_reset(hass: HomeAssistant) -> None:
    """Test var_reset service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "var_reset") as var_reset:
        await hass.services.async_call(
            DOMAIN,
            "var_reset",
            {"address": "pchk.s0.m7", "variable": "var1"},
            blocking=True,
        )

    var_reset.assert_awaited_with(pypck.lcn_defs.Var["VAR1"])


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_lock_regulator(hass: HomeAssistant) -> None:
    """Test lock_regulator service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "lock_regulator") as lock_regulator:
        await hass.services.async_call(
            DOMAIN,
            "lock_regulator",
            {"address": "pchk.s0.m7", "setpoint": "r1varsetpoint", "state": True},
            blocking=True,
        )

    lock_regulator.assert_awaited_with(0, True)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_send_keys(hass: HomeAssistant) -> None:
    """Test send_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "send_keys") as send_keys:
        await hass.services.async_call(
            DOMAIN,
            "send_keys",
            {"address": "pchk.s0.m7", "keys": "a1a5d8", "state": "hit"},
            blocking=True,
        )

    keys = [[False] * 8 for i in range(4)]
    keys[0][0] = True
    keys[0][4] = True
    keys[3][7] = True

    send_keys.assert_awaited_with(keys, pypck.lcn_defs.SendKeyCommand["HIT"])


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_send_keys_hit_deferred(hass: HomeAssistant) -> None:
    """Test send_keys (hit_deferred) service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

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
            "send_keys",
            {"address": "pchk.s0.m7", "keys": "a1a5d8", "time": 5, "time_unit": "s"},
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
            "send_keys",
            {
                "address": "pchk.s0.m7",
                "keys": "a1a5d8",
                "state": "make",
                "time": 5,
                "time_unit": "s",
            },
            blocking=True,
        )


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_lock_keys(hass: HomeAssistant) -> None:
    """Test lock_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "lock_keys") as lock_keys:
        await hass.services.async_call(
            DOMAIN,
            "lock_keys",
            {"address": "pchk.s0.m7", "table": "a", "state": "0011TT--"},
            blocking=True,
        )

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    lock_states = [pypck.lcn_defs.KeyLockStateModifier[state] for state in states]
    lock_keys.assert_awaited_with(0, lock_states)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_lock_keys_tab_a_temporary(hass: HomeAssistant) -> None:
    """Test lock_keys (tab_a_temporary) service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    states = ["OFF", "OFF", "ON", "ON", "TOGGLE", "TOGGLE", "NOCHANGE", "NOCHANGE"]
    lock_states = [pypck.lcn_defs.KeyLockStateModifier[state] for state in states]

    # success
    with patch.object(
        MockModuleConnection, "lock_keys_tab_a_temporary"
    ) as lock_keys_tab_a_temporary:
        await hass.services.async_call(
            DOMAIN,
            "lock_keys",
            {
                "address": "pchk.s0.m7",
                "state": "0011TT--",
                "time": 10,
                "time_unit": "s",
            },
            blocking=True,
        )

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
            "lock_keys",
            {
                "address": "pchk.s0.m7",
                "table": "b",
                "state": "0011TT--",
                "time": 10,
                "time_unit": "s",
            },
            blocking=True,
        )


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_dyn_text(hass: HomeAssistant) -> None:
    """Test dyn_text service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "dyn_text") as dyn_text:
        await hass.services.async_call(
            DOMAIN,
            "dyn_text",
            {"address": "pchk.s0.m7", "row": 1, "text": "text in row 1"},
            blocking=True,
        )

    dyn_text.assert_awaited_with(0, "text in row 1")


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_pck(hass: HomeAssistant) -> None:
    """Test pck service."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "pck") as pck:
        await hass.services.async_call(
            DOMAIN,
            "pck",
            {"address": "pchk.s0.m7", "pck": "PIN4"},
            blocking=True,
        )

    pck.assert_awaited_with("PIN4")


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_called_with_invalid_host_id(hass: HomeAssistant) -> None:
    """Test service was called with non existing host id."""
    await async_setup_component(hass, "persistent_notification", {})
    await setup_component(hass)

    with patch.object(MockModuleConnection, "pck") as pck, pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            "pck",
            {"address": "foobar.s0.m7", "pck": "PIN4"},
            blocking=True,
        )

    pck.assert_not_awaited()
