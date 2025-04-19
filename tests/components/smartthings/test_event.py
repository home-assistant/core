"""Test for the SmartThings event platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pysmartthings import Attribute, Capability
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPES
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities, trigger_update

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.EVENT)


@pytest.mark.parametrize("device_fixture", ["heatit_zpushwall"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    freezer.move_to("2023-10-21")

    assert (
        hass.states.get("event.livingroom_smart_switch_button1").state == STATE_UNKNOWN
    )

    await trigger_update(
        hass,
        devices,
        "5e5b97f3-3094-44e6-abc0-f61283412d6a",
        Capability.BUTTON,
        Attribute.BUTTON,
        "pushed",
        component="button1",
    )

    assert (
        hass.states.get("event.livingroom_smart_switch_button1").state
        == "2023-10-21T00:00:00.000+00:00"
    )


@pytest.mark.parametrize("device_fixture", ["heatit_zpushwall"])
async def test_supported_button_values_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test supported button values update."""
    await setup_integration(hass, mock_config_entry)

    freezer.move_to("2023-10-21")

    assert (
        hass.states.get("event.livingroom_smart_switch_button1").state == STATE_UNKNOWN
    )
    assert hass.states.get("event.livingroom_smart_switch_button1").attributes[
        ATTR_EVENT_TYPES
    ] == ["pushed", "held", "down_hold"]

    await trigger_update(
        hass,
        devices,
        "5e5b97f3-3094-44e6-abc0-f61283412d6a",
        Capability.BUTTON,
        Attribute.SUPPORTED_BUTTON_VALUES,
        ["pushed", "held", "down_hold", "pushed_2x"],
        component="button1",
    )

    assert (
        hass.states.get("event.livingroom_smart_switch_button1").state == STATE_UNKNOWN
    )
    assert hass.states.get("event.livingroom_smart_switch_button1").attributes[
        ATTR_EVENT_TYPES
    ] == ["pushed", "held", "down_hold", "pushed_2x"]
