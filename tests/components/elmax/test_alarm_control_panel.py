"""Tests for the Elmax alarm control panels."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.elmax import ElmaxCoordinator
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform


async def test_alarm_control_panels(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test alarm control panels."""
    with patch(
        "homeassistant.components.elmax.ELMAX_PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_elmax_entity_update_callback(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test ElmaxEntity _handle_update."""
    with patch(
        "homeassistant.components.elmax.ELMAX_PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        entry = await init_integration(hass)
    coordinator: ElmaxCoordinator = hass.data[entry.domain][entry.entry_id]

    pre_update_state = hass.states.get(
        "alarm_control_panel.direct_panel_https_1_1_1_1_443_api_v2_area_1"
    )
    assert pre_update_state.state == "unknown"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    new_state = hass.states.get(
        "alarm_control_panel.direct_panel_https_1_1_1_1_443_api_v2_area_1"
    )
    assert new_state.state == "disarmed"
