"""Tests for the Meshtastic button platform.

Two kinds of button live here.  The node buttons ask one mesh node for
something it already publishes; nothing on the node changes, so they are safe
to press twice.  The gateway's restart button is the destructive one: the
firmware answers ``reboot_seconds`` with a routing acknowledgement and only
then goes away, without closing the TCP connection, so the press opens the
client's reboot grace window as soon as that acknowledgement arrives.
"""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from meshtastic.protobuf import mesh_pb2
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.meshtastic.button import NODE_BUTTONS
from homeassistant.components.meshtastic.config_entity import REBOOT_DELAY_SECONDS
from homeassistant.components.meshtastic.const import (
    DOMAIN as MESHTASTIC_DOMAIN,
    PORTNUM_NODEINFO_APP,
    PORTNUM_POSITION_APP,
    PORTNUM_TELEMETRY_APP,
    PORTNUM_TRACEROUTE_APP,
    REBOOT_GRACE,
    SEND_SPACING,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    REMOTE_ID,
    REMOTE_NUM,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# Six minutes after the newest timestamp in ``nodes.json``.
FROZEN_TIME = "2025-09-08 03:06:00+00:00"

#: ``sendData`` is pre-programmed to this packet id by the client fixture.
SENT_DATA_ID = 111222334
#: The packet id the library assigns to the restart admin message.
ADMIN_PACKET_ID = 222333444

RESTART = "button.ha_gateway_restart"
REQUEST_POSITION = "button.remote_one_request_position"
REQUEST_TELEMETRY = "button.remote_one_request_telemetry"
REQUEST_NODE_INFO = "button.remote_one_request_node_info"

#: The firmware's own per-portnum limits on packets from a client
#: (``PhoneAPI::handleToRadioPacket``, firmware v2.7.26.54e0d8d).
FIRMWARE_SEND_LIMITS = {
    PORTNUM_POSITION_APP: 10.0,
    PORTNUM_TELEMETRY_APP: 10.0,
    PORTNUM_TRACEROUTE_APP: 30.0,
}

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


@pytest.fixture
def restart_calls(mock_meshtastic_client: MagicMock) -> MagicMock:
    """Let the local node answer ``reboot()`` the way the library does."""
    reboot = MagicMock(return_value=mesh_pb2.MeshPacket(id=ADMIN_PACKET_ID))
    mock_meshtastic_client.localNode.reboot = reboot
    return reboot


def routing_packet(request_id: int, error: str = "NONE") -> dict[str, Any]:
    """Return the routing packet the gateway answers an admin message with."""
    return {
        "from": GATEWAY_NUM,
        "to": GATEWAY_NUM,
        "fromId": GATEWAY_ID,
        "toId": GATEWAY_ID,
        "channel": 0,
        "id": 987654330,
        "rxTime": 1757300600,
        "priority": "ACK",
        "decoded": {
            "portnum": "ROUTING_APP",
            "requestId": request_id,
            "routing": {"errorReason": error},
        },
    }


def response_packet(portnum: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return the answer a node sends to a request that wanted a response."""
    return {
        "from": REMOTE_NUM,
        "to": GATEWAY_NUM,
        "fromId": REMOTE_ID,
        "toId": GATEWAY_ID,
        "channel": 0,
        "id": 305441800,
        "rxTime": 1757300600,
        "rxSnr": 4.75,
        "rxRssi": -91,
        "hopLimit": 3,
        "hopStart": 3,
        "decoded": {"portnum": portnum, "requestId": SENT_DATA_ID, **payload},
    }


async def setup_button_platform(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    pubsub: FakePubSub,
    interface: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up only the button platform, with one known mesh node."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, entry)
    await inject_node_info(hass, pubsub, interface, node_fixtures[REMOTE_ID])


async def start_press(hass: HomeAssistant, entity_id: str) -> asyncio.Task[None]:
    """Start a press action and let it reach the radio."""
    task = hass.async_create_task(
        hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    )
    # The library call runs in the executor; give it a few loop iterations to
    # get out before the node's answer is injected.
    for _ in range(10):
        await asyncio.sleep(0)
    return task


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the buttons created for the gateway and one mesh node."""
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "portnum", "answer"),
    [
        (
            REQUEST_POSITION,
            PORTNUM_POSITION_APP,
            (
                "POSITION_APP",
                {
                    "position": {
                        "latitudeI": 521111111,
                        "longitudeI": 131111111,
                        "altitude": 42,
                        "time": 1757300600,
                        "precisionBits": 16,
                        "latitude": 52.1111111,
                        "longitude": 13.1111111,
                    }
                },
            ),
        ),
        (
            REQUEST_TELEMETRY,
            PORTNUM_TELEMETRY_APP,
            (
                "TELEMETRY_APP",
                {"telemetry": {"time": 1757300600, "deviceMetrics": {"voltage": 3.9}}},
            ),
        ),
        (
            REQUEST_NODE_INFO,
            PORTNUM_NODEINFO_APP,
            (
                "NODEINFO_APP",
                {
                    "user": {
                        "id": REMOTE_ID,
                        "longName": "Remote One",
                        "shortName": "RM1",
                        "hwModel": "HELTEC_V3",
                    }
                },
            ),
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_node_request_buttons(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    entity_id: str,
    portnum: int,
    answer: tuple[str, dict[str, Any]],
) -> None:
    """Test that each node button asks that node on the matching port."""
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_press(hass, entity_id)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, response_packet(*answer)
    )
    await task

    # An empty payload is a valid empty message on all three ports, and the
    # destination is always a node number, never a name.
    mock_meshtastic_client.sendData.assert_called_once_with(
        b"",
        destinationId=REMOTE_NUM,
        portNum=portnum,
        wantAck=True,
        wantResponse=True,
        channelIndex=0,
        hopLimit=None,
        pkiEncrypted=False,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == FROZEN_TIME.replace(" ", "T")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_node_that_refuses_the_request(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a routing error becomes a translated error."""
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_press(hass, REQUEST_POSITION)
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        routing_packet(SENT_DATA_ID, "NO_RESPONSE"),
    )

    with pytest.raises(HomeAssistantError) as err:
        await task

    assert err.value.translation_key == "no_response"
    assert err.value.translation_placeholders["node"] == "Remote One"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_node_that_never_answers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a request nothing ever answers becomes a translated error."""
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_press(hass, REQUEST_POSITION)
    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)

    with pytest.raises(HomeAssistantError) as err:
        await task

    assert err.value.translation_key == "timeout_no_ack"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_restart_button(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    restart_calls: MagicMock,
) -> None:
    """Test that the restart button asks the node to reboot and expects it to.

    The acknowledgement means the reboot is scheduled, not done, so the grace
    window has to open on the acknowledgement rather than on the disconnect
    that may never be announced.
    """
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    client = mock_config_entry.runtime_data.client
    assert client.reboot_grace_active is False

    task = await start_press(hass, RESTART)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    restart_calls.assert_called_once_with(REBOOT_DELAY_SECONDS)
    assert client.reboot_grace_active is True


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_the_restart_button_is_the_only_way_to_reboot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that rebooting the gateway has exactly one implementation.

    An action beside this button would give the same operation two different
    authorisation models -- the action administrator-only and confirmed, the
    button pressable by anybody who may press buttons -- and neither the user
    nor a reviewer could tell which one the integration means.  A restart is
    something an entity expresses, so the entity is the one that stays.
    """
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert hass.states.get(RESTART) is not None
    assert "reboot" not in hass.services.async_services_for_domain(MESHTASTIC_DOMAIN)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_the_grace_window_keeps_the_entities_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    restart_calls: MagicMock,
) -> None:
    """Test that a restart we asked for does not make everything unavailable.

    On ESP32 the node reboots without closing the socket, so the link drops
    seconds after the acknowledgement.  Flapping every entity for a reboot
    Home Assistant asked for is noise; the window closes on its own.
    """
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_press(hass, RESTART)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task
    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    client = mock_config_entry.runtime_data.client
    assert client.connected is False
    assert client.reboot_grace_active is True
    assert (state := hass.states.get(RESTART))
    assert state.state != STATE_UNAVAILABLE
    assert (state := hass.states.get(REQUEST_POSITION))
    assert state.state != STATE_UNAVAILABLE

    freezer.tick(timedelta(seconds=REBOOT_DELAY_SECONDS + REBOOT_GRACE + 10))
    assert client.reboot_grace_active is False

    # Nothing announces that the window closed, so the entities find out on
    # the next thing the coordinator has to say about the link.
    mock_config_entry.runtime_data.coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert (state := hass.states.get(RESTART))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_the_grace_window_covers_the_delay_the_node_was_given(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    restart_calls: MagicMock,
) -> None:
    """Test that the window covers the wait as well as the reboot itself.

    ``localNode.reboot(REBOOT_DELAY_SECONDS)`` only schedules the restart: the
    node answers, keeps running for the delay it was given and reboots after
    it.  A window that started at the acknowledgement and lasted a fixed
    ``REBOOT_GRACE`` would close first, so every entity would flap to
    unavailable at exactly the moment the window exists to cover, and the
    duplicate-press guard would reopen with the reboot still pending.
    """
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_press(hass, RESTART)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task
    restart_calls.assert_called_once_with(REBOOT_DELAY_SECONDS)

    client = mock_config_entry.runtime_data.client
    freezer.tick(timedelta(seconds=REBOOT_GRACE + 1))
    # The bare grace has run out, and the node has only just started rebooting.
    assert client.reboot_grace_active is True

    freezer.tick(timedelta(seconds=REBOOT_DELAY_SECONDS))
    assert client.reboot_grace_active is False


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_second_restart_is_refused_while_the_node_is_going_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    restart_calls: MagicMock,
) -> None:
    """Test that the grace window also guards against a second press.

    The node keeps answering for the ten seconds before it actually reboots,
    so a second press would be accepted and would restart the timer.
    """
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_press(hass, RESTART)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: RESTART}, blocking=True
        )

    assert err.value.translation_key == "reboot_in_progress"
    assert err.value.translation_placeholders == {"node": "HA Gateway"}
    restart_calls.assert_called_once_with(REBOOT_DELAY_SECONDS)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_refused_restart_does_not_open_the_grace_window(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    restart_calls: MagicMock,
) -> None:
    """Test that a reboot the node rejected leaves the entities alone."""
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_press(hass, RESTART)
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        routing_packet(ADMIN_PACKET_ID, "NOT_AUTHORIZED"),
    )

    with pytest.raises(HomeAssistantError) as err:
        await task

    assert err.value.translation_key == "admin_not_authorized"
    assert mock_config_entry.runtime_data.client.reboot_grace_active is False


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_button_for_an_operation_the_firmware_rate_limits(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that nothing offers a press the firmware would silently drop.

    ``PhoneAPI::handleToRadioPacket`` drops a second ``TRACEROUTE_APP`` packet
    within thirty seconds and answers with a ``ClientNotification`` instead of
    a route, which is far longer than anyone pressing a button would expect to
    wait.  Traceroute belongs behind an action that can explain the wait, not
    behind a button.  The ports that do get a button are paced by the client
    itself, by at least as long as the firmware's own limit.
    """
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    exposed = {description.portnum for description in NODE_BUTTONS}
    assert PORTNUM_TRACEROUTE_APP not in exposed
    assert not [
        entity_id
        for entity_id in hass.states.async_entity_ids(BUTTON_DOMAIN)
        if "traceroute" in entity_id
    ]
    for portnum in exposed & FIRMWARE_SEND_LIMITS.keys():
        assert SEND_SPACING[portnum] >= FIRMWARE_SEND_LIMITS[portnum]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_buttons_go_unavailable_with_the_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that nothing can be pressed while the node is unreachable."""
    await setup_button_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(REQUEST_POSITION))
    assert state.state != STATE_UNAVAILABLE

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(RESTART))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get(REQUEST_POSITION))
    assert state.state == STATE_UNAVAILABLE
