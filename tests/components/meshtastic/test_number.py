"""Tests for the Meshtastic number platform.

Both numbers write a ``Config`` section the firmware applies live.  The tests
drive the whole round trip — start the write, inject the routing packet the
node answers with, then read the state back — and pin the exact admin payload,
because ``handleSetConfig`` compares the section it receives against its own
copy and restarts the node if a field it cares about changed.
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
    SECTION_LORA,
    async_get_config_snapshot,
)
from homeassistant.components.meshtastic.number import NUMBERS
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
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

HOP_LIMIT = "number.ha_gateway_hop_limit"
NODE_INFO_INTERVAL = "number.ha_gateway_node_info_interval"

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


@pytest.fixture(autouse=True)
def node_configuration(gateway_local_node: SimpleNamespace) -> None:
    """Give the node the configuration a real gateway would report."""
    lora = gateway_local_node.localConfig.lora
    lora.tx_enabled = True
    lora.tx_power = 27
    lora.channel_num = 20
    gateway_local_node.localConfig.device.node_info_broadcast_secs = 10800


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


async def setup_number_platform(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up only the number platform."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, entry)


async def start_set_value(
    hass: HomeAssistant, entity_id: str, value: float
) -> asyncio.Task[None]:
    """Start a set_value action and let it reach the radio."""
    task = hass.async_create_task(
        hass.services.async_call(
            NUMBER_DOMAIN,
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
    """Test the numbers created for the gateway."""
    await setup_number_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_state_comes_from_the_downloaded_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
) -> None:
    """Test that each number shows what the node reported on connect."""
    await setup_number_platform(hass, mock_config_entry)

    assert (state := hass.states.get(HOP_LIMIT))
    assert state.state == "3.0"
    assert (state := hass.states.get(NODE_INFO_INTERVAL))
    assert state.state == "10800.0"
    # Reading the configuration is a local call into the library.
    mock_meshtastic_client.sendData.assert_not_called()


async def test_set_value_sends_the_whole_section_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test the exact admin payload a changed hop limit produces.

    ``handleSetConfig`` replaces its whole ``Config.LoRaConfig`` with the one
    it receives, so the write starts from the section the node reported.
    Losing ``region``, ``modem_preset``, ``tx_power`` or ``channel_num`` on the
    way would count as a change and restart the node.
    """
    await setup_number_platform(hass, mock_config_entry)

    task = await start_set_value(hass, HOP_LIMIT, 5)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    mock_meshtastic_client.localNode.writeConfig.assert_called_once_with(SECTION_LORA)
    assert len(admin_writes) == 1
    assert admin_writes[0].set_config.lora == config_pb2.Config.LoRaConfig(
        region=config_pb2.Config.LoRaConfig.RegionCode.EU_868,
        modem_preset=config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST,
        hop_limit=5,
        tx_enabled=True,
        tx_power=27,
        channel_num=20,
    )
    assert (state := hass.states.get(HOP_LIMIT))
    assert state.state == "5.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_the_node_info_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that the device number writes the device section as an integer."""
    await setup_number_platform(hass, mock_config_entry)

    task = await start_set_value(hass, NODE_INFO_INTERVAL, 7200)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    mock_meshtastic_client.localNode.writeConfig.assert_called_once_with(SECTION_DEVICE)
    assert admin_writes[0].set_config.device == config_pb2.Config.DeviceConfig(
        role=config_pb2.Config.DeviceConfig.Role.CLIENT,
        node_info_broadcast_secs=7200,
    )
    assert (state := hass.states.get(NODE_INFO_INTERVAL))
    assert state.state == "7200.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_below_the_firmware_floor_never_reaches_the_radio(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that an interval the firmware would clamp is refused up front.

    ``handleSetConfig`` raises anything below an hour to the default
    (``AdminModule.cpp:686-689``), so a smaller value would be accepted, cost a
    flash write and then read back as something else.
    """
    await setup_number_platform(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: NODE_INFO_INTERVAL, ATTR_VALUE: 60},
            blocking=True,
        )

    assert err.value.translation_key == "out_of_range"
    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []


async def test_an_unchanged_value_is_never_written(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that writing the value the node already has costs nothing."""
    await setup_number_platform(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: HOP_LIMIT, ATTR_VALUE: 3},
        blocking=True,
    )

    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []
    assert (state := hass.states.get(HOP_LIMIT))
    assert state.state == "3.0"


async def test_a_refused_write_raises_a_translated_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that a routing error from the node becomes a translated error."""
    await setup_number_platform(hass, mock_config_entry)

    task = await start_set_value(hass, HOP_LIMIT, 7)
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
    assert (state := hass.states.get(HOP_LIMIT))
    assert state.state == "3.0"


@pytest.mark.parametrize(
    ("section", "field"),
    [
        (SECTION_LORA, "bandwidth"),
        (SECTION_LORA, "channel_num"),
        (SECTION_LORA, "coding_rate"),
        (SECTION_LORA, "frequency_offset"),
        (SECTION_LORA, "spread_factor"),
        (SECTION_LORA, "tx_power"),
        (SECTION_DEVICE, "buzzer_gpio"),
        # ``power`` reboots for every field this integration would want.
        ("power", "ls_secs"),
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
    """Test that the shared snapshot refuses to write a rebooting number."""
    await setup_number_platform(hass, mock_config_entry)
    config_snapshot = await async_get_config_snapshot(mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await config_snapshot.async_write(section, field, 1)

    assert err.value.translation_key == "setting_reboots_node"
    assert err.value.translation_placeholders == {"setting": f"{section}.{field}"}
    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []


def test_every_exposed_number_is_applied_live() -> None:
    """Test that no number writes a field the firmware reboots for."""
    for description in NUMBERS:
        assert description.field in LIVE_FIELDS[description.section], (
            f"{description.key} writes {description.section}.{description.field}, "
            "which is not on the firmware's live list"
        )
        assert description.field not in REBOOTING_FIELDS[description.section]


def test_the_node_info_interval_offers_no_value_the_firmware_would_clamp() -> None:
    """Test that the entity's floor is the firmware's own minimum."""
    description = next(
        item for item in NUMBERS if item.field == "node_info_broadcast_secs"
    )
    assert description.native_min_value == 3600


async def test_numbers_go_unavailable_with_the_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that nothing can be written while the node is unreachable."""
    await setup_number_platform(hass, mock_config_entry)
    assert (state := hass.states.get(HOP_LIMIT))
    assert state.state != STATE_UNAVAILABLE

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(HOP_LIMIT))
    assert state.state == STATE_UNAVAILABLE
