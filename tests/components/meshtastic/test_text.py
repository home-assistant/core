"""Tests for the Meshtastic text platform.

``device.tzdef`` is one of the device fields ``AdminModule::handleSetConfig``
applies live, so writing it does not restart the radio.  The tests pin the
exact admin payload, because the firmware replaces its whole
``Config.DeviceConfig`` with the one it receives.
"""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from meshtastic.protobuf import admin_pb2, config_pb2
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.meshtastic.config_entity import (
    LIVE_FIELDS,
    REBOOTING_FIELDS,
    SECTION_DEVICE,
    async_get_config_snapshot,
)
from homeassistant.components.meshtastic.text import TEXTS
from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    FakePubSub,
    inject_connection_lost,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry, snapshot_platform

# Six minutes after the newest timestamp in ``nodes.json``.
FROZEN_TIME = "2025-09-08 03:06:00+00:00"

#: The packet id the library assigns to the admin message a write produces.
ADMIN_PACKET_ID = 222333444

#: The POSIX timezone string the node starts out with, and the one written.
BERLIN = "CET-1CEST,M3.5.0,M10.5.0/3"
LONDON = "GMT0BST,M3.5.0/1,M10.5.0"

TZDEF = "text.ha_gateway_time_zone"

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


@pytest.fixture(autouse=True)
def node_configuration(gateway_local_node: SimpleNamespace) -> None:
    """Give the node the configuration a real gateway would report."""
    device = gateway_local_node.localConfig.device
    device.node_info_broadcast_secs = 10800
    device.tzdef = BERLIN


@pytest.fixture
def admin_writes(mock_meshtastic_client: MagicMock) -> list[admin_pb2.AdminMessage]:
    """Record the admin message every configuration write hands the library."""
    local_node = mock_meshtastic_client.localNode
    sent: list[admin_pb2.AdminMessage] = []

    def _write_config(name: str) -> None:
        message = admin_pb2.AdminMessage()
        getattr(message.set_config, name).CopyFrom(
            getattr(local_node.localConfig, name)
        )
        sent.append(message)
        mock_meshtastic_client.currentPacketId = ADMIN_PACKET_ID

    local_node.writeConfig = MagicMock(side_effect=_write_config)
    mock_meshtastic_client.currentPacketId = 0
    return sent


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


async def setup_text_platform(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up only the text platform."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.TEXT]):
        await setup_integration(hass, entry)


async def start_set_value(
    hass: HomeAssistant, entity_id: str, value: str
) -> asyncio.Task[None]:
    """Start a set_value action and let it reach the radio."""
    task = hass.async_create_task(
        hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )
    )
    # The library call runs in the executor; give it a few loop iterations to
    # get out before the node's answer is injected.
    for _ in range(10):
        await asyncio.sleep(0)
    return task


@pytest.mark.usefixtures("mock_meshtastic_client", "entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the text entities created for the gateway."""
    await setup_text_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_state_comes_from_the_downloaded_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
) -> None:
    """Test that the text shows what the node reported on connect."""
    await setup_text_platform(hass, mock_config_entry)

    assert (state := hass.states.get(TZDEF))
    assert state.state == BERLIN
    mock_meshtastic_client.sendData.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_value_sends_the_whole_section_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test the exact admin payload a changed timezone produces.

    ``role`` is on the rebooting side of the device list, so the section the
    node reported has to come back with it intact.
    """
    await setup_text_platform(hass, mock_config_entry)

    task = await start_set_value(hass, TZDEF, LONDON)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    mock_meshtastic_client.localNode.writeConfig.assert_called_once_with(SECTION_DEVICE)
    assert len(admin_writes) == 1
    assert admin_writes[0].set_config.device == config_pb2.Config.DeviceConfig(
        role=config_pb2.Config.DeviceConfig.Role.CLIENT,
        node_info_broadcast_secs=10800,
        tzdef=LONDON,
    )
    assert (state := hass.states.get(TZDEF))
    assert state.state == LONDON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_an_unchanged_value_is_never_written(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that writing the value the node already has costs nothing."""
    await setup_text_platform(hass, mock_config_entry)

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TZDEF, ATTR_VALUE: BERLIN},
        blocking=True,
    )

    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_value_the_firmware_buffer_cannot_hold_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that an oversized timezone never reaches the radio.

    The firmware stores ``tzdef`` in a 65 byte buffer, one byte of which is
    the terminator, so the entity's own maximum is what protects the node.
    """
    await setup_text_platform(hass, mock_config_entry)

    with pytest.raises(ValueError, match="too long"):
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: TZDEF, ATTR_VALUE: "X" * 65},
            blocking=True,
        )

    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_refused_write_raises_a_translated_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that a routing error from the node becomes a translated error."""
    await setup_text_platform(hass, mock_config_entry)

    task = await start_set_value(hass, TZDEF, LONDON)
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        routing_packet(ADMIN_PACKET_ID, "BAD_REQUEST"),
    )

    with pytest.raises(ServiceValidationError) as err:
        await task

    assert err.value.translation_key == "rejected_bad_request"
    assert err.value.translation_placeholders == {
        "node": "HA Gateway",
        "reason": "BAD_REQUEST",
        "message": "",
    }
    assert len(admin_writes) == 1
    assert (state := hass.states.get(TZDEF))
    assert state.state == BERLIN


@pytest.mark.parametrize(
    ("section", "field"),
    [
        # ``network`` (Wi-Fi SSID, PSK, NTP server) is the obvious place for a
        # text entity and reboots for every field.
        ("network", "wifi_ssid"),
        ("network", "ntp_server"),
        # ``set_owner`` is not a config section at all, and reboots whenever
        # the firmware sees a change.
        ("owner", "long_name"),
    ],
)
async def test_a_setting_that_reboots_the_node_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    admin_writes: list[admin_pb2.AdminMessage],
    section: str,
    field: str,
) -> None:
    """Test that the shared snapshot refuses to write a rebooting text field."""
    await setup_text_platform(hass, mock_config_entry)
    config_snapshot = await async_get_config_snapshot(mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await config_snapshot.async_write(section, field, "anything")

    assert err.value.translation_key == "setting_reboots_node"
    assert err.value.translation_placeholders == {"setting": f"{section}.{field}"}
    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []


def test_every_exposed_text_is_applied_live() -> None:
    """Test that no text entity writes a field the firmware reboots for."""
    for description in TEXTS:
        assert description.field in LIVE_FIELDS[description.section], (
            f"{description.key} writes {description.section}.{description.field}, "
            "which is not on the firmware's live list"
        )
        assert description.field not in REBOOTING_FIELDS[description.section]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_texts_go_unavailable_with_the_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that nothing can be written while the node is unreachable."""
    await setup_text_platform(hass, mock_config_entry)
    assert (state := hass.states.get(TZDEF))
    assert state.state != STATE_UNAVAILABLE

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(TZDEF))
    assert state.state == STATE_UNAVAILABLE
