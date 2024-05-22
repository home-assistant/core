"""The tests for the Rfxtrx sensor platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from RFXtrx import ControlEvent
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rfxtrx import get_rfx_object
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_rfx_test_cfg


@pytest.fixture(autouse=True)
def required_platforms_only():
    """Only set up the required platform and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.rfxtrx.PLATFORMS",
        (Platform.EVENT,),
    ):
        yield


async def test_control_event(
    hass: HomeAssistant,
    rfxtrx,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test event update updates correct event object."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")

    await setup_rfx_test_cfg(
        hass,
        devices={
            "0710013d43010150": {},
            "0710013d44010150": {},
        },
    )

    assert hass.states.get("event.arc_c1") == snapshot(name="1")
    assert hass.states.get("event.arc_d1") == snapshot(name="2")

    # only signal one, to make sure we have no overhearing
    await rfxtrx.signal("0710013d44010150")

    assert hass.states.get("event.arc_c1") == snapshot(diff="1")
    assert hass.states.get("event.arc_d1") == snapshot(diff="2")


async def test_status_event(
    hass: HomeAssistant,
    rfxtrx,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test event update updates correct event object."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")

    await setup_rfx_test_cfg(
        hass,
        devices={
            "0820004dd3dc540089": {},
        },
    )

    assert hass.states.get("event.x10_security_d3dc54_32") == snapshot(name="1")

    await rfxtrx.signal("0820004dd3dc540089")

    assert hass.states.get("event.x10_security_d3dc54_32") == snapshot(diff="1")


async def test_invalid_event_type(
    hass: HomeAssistant,
    rfxtrx,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test with 1 sensor."""
    await setup_rfx_test_cfg(
        hass,
        devices={
            "0710013d43010150": {},
        },
    )

    state = hass.states.get("event.arc_c1")

    # Invalid event type should not trigger change
    event = get_rfx_object("0710013d43010150")
    assert isinstance(event, ControlEvent)
    event.values["Command"] = "invalid_command"

    rfxtrx.event_callback(event)
    await hass.async_block_till_done()

    assert hass.states.get("event.arc_c1") == state


async def test_ignoring_lighting4(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 1 sensor."""
    entry = await setup_rfx_test_cfg(
        hass,
        devices={
            "0913000022670e013970": {
                "data_bits": 4,
                "command_on": 0xE,
                "command_off": 0x7,
            }
        },
    )

    registry = er.async_get(hass)
    entries = [
        entry
        for entry in registry.entities.get_entries_for_config_entry_id(entry.entry_id)
        if entry.domain == Platform.EVENT
    ]
    assert entries == []
