"""The tests for Blue Current buttons."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry

charge_point_buttons = ["stop_charge_session", "reset", "reboot"]


async def test_buttons_created(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if all buttons are created."""
    await init_integration(hass, config_entry, "button")

    entity_registry = er.async_get(hass)

    buttons = er.async_entries_for_config_entry(entity_registry, "uuid")
    assert len(charge_point_buttons) == len(buttons)


@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_charge_point_buttons(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the underlying charge point buttons."""
    await init_integration(hass, config_entry, "button")

    entity_registry = er.async_get(hass)

    for button in charge_point_buttons:
        state = hass.states.get(f"button.101_{button}")
        assert state is not None
        assert state.state == "unknown"
        entry = entity_registry.async_get(f"button.101_{button}")
        assert entry and entry.unique_id == f"{button}_101"

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": f"button.101_{button}"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(f"button.101_{button}")
        assert state
        assert state.state == "2023-01-13T12:00:00+00:00"
