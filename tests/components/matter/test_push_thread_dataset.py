"""Test handing a Thread network to a Matter border router."""

import asyncio
from base64 import b64encode
from typing import Any
from unittest.mock import MagicMock

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from freezegun.api import FrozenDateTimeFactory
from matter_server.client.exceptions import NotConnected
from matter_server.common.errors import UnknownError
import pytest
from pytest_homeassistant.common import MockUser, async_fire_time_changed
from python_otbr_api import tlv_parser

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.thread import async_add_dataset, dataset_store
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import set_node_attribute_and_notify, setup_integration_with_node_fixture

from tests.components.thread import DATASET_1, DATASET_2

pytestmark = pytest.mark.usefixtures(
    "short_border_agent_discovery_timeout", "mock_thread_discovery"
)

# The preferred network
DATASET = bytes.fromhex(DATASET_1)
NETWORK_1 = {
    "network_name": "OpenThreadDemo",
    "extended_pan_id": "1111111122222222",
    "pan_id": "1234",
    "channel": 15,
}
UNPROVISIONED = {"1/1106/4": NullValue}


@pytest.fixture(autouse=True)
def answer_reads_from_the_cache(matter_client: MagicMock) -> None:
    """Have a router answer reads with what it reported last."""

    async def read(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        attributes = matter_client.get_node(node_id).node_data.attributes
        return {path: attributes.get(path) for path in attribute_path}

    matter_client.read_attribute.side_effect = read


def _router_answers(matter_client: MagicMock, **values: Any) -> None:
    """Have the router answer reads of its dataset timestamps with these."""
    paths = {"active": "1/1106/4", "pending": "1/1106/5"}

    async def read(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        return {path: values.get(kind) for kind, path in paths.items()}

    matter_client.read_attribute.side_effect = read


@pytest.fixture(name="preferred_network")
async def preferred_network_fixture(hass: HomeAssistant) -> None:
    """Have DATASET_1 as the preferred network."""
    await async_add_dataset(hass, "test", DATASET_1)
    store = await dataset_store.async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets))


def _device_id(hass: HomeAssistant) -> str:
    """Return the device id of the only Matter node."""
    return next(
        device.id
        for device in dr.async_get(hass).devices
        if any(identifier[0] == "matter" for identifier in device.identifiers)
    )


def _entity_id(hass: HomeAssistant, key: str) -> str:
    """Return the entity id of the entity with this schema key."""
    return next(
        entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.platform == "matter" and key in entry.unique_id
    )


def _commands(matter_client: MagicMock) -> list[Any]:
    """Return the commands sent to the device."""
    return [
        call.kwargs["command"]
        for call in matter_client.send_device_command.call_args_list
    ]


async def _push(hass: HomeAssistant, **data: str) -> None:
    """Call the push action for the border router."""
    await hass.services.async_call(
        "matter",
        "push_thread_dataset",
        {"device_id": _device_id(hass), **data},
        blocking=True,
    )


async def _get(hass: HomeAssistant) -> dict[str, Any]:
    """Call the get action for the border router."""
    response = await hass.services.async_call(
        "matter",
        "get_thread_dataset",
        {"device_id": _device_id(hass)},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return response


@pytest.mark.usefixtures("preferred_network")
async def test_provisioned_router_gets_pending_dataset(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A router with a network receives the dataset as pending."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    await _push(hass)

    commands = _commands(matter_client)
    assert len(commands) == 1
    assert isinstance(
        commands[0],
        clusters.ThreadBorderRouterManagement.Commands.SetPendingDatasetRequest,
    )
    pending = tlv_parser.parse_tlv(commands[0].pendingDataset.hex())
    active = tlv_parser.parse_tlv(DATASET_1)
    # The network is the dataset's, with what a pending dataset needs added.
    for tag in (
        tlv_parser.MeshcopTLVType.EXTPANID,
        tlv_parser.MeshcopTLVType.NETWORKKEY,
        tlv_parser.MeshcopTLVType.CHANNEL,
    ):
        assert pending[tag] == active[tag]
    delay = pending[tlv_parser.MeshcopTLVType.DELAYTIMER]
    assert isinstance(delay, tlv_parser.DelayTimer)
    assert delay.delay == 300_000
    for tag in (
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP,
        tlv_parser.MeshcopTLVType.PENDINGTIMESTAMP,
    ):
        timestamp = pending[tag]
        assert isinstance(timestamp, tlv_parser.Timestamp)
        assert timestamp.seconds == 1


@pytest.mark.usefixtures("preferred_network")
async def test_unprovisioned_router_is_adopted_under_failsafe(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A router without a network is provisioned inside a fail-safe window."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )

    await _push(hass)

    commands = _commands(matter_client)
    assert len(commands) == 3
    assert isinstance(commands[0], clusters.GeneralCommissioning.Commands.ArmFailSafe)
    assert commands[0].expiryLengthSeconds == 120
    assert isinstance(
        commands[1],
        clusters.ThreadBorderRouterManagement.Commands.SetActiveDatasetRequest,
    )
    assert commands[1].activeDataset == DATASET
    assert isinstance(
        commands[2], clusters.GeneralCommissioning.Commands.CommissioningComplete
    )


@pytest.mark.usefixtures("preferred_network")
async def test_the_preferred_network_is_pushed_by_default(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Without a dataset, the preferred network is pushed."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    await _push(hass)

    pending = tlv_parser.parse_tlv(_commands(matter_client)[0].pendingDataset.hex())
    extpanid = tlv_parser.MeshcopTLVType.EXTPANID
    assert pending[extpanid] == tlv_parser.parse_tlv(DATASET_1)[extpanid]


async def test_no_dataset_and_no_preferred_network(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Without a dataset or a preferred network, nothing is sent."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "no_preferred_dataset"
    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("preferred_network")
async def test_a_stored_dataset_is_pushed_by_its_id(
    hass: HomeAssistant, matter_client: MagicMock, stored_dataset: str
) -> None:
    """A dataset ID picks a dataset of the Thread store over the preferred one."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )

    await _push(hass, dataset_id=stored_dataset)

    assert _commands(matter_client)[1].activeDataset == bytes.fromhex(DATASET_2)


@pytest.mark.usefixtures("preferred_network")
async def test_the_pending_dataset_is_newer_than_the_routers(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The pending dataset's timestamps pass the router's active timestamp."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/1106/4": 40 << 16},
    )
    # The router has moved on since it last reported.
    _router_answers(matter_client, active=41 << 16)

    await _push(hass)

    pending = tlv_parser.parse_tlv(_commands(matter_client)[0].pendingDataset.hex())
    for tag in (
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP,
        tlv_parser.MeshcopTLVType.PENDINGTIMESTAMP,
    ):
        timestamp = pending[tag]
        assert isinstance(timestamp, tlv_parser.Timestamp)
        assert timestamp.seconds == 42


async def test_a_newer_dataset_keeps_its_own_timestamp(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A dataset already newer than the router's keeps its timestamp, ticks and all."""
    tlvs = tlv_parser.parse_tlv(DATASET_2)
    tag = tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP
    tlvs[tag] = tlv_parser.Timestamp.from_values(tag, seconds=10, ticks=7)
    await async_add_dataset(hass, "test", tlv_parser.encode_tlv(tlvs))
    store = await dataset_store.async_get_store(hass)
    dataset_id = next(iter(store.datasets))
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    await _push(hass, dataset_id=dataset_id)

    pending = tlv_parser.parse_tlv(_commands(matter_client)[0].pendingDataset.hex())
    for tag in (
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP,
        tlv_parser.MeshcopTLVType.PENDINGTIMESTAMP,
    ):
        timestamp = pending[tag]
        assert isinstance(timestamp, tlv_parser.Timestamp)
        assert (timestamp.seconds, timestamp.ticks) == (10, 7)


@pytest.mark.usefixtures("preferred_network")
async def test_a_router_without_pan_change_keeps_its_network(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A router that cannot change its running network is told nothing."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/1106/65532": 0},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "thread_pan_change_unsupported"
    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("preferred_network")
async def test_a_router_without_a_network_but_a_pending_one_is_not_adopted(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A dataset scheduled to replace the adopted one would undo the adoption."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/1106/4": NullValue, "1/1106/5": 2},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "thread_dataset_pending"
    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("preferred_network")
async def test_a_router_with_a_pending_change_is_left_alone(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A second pending dataset would race the first; nothing is sent."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    # Written a moment ago: the router has it, the cache does not yet.
    _router_answers(matter_client, active=1, pending=2)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "thread_dataset_pending"
    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("preferred_network")
async def test_a_router_that_does_not_answer_the_read_is_not_written_to(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A push goes by what the router says: one that does not answer is not written to."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/1106/5": 2},
    )
    matter_client.read_attribute.side_effect = NotConnected()

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "thread_dataset_push_failed"
    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("preferred_network")
async def test_one_transaction_per_node(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A push while another is under way on the node is refused."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )
    release = asyncio.Event()

    async def slow(**kwargs: Any) -> None:
        await release.wait()

    matter_client.send_device_command.side_effect = slow
    first = hass.async_create_task(_push(hass))
    while not matter_client.send_device_command.called:
        await asyncio.sleep(0)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "node_reconfiguring"
    release.set()
    await first
    # The node is free again.
    await _push(hass)


@pytest.mark.parametrize(
    ("action", "data"),
    [("push_thread_dataset", {}), ("get_thread_dataset", {})],
)
@pytest.mark.usefixtures("preferred_network")
async def test_the_actions_are_admin_only(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_read_only_user: MockUser,
    action: str,
    data: dict[str, str],
) -> None:
    """Only an administrator can read or hand out a network key."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "matter",
            action,
            {"device_id": _device_id(hass), **data},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
            return_response=action == "get_thread_dataset",
        )

    assert not matter_client.send_device_command.called


async def test_an_unknown_dataset_id_is_rejected(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A dataset ID the Thread store does not know is rejected before anything is sent."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _push(hass, dataset_id="no-such-dataset")

    assert exc_info.value.translation_key == "unknown_dataset"
    assert not matter_client.send_device_command.called


async def test_a_child_device_is_no_border_router(
    hass: HomeAssistant,
    matter_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A child device of a node stands for its own endpoints, not the node's."""
    await setup_integration_with_node_fixture(
        hass, "eve_energy_20ecn4101", matter_client
    )
    entry = entity_registry.async_get("switch.eve_energy_20ecn4101_top")
    assert entry is not None
    assert entry.device_id is not None

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            "matter",
            "push_thread_dataset",
            {"device_id": entry.device_id},
            blocking=True,
        )

    assert exc_info.value.translation_key == "not_a_border_router"


@pytest.mark.usefixtures("preferred_network")
async def test_failed_adoption_disarms_the_failsafe(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """When the dataset write fails, the fail-safe is disarmed right away."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )

    async def fail_dataset(command: Any, **kwargs: Any) -> None:
        if isinstance(
            command,
            clusters.ThreadBorderRouterManagement.Commands.SetActiveDatasetRequest,
        ):
            raise UnknownError("busy")

    matter_client.send_device_command.side_effect = fail_dataset

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "thread_dataset_push_failed"
    assert exc_info.value.translation_placeholders == {"error": "busy"}
    commands = _commands(matter_client)
    assert isinstance(commands[-1], clusters.GeneralCommissioning.Commands.ArmFailSafe)
    assert commands[-1].expiryLengthSeconds == 0


@pytest.mark.usefixtures("preferred_network")
async def test_an_unanswered_adoption_is_reported_unconfirmed(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A completion whose answer got lost may have been committed: no failure is claimed."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )

    async def lose_completion(command: Any, **kwargs: Any) -> Any:
        if isinstance(
            command, clusters.GeneralCommissioning.Commands.CommissioningComplete
        ):
            raise NotConnected
        return {"errorCode": 0}

    matter_client.send_device_command.side_effect = lose_completion

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "thread_adoption_unconfirmed"
    commands = _commands(matter_client)
    assert isinstance(commands[-1], clusters.GeneralCommissioning.Commands.ArmFailSafe)
    assert commands[-1].expiryLengthSeconds == 0


@pytest.mark.usefixtures("preferred_network")
async def test_a_failed_disarm_keeps_the_write_error(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A disarm that fails too does not hide why the adoption failed."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )
    matter_client.send_device_command.side_effect = [
        None,
        UnknownError("busy"),
        NotConnected(),
    ]

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_placeholders == {"error": "busy"}


@pytest.mark.parametrize(
    ("responses", "error"),
    [
        ([{"errorCode": 4, "debugText": "busy"}], "ArmFailSafe returned error 4 busy"),
        # A failed completion is disarmed like a failed write.
        (
            [None, None, {"errorCode": 1}, None],
            "CommissioningComplete returned error 1",
        ),
    ],
)
@pytest.mark.usefixtures("preferred_network")
async def test_a_failed_commissioning_step_is_reported(
    hass: HomeAssistant,
    matter_client: MagicMock,
    responses: list[dict[str, Any] | None],
    error: str,
) -> None:
    """An error code inside a commissioning response fails the push."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )
    matter_client.send_device_command.side_effect = responses

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "thread_dataset_push_failed"
    assert exc_info.value.translation_placeholders == {"error": error}
    # A failed arm is not followed by a dataset write.
    assert len(_commands(matter_client)) == len(responses)


@pytest.mark.parametrize(
    "disarm",
    [NotConnected(), {"errorCode": 4, "debugText": "busy"}],
    ids=["unanswered", "refused"],
)
@pytest.mark.usefixtures("preferred_network")
async def test_a_router_left_armed_stays_held(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    disarm: Exception | dict[str, Any],
) -> None:
    """A router whose fail-safe could not be disarmed is held until it expires."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )
    matter_client.send_device_command.side_effect = [
        None,
        UnknownError("busy"),
        disarm,
    ]
    with pytest.raises(HomeAssistantError):
        await _push(hass)

    matter_client.send_device_command.side_effect = None
    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)
    assert exc_info.value.translation_key == "node_reconfiguring"

    freezer.tick(121)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await _push(hass)


@pytest.mark.usefixtures("preferred_network")
async def test_a_late_lost_arm_holds_the_router_from_its_end(
    hass: HomeAssistant, matter_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """An arm may have taken until its attempt ended: the hold runs from then."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )

    async def arm(command: Any, **kwargs: Any) -> None:
        if isinstance(command, clusters.GeneralCommissioning.Commands.ArmFailSafe):
            freezer.tick(100)
            raise NotConnected

    matter_client.send_device_command.side_effect = arm
    with pytest.raises(HomeAssistantError):
        await _push(hass)

    matter_client.send_device_command.side_effect = None
    freezer.tick(100)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)
    assert exc_info.value.translation_key == "node_reconfiguring"

    freezer.tick(21)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await _push(hass)


@pytest.mark.usefixtures("preferred_network")
async def test_a_push_ends_with_the_entry(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Unloading Matter cancels a push under way and frees the router."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )
    entry = hass.config_entries.async_entries("matter")[0]
    release = asyncio.Event()
    answer = matter_client.read_attribute.side_effect

    async def slow(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        await release.wait()
        return await answer(node_id, attribute_path)

    # Still reading the timestamps: nothing has been sent.
    matter_client.read_attribute.side_effect = slow
    push = hass.async_create_task(_push(hass))
    while not matter_client.read_attribute.called:
        await asyncio.sleep(0)

    await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(HomeAssistantError) as exc_info:
        await push
    assert exc_info.value.translation_key == "matter_unloaded"

    # Cancelled before anything was sent: the router is free again.
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    matter_client.read_attribute.side_effect = answer
    await _push(hass)


@pytest.mark.usefixtures("preferred_network")
async def test_a_cancelled_caller_cancels_the_push(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A caller that is cancelled itself sees the cancellation, not an error."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )
    release = asyncio.Event()
    answer = matter_client.read_attribute.side_effect

    async def slow(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        await release.wait()
        return await answer(node_id, attribute_path)

    # Still reading the timestamps: nothing has been sent.
    matter_client.read_attribute.side_effect = slow
    push = hass.async_create_task(_push(hass))
    while not matter_client.read_attribute.called:
        await asyncio.sleep(0)

    push.cancel()

    with pytest.raises(asyncio.CancelledError):
        await push
    await hass.async_block_till_done()

    # Cancelled before anything was sent: the router is free again.
    matter_client.read_attribute.side_effect = answer
    await _push(hass)


@pytest.mark.parametrize(
    "blocked",
    [
        clusters.GeneralCommissioning.Commands.ArmFailSafe,
        clusters.ThreadBorderRouterManagement.Commands.SetActiveDatasetRequest,
    ],
    ids=["while-arming", "after-arming"],
)
@pytest.mark.usefixtures("preferred_network")
async def test_a_push_cancelled_once_arming_holds_the_router(
    hass: HomeAssistant, matter_client: MagicMock, blocked: type
) -> None:
    """A router whose fail-safe may be armed stays held when the push is cancelled."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )
    entry = hass.config_entries.async_entries("matter")[0]
    release = asyncio.Event()
    sent = asyncio.Event()

    async def slow(command: Any, **kwargs: Any) -> None:
        if isinstance(command, blocked):
            sent.set()
            await release.wait()

    matter_client.send_device_command.side_effect = slow
    push = hass.async_create_task(_push(hass))
    await sent.wait()

    await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(HomeAssistantError):
        await push

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    matter_client.send_device_command.side_effect = None
    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)
    assert exc_info.value.translation_key == "node_reconfiguring"


@pytest.mark.usefixtures("preferred_network")
async def test_a_failed_pending_write_is_reported(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A pending dataset the server fails to write fails the push."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    matter_client.send_device_command.side_effect = NotConnected()

    with pytest.raises(HomeAssistantError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_placeholders == {"error": "NotConnected"}


async def test_unknown_device_is_rejected(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A stale device ID is user input, not a runtime failure."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            "matter",
            "push_thread_dataset",
            {"device_id": "no-such-device"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_device"


@pytest.mark.usefixtures("preferred_network")
async def test_a_device_without_a_border_router_is_rejected(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Only a border router can be handed a network."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _push(hass)

    assert exc_info.value.translation_key == "not_a_border_router"
    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("preferred_network")
async def test_get_thread_dataset_returns_active(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The get action tells the active network apart, without its key."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    matter_client.send_device_command.return_value = {
        "dataset": b64encode(DATASET).decode()
    }
    store = await dataset_store.async_get_store(hass)

    response = await _get(hass)

    assert response == {
        "active": {
            **NETWORK_1,
            # The dataset's own timestamp: one second, as in DATASET_1
            "timestamp": 1 << 16,
            "dataset_id": next(iter(store.datasets)),
        },
        "pending": None,
    }
    network_key = tlv_parser.parse_tlv(DATASET_1)[
        tlv_parser.MeshcopTLVType.NETWORKKEY
    ].data.hex()
    assert network_key not in str(response).lower()
    # The pending dataset does not exist, so only the active one is read.
    commands = _commands(matter_client)
    assert len(commands) == 1
    assert isinstance(
        commands[0],
        clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest,
    )


async def test_get_thread_dataset_reads_what_the_router_has(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A pending dataset just written is read, though the cache does not know it yet."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    _router_answers(matter_client, active=1, pending=2)
    matter_client.send_device_command.return_value = {
        "dataset": b64encode(DATASET).decode()
    }

    response = await _get(hass)

    assert response["pending"]["extended_pan_id"] == NETWORK_1["extended_pan_id"]
    assert any(
        isinstance(
            command,
            clusters.ThreadBorderRouterManagement.Commands.GetPendingDatasetRequest,
        )
        for command in _commands(matter_client)
    )


async def test_get_thread_dataset_fails_when_the_read_fails(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The cache may miss a change another controller scheduled: it does not stand in."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    matter_client.read_attribute.side_effect = NotConnected()

    with pytest.raises(HomeAssistantError) as exc_info:
        await _get(hass)

    assert exc_info.value.translation_key == "thread_dataset_read_failed"
    assert not matter_client.send_device_command.called


async def test_get_thread_dataset_with_unparsable_tlvs(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A dataset whose TLVs do not parse is reported as unusable."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    matter_client.send_device_command.return_value = {
        "dataset": b64encode(b"\x0e\x08\x00").decode()
    }

    with pytest.raises(HomeAssistantError) as exc_info:
        await _get(hass)

    assert exc_info.value.translation_key == "thread_dataset_unusable"


async def test_get_thread_dataset_returns_pending(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """While a migration is scheduled, the pending dataset is read too."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/1106/4": NullValue, "1/1106/5": 2},
    )
    tlvs = tlv_parser.parse_tlv(DATASET_1)
    tag = tlv_parser.MeshcopTLVType.PENDINGTIMESTAMP
    tlvs[tag] = tlv_parser.Timestamp.from_values(tag, seconds=3)
    pending = bytes.fromhex(tlv_parser.encode_tlv(tlvs))
    matter_client.send_device_command.return_value = {
        "dataset": b64encode(pending).decode()
    }

    assert await _get(hass) == {
        "active": None,
        "pending": {
            **NETWORK_1,
            # The dataset's own pending timestamp, not the one cached
            "timestamp": 3 << 16,
            "dataset_id": None,
        },
    }
    commands = _commands(matter_client)
    assert len(commands) == 1
    assert isinstance(
        commands[0],
        clusters.ThreadBorderRouterManagement.Commands.GetPendingDatasetRequest,
    )


@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        (NotConnected(), "thread_dataset_read_failed"),
        ([{"dataset": None}], "thread_dataset_unusable"),
    ],
)
async def test_a_failed_get_is_reported(
    hass: HomeAssistant,
    matter_client: MagicMock,
    side_effect: Exception | list[dict[str, None]],
    translation_key: str,
) -> None:
    """A read the server fails, or an unusable answer, fails the get action."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    matter_client.send_device_command.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await _get(hass)

    assert exc_info.value.translation_key == translation_key


async def test_the_adopt_button_is_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, matter_client: MagicMock
) -> None:
    """Pressing the button reconfigures a network, so it starts disabled."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    entry = entity_registry.async_get(_entity_id(hass, "ThreadNetworkAdoptButton"))
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "preferred_network")
async def test_the_adopt_button_pushes_the_preferred_network(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The button adopts an unprovisioned router into the preferred network."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _entity_id(hass, "ThreadNetworkAdoptButton")},
        blocking=True,
    )

    assert _commands(matter_client)[1].activeDataset == bytes.fromhex(DATASET_1)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "preferred_network")
async def test_only_an_administrator_adopts_a_router(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_admin_user: MockUser,
    non_admin_user: MockUser,
) -> None:
    """Adopting hands the router the preferred network, as the admin-only action does."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )

    async def press(user: MockUser) -> None:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _entity_id(hass, "ThreadNetworkAdoptButton")},
            blocking=True,
            context=Context(user_id=user.id),
        )

    with pytest.raises(Unauthorized):
        await press(non_admin_user)
    assert not matter_client.send_device_command.called

    await press(hass_admin_user)
    assert _commands(matter_client)[1].activeDataset == bytes.fromhex(DATASET_1)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_the_adopt_button_without_a_preferred_network(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Without a preferred network, the press fails and nothing is sent."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, override_attributes=UNPROVISIONED
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _entity_id(hass, "ThreadNetworkAdoptButton")},
            blocking=True,
        )

    assert exc_info.value.translation_key == "no_preferred_dataset"
    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "preferred_network")
async def test_the_adopt_button_leaves_a_running_network_alone(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The button adopts; moving a running network takes the action."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _entity_id(hass, "ThreadNetworkAdoptButton")},
            blocking=True,
        )

    assert exc_info.value.translation_key == "thread_network_present"
    assert not matter_client.send_device_command.called


async def test_migration_pending_sensor(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The sensor is on while the router has a pending dataset."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    entity_id = _entity_id(hass, "ThreadMigrationPending")
    assert hass.states.get(entity_id).state == STATE_OFF

    await set_node_attribute_and_notify(
        hass, matter_client, node, endpoint=1, cluster_id=1106, attribute_id=5, value=2
    )
    assert hass.states.get(entity_id).state == STATE_ON

    await set_node_attribute_and_notify(
        hass,
        matter_client,
        node,
        endpoint=1,
        cluster_id=1106,
        attribute_id=5,
        value=NullValue,
    )
    assert hass.states.get(entity_id).state == STATE_OFF
