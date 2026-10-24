"""Test the Thread dataset import from Matter border routers."""

import asyncio
from base64 import b64encode
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from freezegun.api import FrozenDateTimeFactory
from matter_server.client.models import device_types
from matter_server.common.errors import NodeNotExists, NodeNotReady, UnknownError
from matter_server.common.models import EventType
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from python_otbr_api import tlv_parser

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.matter import thread_border_router
from homeassistant.components.matter.thread_border_router import (
    THREAD_DATASET_READ_ATTEMPTS,
    THREAD_DATASET_RETRY_DELAY,
    async_store_dataset,
)
from homeassistant.components.thread import async_add_dataset, dataset_store
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    load_and_parse_node_fixture,
    set_node_attribute,
    set_node_attribute_and_notify,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)

from tests.components.thread import DATASET_1, DATASET_2


@pytest.fixture(autouse=True)
def short_border_agent_discovery_timeout() -> Generator[None]:
    """Skip the store's 30 s border agent discovery wait, which never elapses under a frozen clock."""
    with patch.object(dataset_store, "BORDER_AGENT_DISCOVERY_TIMEOUT", 0):
        yield


@pytest.fixture(autouse=True)
def mock_thread_discovery(mock_async_zeroconf: MagicMock) -> MagicMock:
    """Adding a dataset starts Thread discovery, which would open a real socket."""
    return mock_async_zeroconf


def _with_timestamp(dataset: str, seconds: int) -> bytes:
    """Return a dataset with its active timestamp replaced."""
    items = tlv_parser.parse_tlv(dataset)
    items[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP] = tlv_parser.Timestamp.from_values(
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP, seconds=seconds
    )
    return bytes.fromhex(tlv_parser.encode_tlv(items))


# The fixture's border router is on DATASET_1's network.
DATASET_TLV = bytes.fromhex(DATASET_1)
DATASET_NEWER = _with_timestamp(DATASET_1, 2)
DATASET_NEWEST = _with_timestamp(DATASET_1, 3)
NETWORK = "1111111122222222"

BORDER_AGENT_ID = "0102030405060708090a0b0c0d0e0f10"
EXT_ADDRESS_HEX = "1122334455667788"


def _response(dataset: bytes) -> dict[str, str]:
    """Return a DatasetResponse as the client delivers it."""
    return {"dataset": b64encode(dataset).decode()}


def _dataset_reads(matter_client: MagicMock) -> int:
    """Return how often the active dataset was requested."""
    return sum(
        isinstance(
            call.kwargs.get("command"),
            clusters.ThreadBorderRouterManagement.Commands.GetActiveDatasetRequest,
        )
        for call in matter_client.send_device_command.call_args_list
    )


def _import_button(hass: HomeAssistant) -> str | None:
    """Return the entity id of the import button, if there is one."""
    return next(
        (
            entry.entity_id
            for entry in er.async_get(hass).entities.values()
            if entry.platform == "matter"
            and "ThreadDatasetImportButton" in entry.unique_id
        ),
        None,
    )


async def _press_import(hass: HomeAssistant) -> None:
    """Press the import button."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _import_button(hass)},
        blocking=True,
    )


async def _stored(hass: HomeAssistant) -> dataset_store.DatasetEntry | None:
    """Return the stored dataset of the router's network."""
    store = await dataset_store.async_get_store(hass)
    return next(
        (
            entry
            for entry in store.datasets.values()
            if entry.extended_pan_id == NETWORK
        ),
        None,
    )


@pytest.fixture(name="dataset_response")
def dataset_response_fixture(matter_client: MagicMock) -> dict[str, str]:
    """Make GetActiveDatasetRequest return DATASET_1."""
    response = _response(DATASET_TLV)
    matter_client.send_device_command.return_value = response
    return response


@pytest.fixture(name="newer_response")
def newer_response_fixture(matter_client: MagicMock) -> dict[str, str]:
    """Make GetActiveDatasetRequest return a newer DATASET_1."""
    response = _response(DATASET_NEWER)
    matter_client.send_device_command.return_value = response
    return response


@pytest.fixture(name="known_network")
async def known_network_fixture(hass: HomeAssistant) -> None:
    """Have the store hold the router's network already, from another source."""
    await async_add_dataset(hass, "test", DATASET_1)


@pytest.fixture(name="preferred_network")
async def preferred_network_fixture(hass: HomeAssistant) -> None:
    """Have a preferred network, so the store skips its discovery task."""
    await async_add_dataset(hass, "test", DATASET_2)
    store = await dataset_store.async_get_store(hass)
    store.preferred_dataset = next(
        entry.id
        for entry in store.datasets.values()
        if entry.extended_pan_id == "1111111122222233"
    )


async def test_border_router_is_not_read_without_a_press(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A border router of an unknown network is left alone until the user imports it."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    assert _dataset_reads(matter_client) == 0
    assert await _stored(hass) is None
    assert not hass.config_entries.async_entries("thread")


@pytest.mark.parametrize(
    "device_type",
    [
        device_types.NetworkInfrastructureManager.device_type,
        device_types.ThreadBorderRouter.device_type,
    ],
)
async def test_import_button_for_both_border_router_device_types(
    hass: HomeAssistant, matter_client: MagicMock, device_type: int
) -> None:
    """Both border router device types get the import button."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/29/0": [{"0": device_type, "1": 1}]},
    )

    assert _import_button(hass) is not None


async def test_no_import_button_without_a_border_router(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A node without the TBRM cluster has no import button."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    assert _import_button(hass) is None


async def test_pressing_the_button_imports_the_dataset(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """The button reads the dataset by command and adds it to the store."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    await _press_import(hass)

    assert _dataset_reads(matter_client) == 1
    entry = await _stored(hass)
    assert entry is not None
    assert entry.source == "matter"
    assert entry.tlv == DATASET_TLV.hex()
    assert entry.preferred_border_agent_id == BORDER_AGENT_ID
    assert entry.preferred_extended_address == EXT_ADDRESS_HEX


async def test_the_first_import_sets_up_the_thread_integration(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """Thread is set up by the first import, once."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    assert "thread" not in hass.config.components

    await _press_import(hass)
    assert len(hass.config_entries.async_entries("thread")) == 1
    assert "thread" in hass.config.components

    await _press_import(hass)
    assert len(hass.config_entries.async_entries("thread")) == 1


async def test_an_existing_thread_entry_is_left_alone(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """An import does not add a Thread entry next to one that exists."""
    MockConfigEntry(domain="thread").add_to_hass(hass)
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    await _press_import(hass)

    assert len(hass.config_entries.async_entries("thread")) == 1
    assert await _stored(hass) is not None


async def test_an_unprovisioned_router_cannot_be_imported(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A router without a network answers with an empty dataset; the press fails."""
    matter_client.send_device_command.return_value = {"dataset": ""}
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "thread_network_missing"
    assert await _stored(hass) is None
    assert not hass.config_entries.async_entries("thread")


async def test_an_imported_network_follows_its_router(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """After the import, a new active dataset timestamp is read; an unchanged one is not."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await _press_import(hass)
    assert _dataset_reads(matter_client) == 1

    set_node_attribute(node, 1, 1106, 3, False)
    await trigger_subscription_callback(
        hass, matter_client, EventType.NODE_UPDATED, node
    )
    assert _dataset_reads(matter_client) == 1

    matter_client.send_device_command.return_value = _response(DATASET_NEWER)
    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


async def test_a_router_of_an_unknown_network_is_not_followed(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """Without an import, a dataset change on the router is not read."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 0
    assert await _stored(hass) is None


async def test_a_network_imported_later_is_followed(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """A router skipped for an unknown network is read once the network is stored."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 0

    await async_add_dataset(hass, "test", DATASET_1)
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 1
    entry = await _stored(hass)
    assert entry is not None
    assert entry.source == "test"
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network")
async def test_a_network_known_from_elsewhere_is_read_at_setup(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """A router of a network the store holds is read when the integration starts."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 1
    entry = await _stored(hass)
    assert entry is not None
    assert entry.source == "test"
    assert entry.tlv == DATASET_NEWER.hex()


async def test_dataset_reread_on_extended_address_update(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A new extended address under the same dataset is read and stored."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await _press_import(hass)

    set_node_attribute(node, 1, 53, 63, 0x8877665544332211)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        0x8877665544332211,
        node_id=node.node_id,
        attribute_path="1/53/63",
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.preferred_extended_address == "8877665544332211"


@pytest.mark.usefixtures("known_network")
async def test_dataset_changed_during_a_read_is_read_again(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A change during a read is read once that read ends; the overtaken answer is dropped."""
    answer = asyncio.Event()
    answers = [DATASET_NEWER, DATASET_NEWEST]

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        return _response(answers.pop(0))

    matter_client.send_device_command.side_effect = read
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    assert _dataset_reads(matter_client) == 1

    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    assert _dataset_reads(matter_client) == 1

    answer.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWEST.hex()


@pytest.mark.usefixtures("known_network")
async def test_the_store_is_loaded_before_the_read(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The store is loaded when the command is sent, so the add does not wait."""
    loaded_at_read: list[bool] = []

    async def read(**kwargs: Any) -> dict[str, str]:
        loaded_at_read.append(
            isinstance(
                hass.data.get(dataset_store.DATA_STORE), dataset_store.DatasetStore
            )
        )
        return _response(DATASET_NEWER)

    matter_client.send_device_command.side_effect = read
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert loaded_at_read == [True]


async def test_null_ext_address_omits_preference_pair(hass: HomeAssistant) -> None:
    """A router without a Thread stack reports ExtAddress as NullValue, which is truthy."""
    endpoint = MagicMock()
    endpoint.node.node_id = 1
    endpoint.endpoint_id = 1
    endpoint.get_attribute_value.side_effect = lambda _, attr: {
        clusters.ThreadBorderRouterManagement.Attributes.BorderAgentID: b"\x01" * 16,
        clusters.ThreadNetworkDiagnostics.Attributes.ExtAddress: NullValue,
    }[attr]

    with (
        patch(
            "homeassistant.components.matter.thread_border_router.async_add_dataset"
        ) as add_dataset,
        patch(
            "homeassistant.components.matter.thread_border_router.async_ensure_thread_setup"
        ),
    ):
        await async_store_dataset(hass, endpoint, DATASET_TLV)

    add_dataset.assert_called_once()
    kwargs = add_dataset.call_args.kwargs
    assert "preferred_border_agent_id" not in kwargs
    assert "preferred_extended_address" not in kwargs


async def test_a_change_during_a_press_is_read_afterwards(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A dataset change while the pressed import is read is read once the import is done."""
    answer = asyncio.Event()
    answers = [DATASET_TLV, DATASET_NEWER]

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        return _response(answers.pop(0))

    matter_client.send_device_command.side_effect = read
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    entry = hass.config_entries.async_entries("matter")[0]
    press = hass.async_create_background_task(
        entry.runtime_data.thread_datasets.async_import(node.endpoints[1]), "press"
    )
    while _dataset_reads(matter_client) < 1:
        await asyncio.sleep(0)

    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    answer.set()
    await press
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry_stored = await _stored(hass)
    assert entry_stored is not None
    assert entry_stored.tlv == DATASET_NEWER.hex()


async def test_the_dataset_is_stored_before_thread_is_set_up(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """Setting Thread up runs after the store write, not between the checks and it."""
    stored_at_setup: list[bool] = []
    original = thread_border_router.async_ensure_thread_setup

    async def ensure(hass_: HomeAssistant) -> None:
        stored_at_setup.append(await _stored(hass_) is not None)
        await original(hass_)

    with patch.object(thread_border_router, "async_ensure_thread_setup", ensure):
        await setup_integration_with_node_fixture(
            hass, "thread_border_router", matter_client
        )
        await _press_import(hass)

    assert stored_at_setup == [True]
    assert hass.config_entries.async_entries("thread")


async def test_coexists_with_the_otbr_integration(
    hass: HomeAssistant, matter_client: MagicMock, dataset_response: dict[str, str]
) -> None:
    """A network the otbr integration owns is followed but keeps its source and preference."""
    await async_add_dataset(
        hass,
        "otbr",
        DATASET_TLV.hex(),
        preferred_border_agent_id="aabbccddeeff00112233445566778899",
        preferred_extended_address="8877665544332211",
    )

    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 1
    await _press_import(hass)

    store = await dataset_store.async_get_store(hass)
    (entry,) = store.datasets.values()
    assert entry.source == "otbr"
    assert entry.preferred_border_agent_id == "aabbccddeeff00112233445566778899"
    assert entry.preferred_extended_address == "8877665544332211"


@pytest.mark.parametrize(
    ("error", "translation_key", "placeholder"),
    [
        (
            NodeNotReady("node not ready"),
            "thread_dataset_read_failed",
            "node not ready",
        ),
        (UnknownError(), "thread_dataset_read_failed", "UnknownError"),
    ],
)
async def test_a_failed_read_fails_the_press(
    hass: HomeAssistant,
    matter_client: MagicMock,
    error: Exception,
    translation_key: str,
    placeholder: str,
) -> None:
    """A read the server fails is reported to the user, with the server's reason."""
    matter_client.send_device_command.side_effect = error
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {"error": placeholder}
    assert await _stored(hass) is None


@pytest.mark.parametrize(
    "response",
    [
        None,
        {"dataset": None},
        {"dataset": "%%%not-base64%%%"},
        # Non-alphabet characters ahead of a valid value: a lenient decoder
        # would drop them and import the corrupted remainder.
        {"dataset": "!" + b64encode(DATASET_TLV).decode()},
    ],
)
async def test_an_unusable_response_fails_the_press(
    hass: HomeAssistant,
    matter_client: MagicMock,
    response: dict[str, str | None] | None,
) -> None:
    """A response without a readable dataset is reported, nothing imported."""
    matter_client.send_device_command.return_value = response
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "thread_dataset_unusable"
    assert await _stored(hass) is None


async def test_a_dataset_the_store_rejects_fails_the_press(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The store's refusal of a dataset reaches the user."""
    without_xpan = DATASET_1.replace("02081111111122222222", "")
    matter_client.send_device_command.return_value = _response(
        bytes.fromhex(without_xpan)
    )
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError, match="Invalid dataset"):
        await _press_import(hass)


@pytest.mark.usefixtures("known_network")
@pytest.mark.parametrize(
    "response",
    [None, {"dataset": None}, {"dataset": "%%%not-base64%%%"}],
)
async def test_an_unusable_response_is_logged_when_following(
    hass: HomeAssistant,
    matter_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    response: dict[str, str | None] | None,
) -> None:
    """Following a router, an unusable response is logged and read again on the next change."""
    matter_client.send_device_command.return_value = response
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 1
    assert "Could not import the Thread dataset of node 90 endpoint 1" in caplog.text
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_1

    # Not counted as done: an unchanged node update reads again.
    matter_client.send_device_command.return_value = _response(DATASET_NEWER)
    await trigger_subscription_callback(
        hass, matter_client, EventType.NODE_UPDATED, node
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network")
async def test_a_dataset_the_store_rejects_is_logged_when_following(
    hass: HomeAssistant, matter_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Following a router, a dataset the store refuses is logged."""
    without_xpan = DATASET_1.replace("02081111111122222222", "")
    matter_client.send_device_command.return_value = _response(
        bytes.fromhex(without_xpan)
    )

    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        "Could not import the Thread dataset of node 90 endpoint 1: Invalid dataset"
        in caplog.text
    )


@pytest.mark.usefixtures("known_network")
async def test_a_late_extended_pan_id_report_is_read(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """A router whose network is reported after its timestamp is read on that report."""
    node = await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/53/4": None},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 0

    await set_node_attribute_and_notify(
        hass,
        matter_client,
        node,
        endpoint=1,
        cluster_id=53,
        attribute_id=4,
        value=0x1111111122222222,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 1
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network")
async def test_a_router_that_left_for_an_unknown_network_adds_nothing(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """An answer from a network the store does not hold is not added while following."""
    answer = asyncio.Event()

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        return _response(bytes.fromhex(DATASET_2))

    matter_client.send_device_command.side_effect = read
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    assert _dataset_reads(matter_client) == 1

    set_node_attribute(node, 1, 53, 4, 0x1111111122222233)
    answer.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    store = await dataset_store.async_get_store(hass)
    assert [entry.extended_pan_id for entry in store.datasets.values()] == [NETWORK]


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_a_dataset_deleted_during_a_read_is_not_restored(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A network deleted while its router was being read stays deleted.

    Imported again, with older credentials, the router is read on the next
    event even though nothing about it changed.
    """
    answer = asyncio.Event()

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        return _response(DATASET_NEWER)

    matter_client.send_device_command.side_effect = read
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()
    assert _dataset_reads(matter_client) == 1

    store = await dataset_store.async_get_store(hass)
    entry = await _stored(hass)
    assert entry is not None
    store.async_delete(entry.id)
    answer.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert await _stored(hass) is None

    await async_add_dataset(hass, "test", DATASET_1)
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_a_dataset_deleted_after_a_read_is_followed_again_once_imported(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """A network deleted after its router was read is followed again once imported.

    Nothing about the router changes; the store's dataset for its network
    changing hands is what calls for a read.
    """
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 1

    store = await dataset_store.async_get_store(hass)
    entry = await _stored(hass)
    assert entry is not None
    store.async_delete(entry.id)
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 1

    await async_add_dataset(hass, "test", DATASET_1)
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_dataset_read_retried_after_node_not_ready(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A read failing with NodeNotReady is retried after a delay."""
    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")

    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_1

    matter_client.send_device_command.side_effect = None
    matter_client.send_device_command.return_value = _response(DATASET_NEWER)

    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_dataset_retry_cancelled_on_unload(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading the entry cancels a pending retry."""
    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")

    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    reads_before_unload = _dataset_reads(matter_client)

    entry = hass.config_entries.async_entries("matter")[0]
    assert await hass.config_entries.async_unload(entry.entry_id)

    matter_client.send_device_command.side_effect = None
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _dataset_reads(matter_client) == reads_before_unload


@pytest.mark.usefixtures("known_network")
async def test_endpoint_removal_forgets_import_state(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """ENDPOINT_REMOVED drops the router's state, so it is read afresh when it returns."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    reads = _dataset_reads(matter_client)
    assert reads == 1

    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.ENDPOINT_REMOVED,
        data={"node_id": node.node_id, "endpoint_id": 1},
    )
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == reads + 1


@pytest.mark.usefixtures("known_network")
async def test_a_read_outlived_by_its_endpoint_stores_nothing(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """An answer arriving after the endpoint was removed is not stored."""
    answer = asyncio.Event()

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        return _response(DATASET_NEWER)

    matter_client.send_device_command.side_effect = read
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.ENDPOINT_REMOVED,
        data={"node_id": node.node_id, "endpoint_id": 1},
    )
    answer.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_1


@pytest.mark.usefixtures("known_network")
async def test_node_removal_forgets_import_state(
    hass: HomeAssistant, matter_client: MagicMock, newer_response: dict[str, str]
) -> None:
    """NODE_REMOVED drops the state of every endpoint of the node."""
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    reads = _dataset_reads(matter_client)

    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_REMOVED, data=node.node_id
    )
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_ADDED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == reads + 1


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_retry_skipped_when_node_removed_meanwhile(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A pending retry whose node is gone by firing time does nothing."""
    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    reads = _dataset_reads(matter_client)

    original_get_node = matter_client.get_node.side_effect
    matter_client.get_node.side_effect = NodeNotExists(node.node_id)
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    matter_client.get_node.side_effect = original_get_node

    assert _dataset_reads(matter_client) == reads


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_retry_rearmed_not_duplicated(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A second failure while a retry is pending replaces the timer."""
    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    reads_while_failing = _dataset_reads(matter_client)

    matter_client.send_device_command.side_effect = None
    matter_client.send_device_command.return_value = _response(DATASET_NEWER)
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == reads_while_failing + 1
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_server_errors_are_retried_a_few_times(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A read the server fails is tried a few more times, then logged."""
    matter_client.send_device_command.side_effect = UnknownError("timed out")
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    for _ in range(THREAD_DATASET_READ_ATTEMPTS):
        freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == THREAD_DATASET_READ_ATTEMPTS
    assert (
        "Could not read the Thread dataset of node 90 endpoint 1: timed out"
        in caplog.text
    )

    # The next change reads again.
    matter_client.send_device_command.side_effect = None
    matter_client.send_device_command.return_value = _response(DATASET_NEWER)
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_each_border_router_endpoint_retries_on_its_own(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A retry reads only its endpoint; a node's other failing router keeps its count."""
    matter_client.send_device_command.side_effect = UnknownError("timed out")
    fixture = load_and_parse_node_fixture("thread_border_router")
    second_endpoint = {
        f"2/{path[2:]}": value
        for path, value in fixture["attributes"].items()
        if path.startswith("1/")
    }
    second_endpoint["0/29/3"] = [1, 2]
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, second_endpoint
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _dataset_reads(matter_client) == 2

    for _ in range(THREAD_DATASET_READ_ATTEMPTS):
        freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2 * THREAD_DATASET_READ_ATTEMPTS
    for endpoint_id in (1, 2):
        assert (
            f"Could not read the Thread dataset of node 90 endpoint {endpoint_id}"
            in caplog.text
        )


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_an_unchanged_update_during_the_first_reads_discards_nothing(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A node update while its routers are first read does not re-read them.

    Which stored dataset a read kept in step is recorded when it completes;
    judged before that, the reads would discard their answers and re-read
    each other without end.
    """
    answer = asyncio.Event()

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        return _response(DATASET_NEWER)

    matter_client.send_device_command.side_effect = read
    fixture = load_and_parse_node_fixture("thread_border_router")
    second_endpoint = {
        f"2/{path[2:]}": value
        for path, value in fixture["attributes"].items()
        if path.startswith("1/")
    }
    second_endpoint["0/29/3"] = [1, 2]
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client, second_endpoint
    )
    await hass.async_block_till_done()
    assert _dataset_reads(matter_client) == 2

    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    answer.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_a_dataset_change_gets_its_own_retries(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A dataset change starts a fresh set of attempts."""
    matter_client.send_device_command.side_effect = UnknownError("timed out")
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    for _ in range(THREAD_DATASET_READ_ATTEMPTS - 2):
        freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    # One attempt left for the old dataset; the new one starts afresh.
    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "Could not read the Thread dataset" not in caplog.text

    matter_client.send_device_command.side_effect = None
    matter_client.send_device_command.return_value = _response(DATASET_NEWER)
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network")
async def test_a_failed_read_overtaken_by_a_change_reads_again_at_once(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A read that fails after a change overtook it is read again straight away."""
    answer = asyncio.Event()
    answers: list[Exception | dict[str, str]] = [
        UnknownError("timed out"),
        _response(DATASET_NEWER),
    ]

    async def read(**kwargs: Any) -> dict[str, str]:
        await answer.wait()
        result = answers.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    matter_client.send_device_command.side_effect = read
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    set_node_attribute(node, 1, 1106, 4, 2)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.ATTRIBUTE_UPDATED,
        2,
        node_id=node.node_id,
        attribute_path="1/1106/4",
    )
    answer.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _dataset_reads(matter_client) == 2
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()


@pytest.mark.usefixtures("known_network", "preferred_network")
async def test_offline_border_router_not_polled(
    hass: HomeAssistant,
    matter_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An unavailable node is not read, and a pending retry stops on it."""
    matter_client.send_device_command.side_effect = NodeNotReady("node not ready")
    node = await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    reads = _dataset_reads(matter_client)

    node.node_data.available = False
    freezer.tick(THREAD_DATASET_RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _dataset_reads(matter_client) == reads

    matter_client.send_device_command.side_effect = None
    matter_client.send_device_command.return_value = _response(DATASET_NEWER)
    node.node_data.available = True
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=node
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = await _stored(hass)
    assert entry is not None
    assert entry.tlv == DATASET_NEWER.hex()
