"""Tests for the Meshtastic select platform.

``device.buzzer_mode`` is not on the list that keeps ``requiresReboot`` true in
``AdminModule::handleSetConfig``, so writing it is live.  The tests pin the
enum mapping in both directions and the exact admin payload the write
produces.
"""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from meshtastic.protobuf import admin_pb2, config_pb2
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.meshtastic.config_entity import (
    BUZZER_MODES,
    LIVE_FIELDS,
    REBOOTING_FIELDS,
    SECTION_DEVICE,
    SECTION_LORA,
    async_get_config_snapshot,
)
from homeassistant.components.meshtastic.select import SELECTS
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
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

BUZZER_MODE = "select.ha_gateway_buzzer_mode"

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


@pytest.fixture(autouse=True)
def node_configuration(gateway_local_node: SimpleNamespace) -> None:
    """Give the node the configuration a real gateway would report."""
    device = gateway_local_node.localConfig.device
    device.node_info_broadcast_secs = 10800
    device.buzzer_mode = config_pb2.Config.DeviceConfig.BuzzerMode.NOTIFICATIONS_ONLY


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


async def setup_select_platform(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up only the select platform."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, entry)


async def start_select(
    hass: HomeAssistant, entity_id: str, option: str
) -> asyncio.Task[None]:
    """Start a select_option action and let it reach the radio."""
    task = hass.async_create_task(
        hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
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
    """Test the selects created for the gateway."""
    await setup_select_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_state_comes_from_the_downloaded_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
) -> None:
    """Test that the enum number the node reported is shown by name."""
    await setup_select_platform(hass, mock_config_entry)

    assert (state := hass.states.get(BUZZER_MODE))
    assert state.state == "notifications_only"
    assert state.attributes["options"] == list(BUZZER_MODES)
    mock_meshtastic_client.sendData.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_option_sends_the_whole_section_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test the exact admin payload a changed buzzer mode produces.

    ``role`` is on the rebooting side of the device list, so it has to come
    back exactly as the node reported it.
    """
    await setup_select_platform(hass, mock_config_entry)

    task = await start_select(hass, BUZZER_MODE, "direct_msg_only")
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    mock_meshtastic_client.localNode.writeConfig.assert_called_once_with(SECTION_DEVICE)
    assert len(admin_writes) == 1
    assert admin_writes[0].set_config.device == config_pb2.Config.DeviceConfig(
        role=config_pb2.Config.DeviceConfig.Role.CLIENT,
        node_info_broadcast_secs=10800,
        buzzer_mode=config_pb2.Config.DeviceConfig.BuzzerMode.DIRECT_MSG_ONLY,
    )
    assert (state := hass.states.get(BUZZER_MODE))
    assert state.state == "direct_msg_only"


def test_the_option_list_matches_the_protobuf_enum() -> None:
    """Test that every option maps to the enum number the firmware expects."""
    enum = config_pb2.Config.DeviceConfig.BuzzerMode
    assert [enum.Value(option.upper()) for option in BUZZER_MODES] == list(
        range(len(BUZZER_MODES))
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_an_unchanged_option_is_never_written(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that selecting the option the node already has costs nothing."""
    await setup_select_platform(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: BUZZER_MODE, ATTR_OPTION: "notifications_only"},
        blocking=True,
    )

    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_an_unknown_option_never_reaches_the_radio(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that an option the firmware has no number for is refused."""
    await setup_select_platform(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: BUZZER_MODE, ATTR_OPTION: "klaxon"},
            blocking=True,
        )

    assert err.value.translation_key == "not_valid_option"
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
    await setup_select_platform(hass, mock_config_entry)

    task = await start_select(hass, BUZZER_MODE, "disabled")
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
    assert (state := hass.states.get(BUZZER_MODE))
    assert state.state == "notifications_only"


@pytest.mark.parametrize(
    ("section", "field"),
    [
        (SECTION_DEVICE, "role"),
        (SECTION_DEVICE, "rebroadcast_mode"),
        (SECTION_LORA, "modem_preset"),
        (SECTION_LORA, "region"),
        # ``display`` reboots for the fields worth a select, and this
        # integration exposes none of it.
        ("display", "displaymode"),
        ("display", "oled"),
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
    """Test that the shared snapshot refuses to write a rebooting select."""
    await setup_select_platform(hass, mock_config_entry)
    config_snapshot = await async_get_config_snapshot(mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await config_snapshot.async_write(section, field, 1)

    assert err.value.translation_key == "setting_reboots_node"
    assert err.value.translation_placeholders == {"setting": f"{section}.{field}"}
    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []


def test_every_exposed_select_is_applied_live() -> None:
    """Test that no select writes a field the firmware reboots for."""
    for description in SELECTS:
        assert description.field in LIVE_FIELDS[description.section], (
            f"{description.key} writes {description.section}.{description.field}, "
            "which is not on the firmware's live list"
        )
        assert description.field not in REBOOTING_FIELDS[description.section]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_selects_go_unavailable_with_the_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that nothing can be written while the node is unreachable."""
    await setup_select_platform(hass, mock_config_entry)
    assert (state := hass.states.get(BUZZER_MODE))
    assert state.state != STATE_UNAVAILABLE

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(BUZZER_MODE))
    assert state.state == STATE_UNAVAILABLE
