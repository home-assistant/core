"""Tests for Ecovacs event entities."""

from datetime import timedelta

from deebot_client.capabilities import Capabilities
from deebot_client.events import CleanJobStatus, ReportStatsEvent
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.components.event.const import ATTR_EVENT_TYPE
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import notify_and_wait

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.EVENT


async def test_last_job(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    controller: EcovacsController,
) -> None:
    """Test last job event entity."""
    freezer.move_to("2024-03-20T00:00:00+00:00")
    entity_id = "event.ozmo_950_last_job"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-entity_entry")
    assert entity_entry.device_id

    device = next(controller.devices(Capabilities))

    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}

    event_bus = device.events
    await notify_and_wait(
        hass,
        event_bus,
        ReportStatsEvent(10, 5, "spotArea", "1", CleanJobStatus.FINISHED, [1, 2]),
    )

    assert (state := hass.states.get(state.entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    freezer.tick(timedelta(minutes=5))
    await notify_and_wait(
        hass,
        event_bus,
        ReportStatsEvent(
            100, 50, "spotArea", "2", CleanJobStatus.FINISHED_WITH_WARNINGS, [2, 3]
        ),
    )

    assert (state := hass.states.get(state.entity_id))
    assert state.state == "2024-03-20T00:05:00.000+00:00"
    assert state.attributes[ATTR_EVENT_TYPE] == "finished_with_warnings"

    freezer.tick(timedelta(minutes=5))
    await notify_and_wait(
        hass,
        event_bus,
        ReportStatsEvent(0, 1, "spotArea", "3", CleanJobStatus.MANUALLY_STOPPED, [1]),
    )

    assert (state := hass.states.get(state.entity_id))
    assert state.state == "2024-03-20T00:10:00.000+00:00"
    assert state.attributes[ATTR_EVENT_TYPE] == "manually_stopped"

    freezer.tick(timedelta(minutes=5))
    for status in (CleanJobStatus.NO_STATUS, CleanJobStatus.CLEANING):
        # we should not trigger on these statuses
        await notify_and_wait(
            hass,
            event_bus,
            ReportStatsEvent(12, 11, "spotArea", "4", status, [1, 2, 3]),
        )

        assert (state := hass.states.get(state.entity_id))
        assert state.state == "2024-03-20T00:10:00.000+00:00"
        assert state.attributes[ATTR_EVENT_TYPE] == "manually_stopped"
