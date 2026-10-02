"""Test the system state helper."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import system_state


async def test_home_assistant_restart_not_required(hass: HomeAssistant) -> None:
    """Test a fresh instance does not require a restart."""
    state = system_state.async_get(hass)

    assert not state.home_assistant_restart_required
    assert state.as_dict() == {
        "home_assistant_restart_required": False,
        "home_assistant_restart_sources": [],
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
            "home_assistant_restart_required": True,
            "home_assistant_restart_sources": ["hacs"],
        },
        {
            "home_assistant_restart_required": True,
            "home_assistant_restart_sources": ["demo", "hacs"],
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
