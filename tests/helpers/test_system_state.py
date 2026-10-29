"""Test the system state helper."""

from dataclasses import FrozenInstanceError

import pytest

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import system_state


async def test_home_assistant_restart_not_required(hass: HomeAssistant) -> None:
    """Test a fresh instance does not require a restart."""
    state = system_state.async_get(hass)

    assert not state.home_assistant_restart_required
    assert state.as_dict() == {
        "home_assistant_restart_dismissed": False,
        "home_assistant_restart_required": False,
        "home_assistant_restart_sources": [],
        "host_reboot_dismissed": False,
        "host_reboot_required": False,
    }


async def test_set_home_assistant_restart_required(hass: HomeAssistant) -> None:
    """Test integrations flag a restart, each listed once."""
    updates: list[dict[str, bool | list[str]]] = []
    system_state.async_subscribe(
        hass, callback(lambda state: updates.append(state.as_dict()))
    )

    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    system_state.async_set_home_assistant_restart_required(hass, "demo")

    # Asking again for the same integration changes nothing, so no update.
    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    await hass.async_block_till_done()

    assert system_state.async_get(hass).home_assistant_restart_required
    assert updates == [
        {
            "home_assistant_restart_dismissed": False,
            "home_assistant_restart_required": True,
            "home_assistant_restart_sources": ["hacs"],
            "host_reboot_dismissed": False,
            "host_reboot_required": False,
        },
        {
            "home_assistant_restart_dismissed": False,
            "home_assistant_restart_required": True,
            "home_assistant_restart_sources": ["demo", "hacs"],
            "host_reboot_dismissed": False,
            "host_reboot_required": False,
        },
    ]


async def test_unsubscribe(hass: HomeAssistant) -> None:
    """Test a listener stops receiving updates after unsubscribing."""
    updates: list[system_state.SystemState] = []

    @callback
    def _listener(state: system_state.SystemState) -> None:
        updates.append(state)

    unsubscribe = system_state.async_subscribe(hass, _listener)
    unsubscribe()

    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    await hass.async_block_till_done()

    assert updates == []


async def test_system_state_is_read_only(hass: HomeAssistant) -> None:
    """Test callers cannot bypass the latch by changing the state."""
    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    state = system_state.async_get(hass)

    with pytest.raises(FrozenInstanceError):
        state.home_assistant_restart_sources = frozenset()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        state.home_assistant_restart_sources.clear()  # type: ignore[attr-defined]
    with pytest.raises(FrozenInstanceError):
        state.host_reboot_required = True  # type: ignore[misc]

    assert system_state.async_get(hass).home_assistant_restart_sources == {"hacs"}


async def test_set_host_reboot_required(hass: HomeAssistant) -> None:
    """Test the host reboot flag follows Supervisor, and only updates on change."""
    updates: list[bool] = []
    system_state.async_subscribe(
        hass, callback(lambda state: updates.append(state.host_reboot_required))
    )

    system_state.async_set_host_reboot_required(hass, True)
    system_state.async_set_host_reboot_required(hass, True)
    system_state.async_set_host_reboot_required(hass, False)
    await hass.async_block_till_done()

    assert updates == [True, False]
    assert not system_state.async_get(hass).host_reboot_required


async def test_dismiss(hass: HomeAssistant) -> None:
    """Test a dismissed restart stays required, until another integration asks."""
    updates: list[bool] = []
    system_state.async_subscribe(
        hass,
        callback(lambda state: updates.append(state.home_assistant_restart_dismissed)),
    )

    # Nothing pending, so nothing to put off.
    system_state.async_dismiss(hass)

    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    system_state.async_dismiss(hass)
    system_state.async_dismiss(hass)

    state = system_state.async_get(hass)
    assert state.home_assistant_restart_required
    assert state.home_assistant_restart_dismissed

    # The same integration asking again is not news.
    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    assert system_state.async_get(hass).home_assistant_restart_dismissed

    system_state.async_set_home_assistant_restart_required(hass, "demo")
    await hass.async_block_till_done()

    assert not system_state.async_get(hass).home_assistant_restart_dismissed
    assert updates == [False, True, False]


async def test_dismiss_host_reboot(hass: HomeAssistant) -> None:
    """Test a dismissed reboot comes back once Supervisor raises it again."""
    system_state.async_set_host_reboot_required(hass, True)
    system_state.async_dismiss(hass)

    state = system_state.async_get(hass)
    assert state.host_reboot_required
    assert state.host_reboot_dismissed

    # After the reboot a new one is new again, not put off.
    system_state.async_set_host_reboot_required(hass, False)
    system_state.async_set_host_reboot_required(hass, True)

    assert not system_state.async_get(hass).host_reboot_dismissed
