"""Test for the LCN services."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

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
    CONF_ADDRESS,
    CONF_BRIGHTNESS,
    CONF_STATE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    MockConfigEntry,
    MockModuleConnection,
    MockPchkConnectionManager,
    init_integration,
)


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_output_abs(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test output_abs service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "dim_output") as dim_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_ABS,
            {
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_OUTPUT: "output1",
                CONF_BRIGHTNESS: 100,
                CONF_TRANSITION: 5,
            },
            blocking=True,
        )

    assert dim_output.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_output_rel(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test output_rel service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "rel_output") as rel_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_REL,
            {
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_OUTPUT: "output1",
                CONF_BRIGHTNESS: 25,
            },
            blocking=True,
        )

    assert rel_output.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_output_toggle(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test output_toggle service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "toggle_output") as toggle_output:
        await hass.services.async_call(
            DOMAIN,
            LcnService.OUTPUT_TOGGLE,
            {
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_OUTPUT: "output1",
                CONF_TRANSITION: 5,
            },
            blocking=True,
        )

    assert toggle_output.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_relays(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test relays service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "control_relays") as control_relays:
        await hass.services.async_call(
            DOMAIN,
            LcnService.RELAYS,
            {CONF_ADDRESS: "pchk.s0.m7", CONF_STATE: "0011TT--"},
            blocking=True,
        )

    assert control_relays.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_led(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test led service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "control_led") as control_led:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LED,
            {CONF_ADDRESS: "pchk.s0.m7", CONF_LED: "led6", CONF_STATE: "blink"},
            blocking=True,
        )

    assert control_led.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_var_abs(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test var_abs service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "var_abs") as var_abs:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_ABS,
            {
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_VARIABLE: "var1",
                CONF_VALUE: 75,
                CONF_UNIT_OF_MEASUREMENT: "%",
            },
            blocking=True,
        )

    assert var_abs.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_var_rel(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test var_rel service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "var_rel") as var_rel:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_REL,
            {
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_VARIABLE: "var1",
                CONF_VALUE: 10,
                CONF_UNIT_OF_MEASUREMENT: "%",
                CONF_RELVARREF: "current",
            },
            blocking=True,
        )

    assert var_rel.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_var_reset(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test var_reset service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "var_reset") as var_reset:
        await hass.services.async_call(
            DOMAIN,
            LcnService.VAR_RESET,
            {CONF_ADDRESS: "pchk.s0.m7", CONF_VARIABLE: "var1"},
            blocking=True,
        )

    assert var_reset.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_lock_regulator(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test lock_regulator service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_regulator") as lock_regulator:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_REGULATOR,
            {
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_SETPOINT: "r1varsetpoint",
                CONF_STATE: True,
            },
            blocking=True,
        )

    assert lock_regulator.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_send_keys(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test send_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "send_keys") as send_keys:
        await hass.services.async_call(
            DOMAIN,
            LcnService.SEND_KEYS,
            {CONF_ADDRESS: "pchk.s0.m7", CONF_KEYS: "a1a5d8", CONF_STATE: "hit"},
            blocking=True,
        )

    keys = [[False] * 8 for i in range(4)]
    keys[0][0] = True
    keys[0][4] = True
    keys[3][7] = True

    assert send_keys.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_send_keys_hit_deferred(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
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
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_KEYS: "a1a5d8",
                CONF_TIME: 5,
                CONF_TIME_UNIT: "s",
            },
            blocking=True,
        )

    assert send_keys_hit_deferred.await_args.args == snapshot()

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
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_KEYS: "a1a5d8",
                CONF_STATE: "make",
                CONF_TIME: 5,
                CONF_TIME_UNIT: "s",
            },
            blocking=True,
        )


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_lock_keys(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test lock_keys service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "lock_keys") as lock_keys:
        await hass.services.async_call(
            DOMAIN,
            LcnService.LOCK_KEYS,
            {CONF_ADDRESS: "pchk.s0.m7", CONF_TABLE: "a", CONF_STATE: "0011TT--"},
            blocking=True,
        )

    assert lock_keys.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_lock_keys_tab_a_temporary(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
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
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_STATE: "0011TT--",
                CONF_TIME: 10,
                CONF_TIME_UNIT: "s",
            },
            blocking=True,
        )

    assert lock_keys_tab_a_temporary.await_args.args == snapshot()

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
                CONF_ADDRESS: "pchk.s0.m7",
                CONF_TABLE: "b",
                CONF_STATE: "0011TT--",
                CONF_TIME: 10,
                CONF_TIME_UNIT: "s",
            },
            blocking=True,
        )


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_dyn_text(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test dyn_text service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "dyn_text") as dyn_text:
        await hass.services.async_call(
            DOMAIN,
            LcnService.DYN_TEXT,
            {CONF_ADDRESS: "pchk.s0.m7", CONF_ROW: 1, CONF_TEXT: "text in row 1"},
            blocking=True,
        )

    assert dyn_text.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_pck(
    hass: HomeAssistant, entry: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test pck service."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "pck") as pck:
        await hass.services.async_call(
            DOMAIN,
            LcnService.PCK,
            {CONF_ADDRESS: "pchk.s0.m7", CONF_PCK: "PIN4"},
            blocking=True,
        )

    assert pck.await_args.args == snapshot()


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_service_called_with_invalid_host_id(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test service was called with non existing host id."""
    await async_setup_component(hass, "persistent_notification", {})
    await init_integration(hass, entry)

    with patch.object(MockModuleConnection, "pck") as pck, pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            LcnService.PCK,
            {CONF_ADDRESS: "foobar.s0.m7", CONF_PCK: "PIN4"},
            blocking=True,
        )

    pck.assert_not_awaited()
