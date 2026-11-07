"""Test the whole-panel alarm entity base class."""

# ruff: noqa: D103
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from homeassistant.components.visonic.const import (
    CONF_ARM_HOME_ENABLED,
    CONF_INSTANT_ARM_AWAY,
    CONF_INSTANT_ARM_HOME,
)
from homeassistant.components.visonic.entity import AlarmBaseLogic
from homeassistant.components.visonic.exceptions import VisonicException
from homeassistant.components.visonic.visonic_data_types import VisonicConfigEntry
from homeassistant.components.visonic.visonic_types import PanelStateData
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .helpers import SetupIntegration, create_config_entry_empty


# Mock class to replace actual alarm panel
class TestAlarm(AlarmBaseLogic):
    """Simple test alarm."""

    __test__ = False

    def __init__(
        self,
        entry: VisonicConfigEntry,
        identifier: str = "identifier",
    ) -> None:
        """Initialize a whole-panel test alarm."""
        super().__init__(entry, identifier)

    def update_local(self, entry: ConfigEntry) -> None:
        """Update local."""
        self.local_updated = True


@pytest.mark.asyncio
async def test_init_whole_panel(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    wait_for_coordinator_timer: Callable[[], Awaitable[None]],
) -> None:
    result, entry = await setup_integration()
    assert result
    alarm = TestAlarm(entry)
    assert alarm._name == "identifier_main_panel"
    assert alarm._panel_ident == "identifier"
    assert alarm._attr_name is None
    assert alarm._attr_unique_id == "identifier_main_panel"

    assert alarm.local_updated
    # Coordinator method called
    assert alarm.coordinator

    await wait_for_coordinator_timer()


def test_init_without_coordinator() -> None:
    """Reject an entity whose config entry has no coordinator."""
    entry = create_config_entry_empty()
    entry.runtime_data = SimpleNamespace(coordinator=None, panel_id=1)

    with pytest.raises(VisonicException, match="invalid coordinator"):
        TestAlarm(entry)


async def test_arm_options(
    setup_integration: Callable[..., Awaitable[tuple[bool, ConfigEntry]]],
) -> None:
    """Read arm options from the config entry."""
    result, entry = await setup_integration(
        options={
            CONF_ARM_HOME_ENABLED: False,
            CONF_INSTANT_ARM_HOME: True,
            CONF_INSTANT_ARM_AWAY: True,
        }
    )
    assert result
    alarm = TestAlarm(entry)

    assert alarm.isarmhome is False
    assert alarm.isarmhomeinstant is True
    assert alarm.isarmawayinstant is True


async def test_coordinator_update(
    setup_integration: Callable[..., Awaitable[tuple[bool, ConfigEntry]]],
) -> None:
    """Refresh panel state and write the entity state after an update."""
    result, entry = await setup_integration()
    assert result
    alarm = TestAlarm(entry)
    state = PanelStateData(connected=True)
    alarm.coordinator.get_panel_state = MagicMock(return_value=state)
    alarm.async_write_ha_state = MagicMock()

    alarm._handle_coordinator_update()

    assert alarm.panel_state_data is state
    assert alarm.local_updated
    alarm.coordinator.get_panel_state.assert_called_once_with()
    alarm.async_write_ha_state.assert_called_once_with()


async def test_panel_state_without_coordinator(
    setup_integration: Callable[..., Awaitable[tuple[bool, ConfigEntry]]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Use an empty state and warn if an update arrives without a coordinator."""
    result, entry = await setup_integration()
    assert result
    alarm = TestAlarm(entry)
    alarm.coordinator = None

    alarm._update_panel_state()

    assert alarm.panel_state_data == PanelStateData()
    assert "Coordinator not ready for alarm panel" in caplog.text


async def test_available(
    setup_integration: Callable[..., Awaitable[tuple[bool, ConfigEntry]]],
) -> None:
    """Require entity availability and a successful coordinator update."""
    result, entry = await setup_integration()
    assert result
    alarm = TestAlarm(entry)
    alarm._attr_available = True
    alarm.coordinator.last_update_success = True

    assert alarm.available is True

    alarm.coordinator.last_update_success = False
    assert alarm.available is False

    alarm._attr_available = False
    alarm.coordinator.last_update_success = True
    assert alarm.available is False
