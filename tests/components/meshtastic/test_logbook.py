"""Tests for the Meshtastic logbook describer."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.meshtastic.const import (
    ATTR_CHANNEL,
    ATTR_EVENT_TYPE,
    ATTR_FROM_ID,
    ATTR_FROM_NUM,
    ATTR_GATEWAY_ID,
    ATTR_NODE_ID,
    ATTR_NODE_NUM,
    ATTR_PORTNUM,
    ATTR_TEXT,
    ATTR_TO_NUM,
    ATTR_VIA_MQTT,
    BROADCAST_NUM,
    DOMAIN,
    EVENT_MESHTASTIC,
    PORTNUM_NAMES,
    PORTNUM_POSITION_APP,
    PORTNUM_TELEMETRY_APP,
    PORTNUM_TEXT_MESSAGE_APP,
    PORTNUM_UNKNOWN_APP,
    node_device_id,
)
from homeassistant.components.meshtastic.logbook import (
    ICON_MESSAGE,
    ICON_PACKET,
    MAX_TEXT_LENGTH,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    REMOTE_ID,
    REMOTE_NUM,
    SENSOR_NODE_ID,
    FakePubSub,
    inject_node_info,
    setup_integration,
)

from tests.common import MockConfigEntry
from tests.components.logbook.common import MockRow, mock_humanify

FROZEN_TIME = "2025-09-08 02:57:10+00:00"

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


@pytest.fixture
async def logbook_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up the logbook with a Meshtastic gateway and two known nodes."""
    hass.config.components.add("frontend")
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await setup_integration(hass, mock_config_entry)
    for node_id in (REMOTE_ID, SENSOR_NODE_ID):
        await inject_node_info(
            hass, mock_pubsub, mock_meshtastic_client, node_fixtures[node_id]
        )


def _describe(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Return the logbook entry one bus event describes to."""
    (entry,) = mock_humanify(hass, [MockRow(EVENT_MESHTASTIC, data)])
    return entry


@pytest.mark.usefixtures("logbook_integration")
async def test_direct_message(hass: HomeAssistant) -> None:
    """Test a text message addressed to the gateway."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_FROM_ID: REMOTE_ID,
            ATTR_TO_NUM: GATEWAY_NUM,
            ATTR_CHANNEL: 0,
            ATTR_PORTNUM: PORTNUM_NAMES[PORTNUM_TEXT_MESSAGE_APP],
            ATTR_TEXT: "on my way",
        },
    )

    assert entry["domain"] == DOMAIN
    assert entry["name"] == "Remote One"
    assert entry["message"] == 'sent "on my way" as a direct message'
    assert entry["icon"] == ICON_MESSAGE


@pytest.mark.usefixtures("logbook_integration")
async def test_channel_message(hass: HomeAssistant) -> None:
    """Test a text message broadcast on a channel."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_FROM_ID: REMOTE_ID,
            ATTR_TO_NUM: BROADCAST_NUM,
            ATTR_CHANNEL: 2,
            ATTR_PORTNUM: PORTNUM_NAMES[PORTNUM_TEXT_MESSAGE_APP],
            ATTR_TEXT: "anyone around?",
        },
    )

    assert entry["name"] == "Remote One"
    assert entry["message"] == 'sent "anyone around?" on channel 2'
    assert entry["icon"] == ICON_MESSAGE


@pytest.mark.usefixtures("logbook_integration")
async def test_message_without_a_channel(hass: HomeAssistant) -> None:
    """Test a broadcast whose channel the event does not carry."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_TO_NUM: BROADCAST_NUM,
            ATTR_TEXT: "hello mesh",
        },
    )

    assert entry["name"] == "Remote One"
    assert entry["message"] == 'sent "hello mesh" to everyone'


@pytest.mark.usefixtures("logbook_integration")
async def test_long_message_is_cut(hass: HomeAssistant) -> None:
    """Test that a long message is shortened to one line."""
    text = "n" * (MAX_TEXT_LENGTH + 40)

    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_TO_NUM: BROADCAST_NUM,
            ATTR_CHANNEL: 0,
            ATTR_TEXT: text,
        },
    )

    assert entry["message"] == (f'sent "{"n" * (MAX_TEXT_LENGTH - 1)}…" on channel 0')


@pytest.mark.usefixtures("logbook_integration")
async def test_gateway_event_names_the_gateway_device(hass: HomeAssistant) -> None:
    """Test that the gateway's own traffic is not a sub-device of itself."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: GATEWAY_NUM,
            ATTR_TO_NUM: BROADCAST_NUM,
            ATTR_CHANNEL: 0,
            ATTR_TEXT: "gateway speaking",
        },
    )

    assert entry["name"] == "HA Gateway"


@pytest.mark.usefixtures("logbook_integration")
async def test_renamed_device_is_used(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the name the user gave the device wins."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, node_device_id(GATEWAY_NUM, REMOTE_NUM)), mock_config_entry.entry_id
    )
    assert device is not None
    device_registry.async_update_device(device.id, name_by_user="Front Gate")

    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_TO_NUM: BROADCAST_NUM,
            ATTR_CHANNEL: 0,
            ATTR_TEXT: "open",
        },
    )

    assert entry["name"] == "Front Gate"


@pytest.mark.usefixtures("logbook_integration")
@pytest.mark.parametrize(
    ("portnum", "message"),
    [
        (PORTNUM_NAMES[PORTNUM_POSITION_APP], "reported its position"),
        (PORTNUM_NAMES[PORTNUM_TELEMETRY_APP], "reported telemetry"),
        (
            PORTNUM_NAMES[PORTNUM_UNKNOWN_APP],
            "sent a packet this channel cannot decrypt",
        ),
    ],
)
async def test_packet_without_text(
    hass: HomeAssistant, portnum: str, message: str
) -> None:
    """Test that a packet carrying no text is described by its port."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_PORTNUM: portnum,
        },
    )

    assert entry["name"] == "Remote One"
    assert entry["message"] == message
    assert entry["icon"] == ICON_PACKET


@pytest.mark.usefixtures("logbook_integration")
async def test_event_type_is_used_for_an_unknown_port(hass: HomeAssistant) -> None:
    """Test the fallback for a port the describer has no wording for."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_PORTNUM: "SERIAL_APP",
            ATTR_EVENT_TYPE: "direct_message",
        },
    )

    assert entry["message"] == "sent a direct message event"
    assert entry["icon"] == ICON_PACKET


@pytest.mark.usefixtures("logbook_integration")
async def test_via_mqtt_is_reported(hass: HomeAssistant) -> None:
    """Test that a packet that came in over MQTT says so."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_TO_NUM: BROADCAST_NUM,
            ATTR_CHANNEL: 0,
            ATTR_TEXT: "relayed",
            ATTR_VIA_MQTT: True,
        },
    )

    assert entry["message"] == 'sent "relayed" on channel 0, via MQTT'


@pytest.mark.usefixtures("logbook_integration")
async def test_node_spelled_with_the_node_attributes(hass: HomeAssistant) -> None:
    """Test the ``node_num``/``node_id`` spelling used by node-scoped events."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_NODE_NUM: REMOTE_NUM,
            ATTR_NODE_ID: REMOTE_ID,
            ATTR_PORTNUM: PORTNUM_NAMES[PORTNUM_POSITION_APP],
        },
    )

    assert entry["name"] == "Remote One"
    assert entry["message"] == "reported its position"


@pytest.mark.usefixtures("logbook_integration")
async def test_node_identified_only_by_its_id(hass: HomeAssistant) -> None:
    """Test that a node id alone still resolves to the device."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_ID: REMOTE_ID,
            ATTR_TO_NUM: BROADCAST_NUM,
            ATTR_CHANNEL: 0,
            ATTR_TEXT: "id only",
        },
    )

    assert entry["name"] == "Remote One"
    assert entry["message"] == 'sent "id only" on channel 0'


@pytest.mark.usefixtures("logbook_integration")
@pytest.mark.parametrize(
    ("data", "name"),
    [
        # Nothing at all: the recorder must still get a readable line.
        ({}, "Meshtastic"),
        # A node this gateway has no device for.
        (
            {ATTR_GATEWAY_ID: GATEWAY_ID, ATTR_FROM_NUM: 1},
            "!00000001",
        ),
        # An id that is not a node id at all.
        (
            {ATTR_GATEWAY_ID: GATEWAY_ID, ATTR_FROM_ID: "not-a-node"},
            "not-a-node",
        ),
        # A gateway id that is not a node id either.
        (
            {ATTR_GATEWAY_ID: "nonsense", ATTR_FROM_ID: REMOTE_ID},
            REMOTE_ID,
        ),
        # No gateway at all, so no device can be resolved.
        ({ATTR_FROM_NUM: REMOTE_NUM}, "!aabbccdd"),
    ],
)
async def test_event_with_missing_fields(
    hass: HomeAssistant, data: dict[str, Any], name: str
) -> None:
    """Test that an event missing its optional fields still describes."""
    entry = _describe(hass, data)

    assert entry["domain"] == DOMAIN
    assert entry["name"] == name
    assert entry["message"] == "was heard by the mesh"
    assert entry["icon"] == ICON_PACKET


@pytest.mark.usefixtures("logbook_integration")
async def test_empty_text_falls_back_to_the_port(hass: HomeAssistant) -> None:
    """Test that an empty text field is not reported as a message."""
    entry = _describe(
        hass,
        {
            ATTR_GATEWAY_ID: GATEWAY_ID,
            ATTR_FROM_NUM: REMOTE_NUM,
            ATTR_TEXT: "",
            ATTR_PORTNUM: PORTNUM_NAMES[PORTNUM_POSITION_APP],
        },
    )

    assert entry["message"] == "reported its position"
    assert entry["icon"] == ICON_PACKET
