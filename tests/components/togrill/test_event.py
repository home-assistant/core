"""Test events for ToGrill integration."""

from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion
from togrill_bluetooth.packets import PacketA1Notify, PacketA5Notify

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import TOGRILL_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.freeze_time("2023-10-21")
@pytest.mark.parametrize(
    "packets",
    [
        pytest.param([], id="no_data"),
        pytest.param([PacketA1Notify([10, None])], id="non_event_packet"),
        pytest.param([PacketA5Notify(probe=1, message=99)], id="non_known_message"),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    packets,
) -> None:
    """Test standard events."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.EVENT])

    for packet in packets:
        mock_client.mocked_notify(packet)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


@pytest.mark.freeze_time("2023-10-21")
@pytest.mark.parametrize(
    "message",
    [pytest.param(message, id=message.name) for message in PacketA5Notify.Message],
)
async def test_events(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    message: PacketA5Notify.Message,
) -> None:
    """Test all possible events."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.EVENT])

    mock_client.mocked_notify(PacketA5Notify(probe=1, message=message))

    state = hass.states.get("event.probe_2_event")
    assert state
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("event.probe_1_event")
    assert state
    assert state.state == "2023-10-21T00:00:00.000+00:00"
    assert state.attributes.get(ATTR_EVENT_TYPE) == slugify(message.name)
