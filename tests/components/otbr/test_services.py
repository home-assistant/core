"""Test the Open Thread Border Router actions."""

import asyncio
from http import HTTPStatus
import re
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from aiohttp.client_reqrep import ConnectionKey
from freezegun.api import FrozenDateTimeFactory
import pytest
import python_otbr_api
from python_otbr_api import tlv_parser
from python_otbr_api.tlv_parser import DelayTimer, MeshcopTLVType, Timestamp

from homeassistant.components.otbr import (
    silabs_multiprotocol as otbr_silabs_multiprotocol,
)
from homeassistant.components.otbr.types import OTBRConfigEntry
from homeassistant.components.otbr.util import (
    INSECURE_NETWORK_KEYS,
    ISSUED_TIMESTAMPS_KEY,
    ISSUED_TIMESTAMPS_STORAGE_KEY,
    async_get_dataset_lock,
    async_get_issued_timestamps,
)
from homeassistant.components.thread import (
    async_add_dataset,
    async_get_store,
    dataset_store,
)
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from . import BASE_URL, DATASET_CH16

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

# A different network from the one under test: ts 1003, channel 15. Carries
# every network-defining TLV plus a wake-up channel TLV (0x4a), which the
# router keeps, to prove the PUT body is the target re-stamped and no more.
TARGET = (
    "0e080000000003eb0000000300000f4a0300001035060004001fffe002081111111122222222"
    "0708fd111111222222220510aaaaaaaaaaaaaaaabbbbbbbbbbbbbbbb030f4f70656e546872"
    "6561642048412032010212340410ccccccccccccccccdddddddddddddddd0c0402a0f7f8"
)

# A third network: TARGET under another extended PAN ID.
THIRD_TARGET = tlv_parser.encode_tlv(
    {
        **tlv_parser.parse_tlv(TARGET),
        MeshcopTLVType.EXTPANID: tlv_parser.MeshcopTLVItem(
            MeshcopTLVType.EXTPANID, bytes.fromhex("3333333344444444")
        ),
    }
)


pytestmark = pytest.mark.usefixtures("multiprotocol_addon_manager_mock")


async def call_migrate(hass: HomeAssistant, **data) -> dict:
    """Invoke the migrate_network action."""
    return await hass.services.async_call(
        "otbr",
        "migrate_network",
        data,
        blocking=True,
        return_response=True,
    )


def expected_pending(target_hex: str, seconds: int, delay_ms: int) -> dict:
    """Return the dataset the router must receive for a migration."""
    expected = tlv_parser.parse_tlv(target_hex)
    expected[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=seconds
    )
    expected[MeshcopTLVType.PENDINGTIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.PENDINGTIMESTAMP, seconds=seconds
    )
    expected[MeshcopTLVType.DELAYTIMER] = DelayTimer.from_milliseconds(delay_ms)
    return expected


def mock_pending_endpoint(
    aioclient_mock: AiohttpClientMocker,
    in_flight: str | None = None,
    put_status: HTTPStatus = HTTPStatus.CREATED,
    put_json: dict[str, Any] | None = None,
) -> None:
    """Mock the router's pending-dataset endpoint."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    # A router that writes the pending dataset locally; the tests of one that
    # registers it with the leader announce that with a version.
    aioclient_mock.get(
        f"{BASE_URL}/.well-known/thread/br-rest", status=HTTPStatus.NOT_FOUND
    )
    if in_flight is None:
        aioclient_mock.get(
            f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT
        )
    else:
        aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", text=in_flight)
    aioclient_mock.put(
        f"{BASE_URL}/node/dataset/pending", status=put_status, json=put_json
    )


def pending_calls(aioclient_mock: AiohttpClientMocker) -> list:
    """Return the PUT calls the router received."""
    return [call for call in aioclient_mock.mock_calls if call[0] == "PUT"]


@pytest.fixture(name="second_router")
async def second_router_fixture(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> OTBRConfigEntry:
    """Set up a second border router, both routers' pending endpoints mocked."""
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    return next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )


async def test_a_pending_dataset_is_checked_before_the_network_is_read(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
) -> None:
    """The pending dataset is read before the network the router is on.

    Read the other way round, a pending dataset expiring in between would
    leave a snapshot of the network the mesh has just left.
    """
    mock_pending_endpoint(aioclient_mock, in_flight=TARGET)
    get_active_dataset_tlvs.side_effect = HomeAssistantError("not read")

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)

    assert exc_info.value.translation_key == "pending_dataset_in_place"


async def test_network_is_migrated(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The pending dataset is the target network, only re-stamped."""
    mock_pending_endpoint(aioclient_mock)

    response = await call_migrate(hass, dataset=TARGET)

    assert response == {
        "status": "migrating",
        "delay": 300,
        "network_name": "OpenThread HA 2",
    }

    # Newer than both the network being left (ts 1) and the target (ts 1003),
    # and taken verbatim otherwise - including the wakeup-channel TLV.
    puts = pending_calls(aioclient_mock)
    assert len(puts) == 1
    assert tlv_parser.parse_tlv(puts[0][2]) == expected_pending(TARGET, 1004, 300000)

    # The store learns what the network will run - the re-stamped dataset
    # without the pending machinery - bound to this router.
    store = await async_get_store(hass)
    entries = [
        entry
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    ]
    assert len(entries) == 1
    stored = tlv_parser.parse_tlv(entries[0].tlv)
    expected = expected_pending(TARGET, 1004, 300000)
    del expected[MeshcopTLVType.PENDINGTIMESTAMP]
    del expected[MeshcopTLVType.DELAYTIMER]
    assert stored == expected


async def test_migration_repoints_preferred_dataset(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Migrating away from the preferred network moves the preferred pointer.

    Everything handing out Thread credentials starts from the preferred
    dataset; left behind it would keep sharing a network nobody runs.
    """
    mock_pending_endpoint(aioclient_mock)
    await async_add_dataset(hass, "test", DATASET_CH16.hex())
    store = await async_get_store(hass)
    source_id = next(iter(store.datasets.values())).id
    store.preferred_dataset = source_id

    await call_migrate(hass, dataset=TARGET)

    preferred = store.datasets[store.preferred_dataset]
    assert preferred.extended_pan_id.lower() == "1111111122222222"


async def test_migration_sets_preferred_dataset_when_none_is_chosen(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Without a preferred network yet, the target becomes it.

    The store picks a preference on its own once a router's first dataset
    has been through discovery; a migration started inside that wait must
    not see the abandoned network chosen when the wait ends.
    """
    mock_pending_endpoint(aioclient_mock)
    store = await async_get_store(hass)
    assert store.preferred_dataset is None

    await call_migrate(hass, dataset=TARGET)

    preferred = store.datasets[store.preferred_dataset]
    assert preferred.extended_pan_id.lower() == "1111111122222222"


async def test_migration_sets_preferred_dataset_for_unknown_source(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
) -> None:
    """The promotion also covers a router whose network the store never saw.

    A router re-provisioned by another controller runs a network the store
    has no entry for; with no preference chosen yet, the migration target
    still becomes it.
    """
    mock_pending_endpoint(aioclient_mock)
    foreign = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    foreign[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("5555666677778888")
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(tlv_parser.encode_tlv(foreign))
    store = await async_get_store(hass)
    assert store.preferred_dataset is None

    await call_migrate(hass, dataset=TARGET)

    preferred = store.datasets[store.preferred_dataset]
    assert preferred.extended_pan_id.lower() == "1111111122222222"


async def test_migration_leaves_an_unrelated_preference_alone(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A preference for a third network is not moved by the migration."""
    mock_pending_endpoint(aioclient_mock)
    unrelated = dict(tlv_parser.parse_tlv(TARGET))
    unrelated[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("3333333344444444")
    )
    await async_add_dataset(hass, "test", tlv_parser.encode_tlv(unrelated))
    store = await async_get_store(hass)
    unrelated_id = next(
        entry.id
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "3333333344444444"
    )
    store.preferred_dataset = unrelated_id

    await call_migrate(hass, dataset=TARGET)

    assert store.preferred_dataset == unrelated_id


async def test_credentials_are_rotated_on_the_same_network(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A dataset that keeps the network but replaces its key is a migration."""
    mock_pending_endpoint(aioclient_mock)

    rotated = tlv_parser.parse_tlv(DATASET_CH16.hex())
    rotated[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, bytes.fromhex("11111111222222223333333344444444")
    )
    rotated_hex = tlv_parser.encode_tlv(rotated)

    response = await call_migrate(hass, dataset=rotated_hex)

    assert response["status"] == "migrating"
    puts = pending_calls(aioclient_mock)
    assert len(puts) == 1
    # Active and target timestamps are both 1 here.
    assert tlv_parser.parse_tlv(puts[0][2]) == expected_pending(rotated_hex, 2, 300000)


async def test_rotation_sets_preferred_dataset_when_none_is_chosen(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A rotation promotes the network when no preference exists yet.

    Source and target are the same network then, so resolving the target
    entry must not depend on it differing from the source.
    """
    mock_pending_endpoint(aioclient_mock)

    rotated = tlv_parser.parse_tlv(DATASET_CH16.hex())
    rotated[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, bytes.fromhex("11111111222222223333333344444444")
    )
    store = await async_get_store(hass)
    assert store.preferred_dataset is None

    await call_migrate(hass, dataset=tlv_parser.encode_tlv(rotated))

    preferred = store.datasets[store.preferred_dataset]
    assert preferred.extended_pan_id.lower() == (
        rotated[MeshcopTLVType.EXTPANID].data.hex().lower()
    )


async def test_migration_refuses_while_a_pending_dataset_is_in_flight(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """A pending dataset in flight refuses the migration outright.

    Superseding it would race the delay timer on every device already
    holding it, so a late replacement can split the mesh, and it would
    silently undo whatever that dataset was doing. Nothing is written and
    nothing is recorded; the user is told to wait it out.
    """
    mock_pending_endpoint(aioclient_mock, in_flight=TARGET)

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)

    assert exc_info.value.translation_key == "pending_dataset_in_place"
    assert not pending_calls(aioclient_mock)
    assert ISSUED_TIMESTAMPS_STORAGE_KEY not in hass_storage


async def test_pending_dataset_appearing_mid_flight_is_surfaced(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A pending dataset that appears between the read and the write refuses.

    The early check cannot see it, so the refusal comes back from the router
    (the If-None-Match precondition) through the library, and must surface
    as the same error rather than a generic failure.
    """
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.PRECONDITION_FAILED)

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)

    assert exc_info.value.translation_key == "pending_dataset_in_place"

    # The router refused, so no migration is under way: the propagation
    # window recorded before the write is handed back, and a retry once the
    # other pending dataset is gone is not refused as still in flight.
    mock_pending_endpoint(aioclient_mock)
    response = await call_migrate(hass, dataset=TARGET)
    assert response["status"] == "migrating"


async def test_migration_window_is_measured_from_the_routers_acceptance(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A slow write does not shorten the recorded propagation window.

    The router's delay timer starts when it accepts the dataset, so the
    window is re-anchored once the request completes; measured from before
    the request, a 600s delay behind an 8s request would have ended while
    the mesh was still counting down.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)

    async def slow_put(method, url, data):
        freezer.tick(8)
        return AiohttpClientMockResponse(method, url, status=HTTPStatus.CREATED)

    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", side_effect=slow_put)
    await call_migrate(hass, dataset=TARGET, delay=600)

    mock_pending_endpoint(aioclient_mock)
    freezer.tick(595)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "5"}

    freezer.tick(5)
    assert (await call_migrate(hass, dataset=TARGET))["status"] == "migrating"


async def test_a_write_that_never_arrived_frees_the_migration_window(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A lost connection over a router that took nothing does not block.

    The window is opened before the write, so a connection that dies has to
    be resolved rather than assumed: a router that answers and holds no
    pending dataset never got it, and refusing retries for the whole delay
    would be a self-inflicted outage.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(
        f"{BASE_URL}/.well-known/thread/br-rest", status=HTTPStatus.NOT_FOUND
    )
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", exc=aiohttp.ClientError)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)

    # The retry is a normal migration, not a refusal.
    mock_pending_endpoint(aioclient_mock)
    response = await call_migrate(hass, dataset=TARGET)

    assert response["status"] == "migrating"


async def test_a_write_that_never_arrived_records_nothing(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A dropped connection and no pending dataset on the router: never written.

    A router that writes the dataset locally holds it for the whole delay,
    so none there within the delay says the write never arrived. Nothing is
    recorded, and the migration is not kept as one still to be settled.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(
        f"{BASE_URL}/.well-known/thread/br-rest", status=HTTPStatus.NOT_FOUND
    )
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", exc=aiohttp.ClientError)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)

    issued = await async_get_issued_timestamps(hass)
    assert issued.get("f642646da209b1c0") == (0, 0)
    assert issued.seconds_in_flight("f642646da209b1c0") == 0
    assert (
        issued.migration_source("1111111122222222", otbr_config_entry_multipan) is None
    )

    mock_pending_endpoint(aioclient_mock)
    await call_migrate(hass, dataset=TARGET)
    stamp = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[-1][2])[
        MeshcopTLVType.ACTIVETIMESTAMP
    ]
    assert stamp.seconds == 1004


async def test_a_write_the_delay_outlived_keeps_its_stamp(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The stamp of a write the router no longer holds stays the floor.

    Once the delay has run out by the time the router is asked, no pending
    dataset there can also mean written and applied already. Only the window
    is handed back; the next migration still steps above the stamp, which
    the mesh may run.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(
        f"{BASE_URL}/.well-known/thread/br-rest", status=HTTPStatus.NOT_FOUND
    )
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)

    async def slow_failure(method, url, data):
        freezer.tick(301)
        return AiohttpClientMockResponse(method, url, exc=aiohttp.ClientError)

    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", side_effect=slow_failure)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)

    issued = await async_get_issued_timestamps(hass)
    assert issued.get("f642646da209b1c0") == (1004, 0)
    assert issued.seconds_in_flight("f642646da209b1c0") == 0

    mock_pending_endpoint(aioclient_mock)
    await call_migrate(hass, dataset=TARGET)
    stamp = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[-1][2])[
        MeshcopTLVType.ACTIVETIMESTAMP
    ]
    assert stamp.seconds == 1005


async def test_a_timeout_before_the_write_records_nothing(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A timeout of the library's reads before the write leaves no window.

    The library reports a timeout of the write itself as an unknown outcome,
    so a bare one comes from the reads before it: nothing was sent. The
    record is put back, or every retry would be refused for the delay.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    # This action's own read answers; the library's, before its write, times out.
    answers: list[HTTPStatus | None] = [HTTPStatus.NO_CONTENT, None]

    async def pending_get(method, url, data):
        if (status := answers.pop(0)) is None:
            raise TimeoutError
        return AiohttpClientMockResponse(method, url, status=status)

    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", side_effect=pending_get)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.CREATED)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)

    assert not pending_calls(aioclient_mock)
    assert not answers
    issued = await async_get_issued_timestamps(hass)
    assert issued.get("f642646da209b1c0") == (0, 0)
    assert issued.seconds_in_flight("f642646da209b1c0") == 0


async def test_the_persisted_window_covers_the_router_request(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A crash during the write cannot leave a window that ends too early.

    Home Assistant can stop between the router accepting the dataset and the
    deadline being re-anchored afterwards, leaving only what was written
    before the request. The router starts its delay when it accepts, so that
    record has to cover the request as well.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)

    persisted: list[float] = []

    async def slow_put(method, url, data):
        # What a crash right here would leave behind, at the moment the
        # router accepts the write and starts counting down.
        freezer.tick(8)
        (record,) = hass_storage[ISSUED_TIMESTAMPS_STORAGE_KEY]["data"].values()
        persisted.append(record["until"] - dt_util.utcnow().timestamp())
        return AiohttpClientMockResponse(method, url, status=HTTPStatus.CREATED)

    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", side_effect=slow_put)
    await call_migrate(hass, dataset=TARGET, delay=60)

    assert persisted and persisted[0] >= 60


async def test_a_recorded_migration_keeps_no_credentials(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """The record keeps the dataset sent only until the migration is recorded.

    Until then it is what the target is known as, and the router it was handed
    to is what settles it. Afterwards the store holds the dataset, and the
    record would otherwise carry the network key and PSKC on indefinitely.
    """
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)

    (record,) = hass_storage[ISSUED_TIMESTAMPS_STORAGE_KEY]["data"].values()
    assert record["router"] == otbr_config_entry_multipan
    sent = tlv_parser.parse_tlv(record["dataset"])
    assert (
        sent[MeshcopTLVType.NETWORKKEY]
        == (tlv_parser.parse_tlv(TARGET)[MeshcopTLVType.NETWORKKEY])
    )

    freezer.tick(301)
    mock_pending_endpoint(aioclient_mock)
    await call_migrate(hass, dataset=TARGET)

    (record,) = hass_storage[ISSUED_TIMESTAMPS_STORAGE_KEY]["data"].values()
    assert record["target"] == "1111111122222222"
    assert "router" not in record
    assert "dataset" not in record


async def test_a_lost_connection_keeps_the_migration_window(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A write that may have landed keeps the mesh marked as migrating.

    With no answer from the router the dataset may well be propagating, and
    refusing a retry for the delay is the safe side of that uncertainty.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(
        f"{BASE_URL}/.well-known/thread/br-rest", status=HTTPStatus.NOT_FOUND
    )

    # Nothing before the write (this action checks, then the library checks
    # again), the written dataset after it: the connection died reporting a
    # write the router did take.
    pending = [None, None, TARGET]

    async def pending_get(method, url, data):
        answer = pending[0] if len(pending) == 1 else pending.pop(0)
        if answer is None:
            return AiohttpClientMockResponse(method, url, status=HTTPStatus.NO_CONTENT)
        return AiohttpClientMockResponse(method, url, text=answer)

    async def slow_failure(method, url, data):
        freezer.tick(8)
        return AiohttpClientMockResponse(method, url, exc=aiohttp.ClientError)

    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", side_effect=pending_get)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", side_effect=slow_failure)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET, delay=600)

    # The write may have landed as late as the moment the connection died,
    # so the window is measured from there, not from before the request.
    mock_pending_endpoint(aioclient_mock)
    freezer.tick(595)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "5"}


async def test_delay_is_applied(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A non-default delay reaches the router and the response.

    Above the 300s the leader insists on for a network key change, so this
    is the delay that is sent rather than one that gets raised.
    """
    mock_pending_endpoint(aioclient_mock)

    response = await call_migrate(hass, dataset=TARGET, delay=600)

    assert response["delay"] == 600
    puts = pending_calls(aioclient_mock)
    assert tlv_parser.parse_tlv(puts[0][2]) == expected_pending(TARGET, 1004, 600000)


async def test_already_on_network(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Migrating to the network the router already runs does nothing."""
    mock_pending_endpoint(aioclient_mock)

    response = await call_migrate(hass, dataset=DATASET_CH16.hex())

    assert response == {"status": "already_on_network"}
    assert not pending_calls(aioclient_mock)


async def test_an_unanswered_registration_keeps_the_migration_window(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A router that got no answer from the leader may have migrated the mesh.

    A border router that registers the dataset with the Thread leader
    reports no verdict in time as its own status, and the dataset may well
    have been accepted. That is the dropped-connection case with a name on
    it: the window is kept, measured from now, and the user is told why.
    """
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET, delay=600)
    assert exc_info.value.translation_key == "pending_dataset_unanswered"

    mock_pending_endpoint(aioclient_mock)
    freezer.tick(595)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "5"}


async def test_an_unanswered_migration_is_finished_once_the_router_is_on_its_target(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A router found on the network it was sent to settles an unanswered write.

    No answer from the leader records nothing but the window, since nothing
    may have been written. Once the router reports the target, the migrated
    dataset is stored and the preferred pointer moved, before a call without
    a dataset reads that pointer: it would otherwise migrate the mesh straight
    back onto the network left behind.
    """
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "pending_dataset_unanswered"

    # The mesh switched after all: the router runs the re-stamped target.
    migrated = dict(tlv_parser.parse_tlv(TARGET))
    migrated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1004
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(
        tlv_parser.encode_tlv(migrated)
    )
    freezer.tick(301)
    mock_pending_endpoint(aioclient_mock)

    assert (await call_migrate(hass, dataset=TARGET))["status"] == (
        "already_on_network"
    )
    preferred = store.datasets[store.preferred_dataset]
    assert preferred.extended_pan_id.lower() == "1111111122222222"
    # The default target is the migrated network now, not the one left.
    assert (await call_migrate(hass))["status"] == "already_on_network"
    assert not pending_calls(aioclient_mock)


async def test_an_unanswered_migration_is_settled_against_what_was_sent(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The router's stamp is held against the dataset sent, not the floor.

    The network's floor can rise after the write, through a channel change on
    a router that stayed; the router found on the target with the stamp it
    was sent has switched regardless.
    """
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)
    issued = await async_get_issued_timestamps(hass)
    await issued.async_set("f642646da209b1c0", (2000, 0), until=0)

    migrated = dict(tlv_parser.parse_tlv(TARGET))
    migrated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1004
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(
        tlv_parser.encode_tlv(migrated)
    )
    freezer.tick(301)
    mock_pending_endpoint(aioclient_mock)

    assert (await call_migrate(hass, dataset=TARGET))["status"] == (
        "already_on_network"
    )
    preferred = store.datasets[store.preferred_dataset]
    assert preferred.extended_pan_id.lower() == "1111111122222222"


async def test_an_unanswered_migration_is_settled_at_the_routers_setup(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A restart inside the delay settles the migration at the router's setup.

    Its record is all that is left of it. The router found on the target when
    it is set up again moves the preferred pointer there, as the action would,
    rather than leaving it on the network left until the action is run again.
    """
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)
    issued = await async_get_issued_timestamps(hass)
    assert issued.sent("f642646da209b1c0") is not None

    migrated = dict(tlv_parser.parse_tlv(TARGET))
    migrated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1004
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(
        tlv_parser.encode_tlv(migrated)
    )
    freezer.tick(301)
    assert await hass.config_entries.async_reload(otbr_config_entry_multipan)
    await hass.async_block_till_done()

    preferred = store.datasets[store.preferred_dataset]
    assert preferred.extended_pan_id.lower() == "1111111122222222"
    assert issued.sent("f642646da209b1c0") is None
    assert (
        issued.migration_source("1111111122222222", otbr_config_entry_multipan) is None
    )


async def test_an_unanswered_channel_change_is_settled_by_its_router(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A channel change the router never answered is settled like a migration.

    Nothing showed whether the write landed, so the store kept the old
    channel; this router found running the dataset sent settles it before
    the default target is read, or the stored network would move the mesh
    straight back onto the old channel.
    """
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id
    mock_pending_endpoint(aioclient_mock)
    with (
        patch(
            "python_otbr_api.OTBR.set_channel",
            side_effect=python_otbr_api.PendingDatasetOutcomeUnknownError("lost"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=300)
    issued = await async_get_issued_timestamps(hass)
    assert (sent := issued.sent("f642646da209b1c0")) is not None

    get_active_dataset_tlvs.return_value = bytes.fromhex(sent)
    freezer.tick(301)
    mock_pending_endpoint(aioclient_mock)

    assert (await call_migrate(hass))["status"] == "already_on_network"
    assert pending_calls(aioclient_mock) == []
    assert issued.sent("f642646da209b1c0") is None
    stored = tlv_parser.parse_tlv(store.datasets[store.preferred_dataset].tlv)
    assert stored[MeshcopTLVType.CHANNEL].channel == 15
    assert stored[MeshcopTLVType.ACTIVETIMESTAMP].seconds == 2


async def test_a_router_on_the_target_all_along_settles_nothing(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Only the router the dataset was handed to can show that it landed.

    Another router on the target may have been there all along, and its stamp
    can reach the issued one on its own, through a channel change. Found
    there, it must not move the preferred pointer off the network the
    migration was to leave, nor forget that migration.
    """
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError):
        await call_migrate(
            hass, dataset=TARGET, config_entry=otbr_config_entry_multipan
        )
    freezer.tick(301)

    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    on_target = dict(tlv_parser.parse_tlv(TARGET))
    on_target[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1004
    )
    with (
        patch.object(
            thread_entry.runtime_data,
            "get_active_dataset_tlvs",
            return_value=bytes.fromhex(tlv_parser.encode_tlv(on_target)),
        ),
        patch.object(
            thread_entry.runtime_data, "get_pending_dataset_tlvs", return_value=None
        ),
    ):
        response = await call_migrate(
            hass, dataset=TARGET, config_entry=thread_entry.entry_id
        )

    assert response["status"] == "already_on_network"
    assert store.datasets[store.preferred_dataset].extended_pan_id.lower() == (
        "f642646da209b1c0"
    )
    issued = await async_get_issued_timestamps(hass)
    assert issued.migration_source("1111111122222222", otbr_config_entry_multipan) == (
        "f642646da209b1c0"
    )


async def test_a_finished_migration_refreshes_the_repair_issues(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A migration settled late refreshes the repair issues like one that answered.

    Both the router found on the new network and the others the dataset
    reached still carry the issues of the network left behind.
    """
    insecure = dict(tlv_parser.parse_tlv(TARGET))
    insecure[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, INSECURE_NETWORK_KEYS[0]
    )
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError):
        await call_migrate(
            hass,
            dataset=tlv_parser.encode_tlv(insecure),
            config_entry=otbr_config_entry_multipan,
        )
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    for entry_id in (otbr_config_entry_multipan, thread_entry.entry_id):
        assert not issue_registry.async_get_issue(
            domain="otbr", issue_id=f"insecure_thread_network_{entry_id}"
        )

    migrated = dict(insecure)
    migrated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1004
    )
    multipan_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert multipan_entry is not None
    freezer.tick(301)
    mock_pending_endpoint(aioclient_mock)
    with patch.object(
        multipan_entry.runtime_data,
        "get_active_dataset_tlvs",
        return_value=bytes.fromhex(tlv_parser.encode_tlv(migrated)),
    ):
        response = await call_migrate(
            hass,
            dataset=tlv_parser.encode_tlv(insecure),
            config_entry=otbr_config_entry_multipan,
        )

    assert response["status"] == "already_on_network"
    for entry_id in (otbr_config_entry_multipan, thread_entry.entry_id):
        assert issue_registry.async_get_issue(
            domain="otbr", issue_id=f"insecure_thread_network_{entry_id}"
        )


async def test_a_finished_migration_is_reported_even_when_the_call_fails(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A call that fails after settling an unanswered migration still reports it.

    The record is gone once the migration is recorded, so this call is the
    only one that will refresh the repair issues for it.
    """
    insecure = dict(tlv_parser.parse_tlv(TARGET))
    insecure[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, INSECURE_NETWORK_KEYS[0]
    )
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(insecure))

    migrated = dict(insecure)
    migrated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1004
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(
        tlv_parser.encode_tlv(migrated)
    )
    freezer.tick(301)
    mock_pending_endpoint(aioclient_mock)
    # A known network asked for with other settings is refused under the
    # lock, after the settlement; a dataset that does not parse never gets
    # that far.
    differ = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    differ[MeshcopTLVType.CHANNEL] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.CHANNEL, bytes.fromhex("00000b")
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(differ))

    assert exc_info.value.translation_key == "target_settings_differ"
    assert issue_registry.async_get_issue(
        domain="otbr", issue_id=f"insecure_thread_network_{otbr_config_entry_multipan}"
    )
    # Settled and reported; the next call is a plain no-op.
    assert (await call_migrate(hass, dataset=tlv_parser.encode_tlv(insecure)))[
        "status"
    ] == "already_on_network"


async def test_a_finished_migration_reports_a_discarded_store_write(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Newer stored credentials for the network found are reported, as after a write.

    The migration is settled first, pointer included, and nothing more is
    written in that call.
    """
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)
    # Newer credentials for the target were stored in the meantime.
    newer = dict(tlv_parser.parse_tlv(TARGET))
    newer[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=2000
    )
    await async_add_dataset(hass, "other", tlv_parser.encode_tlv(newer))

    migrated = dict(tlv_parser.parse_tlv(TARGET))
    migrated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1004
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(
        tlv_parser.encode_tlv(migrated)
    )
    freezer.tick(301)
    mock_pending_endpoint(aioclient_mock)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)

    assert exc_info.value.translation_key == "dataset_discarded"
    assert not pending_calls(aioclient_mock)
    assert store.datasets[store.preferred_dataset].extended_pan_id.lower() == (
        "1111111122222222"
    )
    # Settled: the next call is a plain no-op.
    assert (await call_migrate(hass, dataset=TARGET))["status"] == (
        "already_on_network"
    )


async def test_a_refused_retry_keeps_the_unanswered_migration(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A later write the router refuses puts back the migration still to settle.

    The retry may target another network through a router that never
    switched. Refused, it must not take the earlier migration's record with
    it: the router found on that network later would settle nothing, and a
    call without a dataset could migrate the mesh back.
    """
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)
    freezer.tick(301)

    other_target = dict(tlv_parser.parse_tlv(TARGET))
    other_target[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("3333333344444444")
    )
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.PRECONDITION_FAILED)
    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))

    migrated = dict(tlv_parser.parse_tlv(TARGET))
    migrated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1004
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(
        tlv_parser.encode_tlv(migrated)
    )
    mock_pending_endpoint(aioclient_mock)
    assert (await call_migrate(hass, dataset=TARGET))["status"] == (
        "already_on_network"
    )
    assert store.datasets[store.preferred_dataset].extended_pan_id.lower() == (
        "1111111122222222"
    )


async def test_a_lost_connection_to_a_leader_registering_router_keeps_the_window(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A router that registers with the leader is not asked what it holds.

    Its own copy of the pending dataset only arrives once the leader hands
    it back to the mesh, so right after a dropped connection "none" is not
    an answer. The window is kept on the strength of the API version alone,
    even though the router reports no pending dataset.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(
        f"{BASE_URL}/.well-known/thread/br-rest", json={"api": {"version": "0.6.0"}}
    )
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", exc=aiohttp.ClientError)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET, delay=600)

    mock_pending_endpoint(aioclient_mock)
    freezer.tick(595)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "5"}


async def test_a_refusal_carries_the_routers_reason(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The border router's own words for a refusal reach the user."""
    mock_pending_endpoint(
        aioclient_mock,
        put_status=HTTPStatus.CONFLICT,
        put_json={"title": "Conflict", "status": 409, "detail": "rejected by leader"},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)

    assert exc_info.value.translation_key == "pending_dataset_refused_reason"
    assert exc_info.value.translation_placeholders == {"reason": "rejected by leader"}


async def test_a_write_the_client_stopped_waiting_for_keeps_the_window(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Giving up on the write is not the same as the write having failed.

    The library reports a timeout on the write as an unknown outcome, the
    same as the router reporting no verdict from the leader, so the window
    is kept rather than the router being asked what it holds.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", exc=TimeoutError)

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET, delay=600)
    assert exc_info.value.translation_key == "pending_dataset_unanswered"

    mock_pending_endpoint(aioclient_mock)
    freezer.tick(595)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "migration_in_flight"


async def test_a_router_that_refuses_the_pending_dataset_says_so(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A refusal by the border router is reported as one, and hands back the window.

    A border router that registers the dataset with the Thread leader answers
    with a conflict when it is not attached, or when the leader rejects the
    dataset. Nothing was registered, so nothing is propagating, and a retry
    is not refused.
    """
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.CONFLICT)

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "pending_dataset_refused"

    mock_pending_endpoint(aioclient_mock)
    assert (await call_migrate(hass, dataset=TARGET))["status"] == "migrating"


async def test_router_refusal_is_reported(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A router refusing the pending dataset surfaces as an error."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(
        f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.BAD_REQUEST
    )

    # Setup recorded the router's own dataset; a failed migration must
    # not add or change anything.
    store = await async_get_store(hass)
    before = dict(store.datasets)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)

    assert store.datasets == before


@pytest.mark.parametrize(
    "bad_dataset",
    [
        "zz",
        # An empty dataset is a mistake, not a request for the default.
        "",
        # Truncated TLV: NETWORKNAME announcing 14 bytes, carrying 13.
        "030e4f70656e54687265616444656d",
    ],
)
async def test_invalid_dataset_is_rejected(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    bad_dataset: str,
) -> None:
    """A dataset that does not parse must not be sent anywhere."""
    aioclient_mock.clear_requests()

    with pytest.raises(ServiceValidationError) as exc_info:
        await call_migrate(hass, dataset=bad_dataset)
    assert exc_info.value.translation_key == "invalid_dataset"
    assert not aioclient_mock.mock_calls


async def test_incomplete_dataset_is_rejected(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A partial dataset would be completed by the router with random settings."""
    aioclient_mock.clear_requests()

    # Extended PAN id and network key only.
    with pytest.raises(ServiceValidationError) as exc_info:
        await call_migrate(
            hass,
            dataset="020811111111222222220510aaaaaaaaaaaaaaaabbbbbbbbbbbbbbbb",
        )
    assert exc_info.value.translation_key == "incomplete_dataset"
    assert "NETWORKNAME" in exc_info.value.translation_placeholders["missing"]
    assert not aioclient_mock.mock_calls


async def test_no_active_network(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    get_active_dataset_tlvs: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An unprovisioned router has no network to migrate."""
    mock_pending_endpoint(aioclient_mock)
    get_active_dataset_tlvs.return_value = None

    with pytest.raises(ServiceValidationError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "no_active_network"


async def test_no_preferred_dataset(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Without a dataset and without a preferred network there is no target."""
    mock_pending_endpoint(aioclient_mock)

    # Setup stored the router's dataset, but nothing marked one preferred.
    store = await async_get_store(hass)
    assert store.preferred_dataset is None

    with pytest.raises(ServiceValidationError) as exc_info:
        await call_migrate(hass)
    assert exc_info.value.translation_key == "no_preferred_dataset"


async def test_unknown_config_entry(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Naming a config entry that does not exist is a validation error."""
    aioclient_mock.clear_requests()

    with pytest.raises(ServiceValidationError):
        await call_migrate(hass, dataset=TARGET, config_entry="not-an-entry-id")


async def test_config_entry_is_honoured(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The named config entry is the router that is migrated."""
    mock_pending_endpoint(aioclient_mock)

    response = await call_migrate(
        hass, dataset=TARGET, config_entry=otbr_config_entry_multipan
    )

    assert response["status"] == "migrating"
    assert len(pending_calls(aioclient_mock)) == 1


async def test_pinned_channel_conflict(
    hass: HomeAssistant,
    multiprotocol_addon_manager_mock: Mock,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A migration off a channel another radio pins is refused."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 25

    with pytest.raises(ServiceValidationError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "channel_conflict"
    assert not pending_calls(aioclient_mock)


async def test_default_target_is_preferred_dataset(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Without a dataset, the preferred Thread network is the target."""
    mock_pending_endpoint(aioclient_mock)
    await async_add_dataset(hass, "test", TARGET)
    store = await async_get_store(hass)
    preferred_id = next(
        entry.id
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )
    store.preferred_dataset = preferred_id

    response = await call_migrate(hass)

    assert response["status"] == "migrating"
    puts = pending_calls(aioclient_mock)
    assert len(puts) == 1
    assert tlv_parser.parse_tlv(puts[0][2]) == expected_pending(TARGET, 1004, 300000)


async def test_targeting_the_current_network_also_refuses_while_pending(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """With a move away queued, re-targeting the current network refuses too.

    It must not be swallowed as "already on network": the mesh is about to
    leave it. But refusing is all this action can offer, since a counter
    dataset would race the delay timers the same as any other replacement.
    """
    mock_pending_endpoint(aioclient_mock, in_flight=TARGET)

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=DATASET_CH16.hex())

    assert exc_info.value.translation_key == "pending_dataset_in_place"
    assert not pending_calls(aioclient_mock)
    assert ISSUED_TIMESTAMPS_STORAGE_KEY not in hass_storage


async def test_concurrent_migrations_are_serialized(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Overlapping migrations of one mesh run one at a time, and only one runs.

    The lock serializes them; the second then finds the first still
    propagating and is refused rather than stamped newer, since a router that
    has not learned the first dataset yet would accept the second in its
    place and split the mesh.
    """
    mock_pending_endpoint(aioclient_mock)

    results = await asyncio.gather(
        call_migrate(hass, dataset=TARGET),
        call_migrate(hass, dataset=TARGET),
        return_exceptions=True,
    )

    outcomes = sorted(type(r).__name__ for r in results)
    assert outcomes == ["HomeAssistantError", "dict"]
    refused = next(r for r in results if isinstance(r, HomeAssistantError))
    assert refused.translation_key == "migration_in_flight"
    assert len(pending_calls(aioclient_mock)) == 1


async def test_second_migration_of_a_mesh_waits_for_the_first(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A mesh mid-migration refuses another until the delay has expired.

    The refusal names the time left; once the delay is over the next
    migration of the same mesh proceeds, stamped above the first.
    """
    mock_pending_endpoint(aioclient_mock)
    other_target = dict(tlv_parser.parse_tlv(TARGET))
    other_target[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("3333333344444444")
    )

    await call_migrate(hass, dataset=TARGET, delay=600)
    freezer.tick(570)

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))
    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "30"}
    assert len(pending_calls(aioclient_mock)) == 1

    freezer.tick(30)
    response = await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))

    assert response["status"] == "migrating"
    stamps = [
        tlv_parser.parse_tlv(put[2])[MeshcopTLVType.ACTIVETIMESTAMP].seconds
        for put in pending_calls(aioclient_mock)
    ]
    assert stamps == [1004, 1005]


async def test_a_network_still_receiving_a_mesh_cannot_move_on(
    hass: HomeAssistant,
    second_router: OTBRConfigEntry,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The network a migration moves onto is left alone until the mesh arrives.

    The mesh was sent that network as it is. Moved on in the meantime through
    a router already there, even with a shorter delay, the network it reaches
    has been left by everyone else. The record outlives the recording of the
    migration and a restart, like the window.
    """
    await call_migrate(
        hass, dataset=TARGET, delay=600, config_entry=otbr_config_entry_multipan
    )
    del hass.data[ISSUED_TIMESTAMPS_KEY]

    with patch.object(
        second_router.runtime_data,
        "get_active_dataset_tlvs",
        return_value=bytes.fromhex(TARGET),
    ):
        with pytest.raises(HomeAssistantError) as exc_info:
            await call_migrate(
                hass,
                dataset=THIRD_TARGET,
                delay=300,
                config_entry=second_router.entry_id,
            )
        assert exc_info.value.translation_key == "migration_in_flight"
        assert exc_info.value.translation_placeholders == {"remaining": "600"}
        assert len(pending_calls(aioclient_mock)) == 1

        freezer.tick(600)
        response = await call_migrate(
            hass,
            dataset=THIRD_TARGET,
            delay=300,
            config_entry=second_router.entry_id,
        )

    assert response["status"] == "migrating"
    assert [str(put[1]) for put in pending_calls(aioclient_mock)] == [
        f"{BASE_URL}/node/dataset/pending",
        "/dev/ttyAMA1/node/dataset/pending",
    ]


async def test_a_mesh_is_not_sent_onto_a_network_that_is_moving_on(
    hass: HomeAssistant,
    second_router: OTBRConfigEntry,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A network whose own mesh is counting down receives no other mesh.

    Sent there regardless, the mesh would arrive after the others have left,
    or on the channel they have left.
    """
    with patch.object(
        second_router.runtime_data,
        "get_active_dataset_tlvs",
        return_value=bytes.fromhex(TARGET),
    ):
        await call_migrate(
            hass,
            dataset=THIRD_TARGET,
            delay=600,
            config_entry=second_router.entry_id,
        )

        with pytest.raises(HomeAssistantError) as exc_info:
            await call_migrate(
                hass, dataset=TARGET, config_entry=otbr_config_entry_multipan
            )
        assert exc_info.value.translation_key == "target_in_flight"
        assert exc_info.value.translation_placeholders == {"remaining": "600"}
        assert len(pending_calls(aioclient_mock)) == 1

        freezer.tick(600)
        response = await call_migrate(
            hass, dataset=TARGET, config_entry=otbr_config_entry_multipan
        )

    assert response["status"] == "migrating"
    assert len(pending_calls(aioclient_mock)) == 2


async def test_a_second_mesh_may_join_a_network_still_receiving_one(
    hass: HomeAssistant,
    second_router: OTBRConfigEntry,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Meshes converging on one network do not wait for each other.

    Each arrives on the network it was sent, which is not moving; the second
    is stamped above the first, which the store knows by then.
    """
    await call_migrate(
        hass, dataset=TARGET, delay=600, config_entry=otbr_config_entry_multipan
    )
    with patch.object(
        second_router.runtime_data,
        "get_active_dataset_tlvs",
        return_value=bytes.fromhex(THIRD_TARGET),
    ):
        response = await call_migrate(
            hass, dataset=TARGET, config_entry=second_router.entry_id
        )

    assert response["status"] == "migrating"
    stamps = [
        tlv_parser.parse_tlv(put[2])[MeshcopTLVType.ACTIVETIMESTAMP].seconds
        for put in pending_calls(aioclient_mock)
    ]
    assert stamps == [1004, 1005]


async def test_a_second_mesh_is_not_sent_other_settings_for_a_receiving_network(
    hass: HomeAssistant,
    second_router: OTBRConfigEntry,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Meshes converging on one network must be sent the same settings.

    The same name with another key would have them arrive on networks that
    cannot talk to each other. What the first was sent is what the store
    holds for the target by then.
    """
    rekeyed = dict(tlv_parser.parse_tlv(TARGET))
    rekeyed[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, bytes.fromhex("99999999888888887777777766666666")
    )

    await call_migrate(
        hass, dataset=TARGET, delay=600, config_entry=otbr_config_entry_multipan
    )
    with patch.object(
        second_router.runtime_data,
        "get_active_dataset_tlvs",
        return_value=bytes.fromhex(THIRD_TARGET),
    ):
        with pytest.raises(HomeAssistantError) as exc_info:
            await call_migrate(
                hass,
                dataset=tlv_parser.encode_tlv(rekeyed),
                config_entry=second_router.entry_id,
            )
        assert exc_info.value.translation_key == "target_settings_differ"
        assert len(pending_calls(aioclient_mock)) == 1

        response = await call_migrate(
            hass, dataset=TARGET, config_entry=second_router.entry_id
        )

    assert response["status"] == "migrating"
    assert len(pending_calls(aioclient_mock)) == 2


async def test_an_unconfirmed_migration_counts_as_known_whatever_its_age(
    hass: HomeAssistant,
    second_router: OTBRConfigEntry,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """What an unanswered write sent is what the target is known as.

    The write may have landed, so until the router it was handed to settles
    it, other settings under that name are refused, past the delay and across
    a restart alike; the same settings are not.
    """
    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.GATEWAY_TIMEOUT)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    with pytest.raises(HomeAssistantError):
        await call_migrate(
            hass, dataset=TARGET, delay=600, config_entry=otbr_config_entry_multipan
        )
    rekeyed = dict(tlv_parser.parse_tlv(TARGET))
    rekeyed[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, bytes.fromhex("99999999888888887777777766666666")
    )

    with patch.object(
        second_router.runtime_data,
        "get_active_dataset_tlvs",
        return_value=bytes.fromhex(THIRD_TARGET),
    ):
        for _ in range(2):
            with pytest.raises(HomeAssistantError) as exc_info:
                await call_migrate(
                    hass,
                    dataset=tlv_parser.encode_tlv(rekeyed),
                    config_entry=second_router.entry_id,
                )
            assert exc_info.value.translation_key == "target_settings_differ"
            freezer.tick(601)
            del hass.data[ISSUED_TIMESTAMPS_KEY]
        # Only the unanswered write went out.
        assert len(pending_calls(aioclient_mock)) == 1

        response = await call_migrate(
            hass, dataset=TARGET, config_entry=second_router.entry_id
        )

    assert response["status"] == "migrating"
    assert len(pending_calls(aioclient_mock)) == 2


async def test_a_known_network_is_migrated_to_as_stored(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A network the store knows is not sent under its name with other settings.

    Nothing is arriving there; the pending dataset never reaches that
    network's own mesh, so the result would be two meshes of the same
    identity that cannot join each other, and the stored credentials
    replaced by the newer stamp. A rotation keeps its own name and may.
    """
    mock_pending_endpoint(aioclient_mock)
    await async_add_dataset(hass, "test", TARGET)
    rekeyed = dict(tlv_parser.parse_tlv(TARGET))
    rekeyed[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, bytes.fromhex("99999999888888887777777766666666")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(rekeyed))

    assert exc_info.value.translation_key == "target_settings_differ"
    assert not pending_calls(aioclient_mock)
    store = await async_get_store(hass)
    stored = next(
        entry
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )
    assert stored.tlv == TARGET

    assert (await call_migrate(hass, dataset=TARGET))["status"] == "migrating"


async def test_a_stored_network_with_an_extra_tlv_is_the_same_network(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Only the operational components tell two datasets apart.

    A stored dataset can carry a TLV the target was stripped of, steering
    data here; it is the same network regardless.
    """
    mock_pending_endpoint(aioclient_mock)
    await async_add_dataset(hass, "test", TARGET + "0801ff")

    assert (await call_migrate(hass, dataset=TARGET))["status"] == "migrating"


async def test_channel_change_waits_for_dataset_lock(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
) -> None:
    """A channel change cannot write while a migration holds the lock."""
    with (
        patch("python_otbr_api.OTBR.set_channel") as set_channel,
        patch("python_otbr_api.OTBR.get_active_dataset", return_value=None),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=DATASET_CH16,
        ),
    ):
        async with async_get_dataset_lock(hass):
            task = hass.async_create_task(
                otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=300)
            )
            for _ in range(5):
                await asyncio.sleep(0)
            # Blocked on the shared lock before touching the router.
            assert not task.done()
            set_channel.assert_not_awaited()

        await task
        set_channel.assert_awaited_once()


async def test_exhausted_seconds_are_refused(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A timestamp that cannot be stepped by a second is an error, not a wrap."""
    mock_pending_endpoint(aioclient_mock)
    maxed = dict(tlv_parser.parse_tlv(TARGET))
    maxed[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=2**48 - 1
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(maxed))
    assert exc_info.value.translation_key == "timestamp_exhausted"
    assert not pending_calls(aioclient_mock)


async def test_the_stored_dataset_raises_the_stamp(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A stored dataset newer than router and target is out-stamped too.

    The store keeps its entry unless the update is newer; stamped below it,
    the mesh would migrate while the store kept the old credentials.
    """
    mock_pending_endpoint(aioclient_mock)
    stored = dict(tlv_parser.parse_tlv(TARGET))
    stored[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1500
    )
    await async_add_dataset(hass, "test", tlv_parser.encode_tlv(stored))

    await call_migrate(hass, dataset=TARGET)

    stamp = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[0][2])[
        MeshcopTLVType.ACTIVETIMESTAMP
    ]
    assert (stamp.seconds, stamp.ticks) == (1501, 0)
    store = await async_get_store(hass)
    stored_entry = next(
        entry
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )
    assert _timestamp_parts_seconds(stored_entry.tlv) == 1501


async def test_the_stored_source_dataset_raises_the_stamp(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A stored copy of the network being left out-stamps a stale router.

    The store can know the network newer than the router the action was
    handed to. Stamped below that, the rest of the mesh discards the dataset
    when the delay expires, and this router moves alone.
    """
    mock_pending_endpoint(aioclient_mock)
    stored = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    stored[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1500
    )
    await async_add_dataset(hass, "test", tlv_parser.encode_tlv(stored))

    await call_migrate(hass, dataset=TARGET)

    stamp = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[0][2])[
        MeshcopTLVType.ACTIVETIMESTAMP
    ]
    assert (stamp.seconds, stamp.ticks) == (1501, 0)


async def test_migration_is_persisted_before_success_is_reported(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """The store is written before the action returns, not on the save delay.

    The mesh is migrating either way once the router accepted the write; a
    crash inside the store's save delay must not leave Home Assistant with
    the abandoned network as its preferred one.
    """
    mock_pending_endpoint(aioclient_mock)
    await async_add_dataset(hass, "test", DATASET_CH16.hex())
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id

    await call_migrate(hass, dataset=TARGET)

    saved = hass_storage[dataset_store.STORAGE_KEY]["data"]
    by_id = {entry["id"]: entry for entry in saved["datasets"]}
    preferred = by_id[saved["preferred_dataset"]]
    assert tlv_parser.parse_tlv(preferred["tlv"])[MeshcopTLVType.EXTPANID].data == (
        bytes.fromhex("1111111122222222")
    )


async def test_migration_refreshes_repair_issues(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Migrating onto insecure credentials raises the repair issue for them."""
    mock_pending_endpoint(aioclient_mock)
    insecure = dict(tlv_parser.parse_tlv(TARGET))
    insecure[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, INSECURE_NETWORK_KEYS[0]
    )

    assert not issue_registry.async_get_issue(
        domain="otbr", issue_id=f"insecure_thread_network_{otbr_config_entry_multipan}"
    )

    await call_migrate(hass, dataset=tlv_parser.encode_tlv(insecure))

    assert issue_registry.async_get_issue(
        domain="otbr", issue_id=f"insecure_thread_network_{otbr_config_entry_multipan}"
    )


async def test_migration_refreshes_repair_issues_on_the_whole_mesh(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Every router the migration reaches gets its repair issues refreshed.

    The pending dataset reaches the whole mesh, so credentials the migration
    adopts are as insecure on the other border routers as on the one the
    action was handed to.
    """
    mock_pending_endpoint(aioclient_mock)
    insecure = dict(tlv_parser.parse_tlv(TARGET))
    insecure[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, INSECURE_NETWORK_KEYS[0]
    )
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )

    await call_migrate(
        hass,
        dataset=tlv_parser.encode_tlv(insecure),
        config_entry=otbr_config_entry_multipan,
    )

    for entry_id in (otbr_config_entry_multipan, thread_entry.entry_id):
        assert issue_registry.async_get_issue(
            domain="otbr", issue_id=f"insecure_thread_network_{entry_id}"
        )


async def test_a_router_that_already_switched_gets_its_repair_issues_refreshed(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A router already on the migrated network is refreshed, not skipped.

    The delay can run out while the other routers are read one by one; such
    a router reports the target network, and its issues describe it from its
    own active dataset.
    """
    mock_pending_endpoint(aioclient_mock)
    insecure = dict(tlv_parser.parse_tlv(TARGET))
    insecure[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, INSECURE_NETWORK_KEYS[0]
    )
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )

    with patch.object(
        thread_entry.runtime_data,
        "get_active_dataset_tlvs",
        return_value=bytes.fromhex(tlv_parser.encode_tlv(insecure)),
    ):
        await call_migrate(
            hass,
            dataset=tlv_parser.encode_tlv(insecure),
            config_entry=otbr_config_entry_multipan,
        )

    assert issue_registry.async_get_issue(
        domain="otbr", issue_id=f"insecure_thread_network_{thread_entry.entry_id}"
    )


async def test_a_router_on_another_mesh_keeps_its_repair_issues(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A border router the pending dataset never reaches is left alone."""
    mock_pending_endpoint(aioclient_mock)
    insecure = dict(tlv_parser.parse_tlv(TARGET))
    insecure[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, INSECURE_NETWORK_KEYS[0]
    )
    elsewhere = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    elsewhere[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("5555666677778888")
    )
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )

    with patch.object(
        thread_entry.runtime_data,
        "get_active_dataset_tlvs",
        return_value=bytes.fromhex(tlv_parser.encode_tlv(elsewhere)),
    ):
        await call_migrate(
            hass,
            dataset=tlv_parser.encode_tlv(insecure),
            config_entry=otbr_config_entry_multipan,
        )

    assert issue_registry.async_get_issue(
        domain="otbr", issue_id=f"insecure_thread_network_{otbr_config_entry_multipan}"
    )
    assert not issue_registry.async_get_issue(
        domain="otbr", issue_id=f"insecure_thread_network_{thread_entry.entry_id}"
    )


async def test_a_short_delay_is_raised_to_what_the_leader_accepts(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """A network change cannot propagate faster than the leader allows.

    The leader raises a delay below 300 seconds when the dataset replaces
    the network key, but only on the copy it hands back to the mesh: this
    router keeps counting down from what was written to it. Sending the
    short delay would move it ahead of every other device.
    """
    mock_pending_endpoint(aioclient_mock)

    response = await call_migrate(hass, dataset=TARGET, delay=60)

    written = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[0][2])
    assert written[MeshcopTLVType.DELAYTIMER].delay == 300 * 1000
    # What is reported and what is recorded describe the same migration.
    assert response["delay"] == 300
    (record,) = hass_storage[ISSUED_TIMESTAMPS_STORAGE_KEY]["data"].values()
    assert record["until"] - dt_util.utcnow().timestamp() >= 299


async def test_a_short_delay_survives_a_change_that_keeps_the_key(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Only a network key change is held to the longer delay."""
    mock_pending_endpoint(aioclient_mock)
    active = tlv_parser.parse_tlv(DATASET_CH16.hex())
    renamed = dict(active)
    renamed[MeshcopTLVType.NETWORKNAME] = tlv_parser.NetworkName(
        MeshcopTLVType.NETWORKNAME, b"renamed"
    )

    response = await call_migrate(
        hass, dataset=tlv_parser.encode_tlv(renamed), delay=60
    )

    written = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[0][2])
    assert written[MeshcopTLVType.DELAYTIMER].delay == 60 * 1000
    assert response["delay"] == 60


async def test_a_migrating_mesh_is_not_reported_as_already_on_network(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Targeting the network a migrating mesh is leaving is not a no-op.

    A second border router on the mesh has not learned the pending dataset
    yet, so it still reports the network being left as its active one.
    Calling that "already on network" would be wrong within the delay.
    """
    mock_pending_endpoint(aioclient_mock)
    issued = await async_get_issued_timestamps(hass)
    active = tlv_parser.parse_tlv(DATASET_CH16.hex())
    source_xpan = str(active[MeshcopTLVType.EXTPANID]).lower()
    await issued.async_set(
        source_xpan, (1, 0), until=dt_util.utcnow().timestamp() + 300
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=DATASET_CH16.hex())

    assert exc_info.value.translation_key == "migration_in_flight"
    assert not pending_calls(aioclient_mock)


async def test_the_store_is_flushed_before_the_other_routers_are_asked(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """Reaching the other routers cannot delay the migration reaching disk.

    Refreshing their repair issues reads each of them over the network,
    which can block or never answer. The mesh is already migrating by then,
    so what the store holds must not wait on it.
    """
    mock_pending_endpoint(aioclient_mock)
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    saved_when_asked: list[bool] = []

    async def record_and_answer() -> bytes:
        saved_when_asked.append(dataset_store.STORAGE_KEY in hass_storage)
        return DATASET_CH16

    with patch.object(
        thread_entry.runtime_data,
        "get_active_dataset_tlvs",
        side_effect=record_and_answer,
    ):
        await call_migrate(
            hass, dataset=TARGET, config_entry=otbr_config_entry_multipan
        )

    assert saved_when_asked == [True]


async def test_the_other_routers_are_read_with_the_lock_released(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Refreshing the other routers' repair issues holds up nobody.

    Each read can wait for a network timeout, and by then everything the
    dataset lock protects has been written; other dataset writers and the
    config flow must not queue behind those reads.
    """
    mock_pending_endpoint(aioclient_mock)
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    locked_when_asked: list[bool] = []

    async def record_and_answer() -> bytes:
        locked_when_asked.append(async_get_dataset_lock(hass).locked())
        return DATASET_CH16

    with patch.object(
        thread_entry.runtime_data,
        "get_active_dataset_tlvs",
        side_effect=record_and_answer,
    ):
        await call_migrate(
            hass, dataset=TARGET, config_entry=otbr_config_entry_multipan
        )

    assert locked_when_asked == [False]


@pytest.mark.usefixtures("otbr_config_entry_thread")
async def test_the_other_routers_are_read_at_once(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """One slow router does not hold up the refresh of the others.

    Each read may wait out a timeout; read one after another, a dead router
    would add its timeout to every migration. Each read here waits for the
    other to have started, which only reads made at once can satisfy.
    """
    mock_pending_endpoint(aioclient_mock)
    third = MockConfigEntry(
        data={"url": "/dev/ttyAMA2"}, domain="otbr", title="Third", unique_id="third"
    )
    third.add_to_hass(hass)
    assert await hass.config_entries.async_setup(third.entry_id)
    others = [
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    ]
    assert len(others) == 2
    started = [asyncio.Event(), asyncio.Event()]

    def read_after_the_other_started(me: int):
        async def read() -> bytes:
            started[me].set()
            await asyncio.wait_for(started[1 - me].wait(), 1)
            return DATASET_CH16

        return read

    with (
        patch.object(
            others[0].runtime_data,
            "get_active_dataset_tlvs",
            side_effect=read_after_the_other_started(0),
        ),
        patch.object(
            others[1].runtime_data,
            "get_active_dataset_tlvs",
            side_effect=read_after_the_other_started(1),
        ),
    ):
        await call_migrate(
            hass, dataset=TARGET, config_entry=otbr_config_entry_multipan
        )


async def test_migration_reports_a_discarded_store_write(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a store write lost to a concurrent writer is reported.

    The router has already been told to migrate and cannot be called back, so
    the repair issues and the preferred dataset must still be brought up to
    date before the failure is raised.
    """
    mock_pending_endpoint(aioclient_mock)
    await async_add_dataset(hass, "test", DATASET_CH16.hex())
    store = await async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets.values())).id

    # Migrate onto insecure credentials, so the repair issue below can only
    # exist if update_issues ran before the failure was raised.
    insecure = dict(tlv_parser.parse_tlv(TARGET))
    insecure[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, INSECURE_NETWORK_KEYS[0]
    )

    async def store_newer_dataset(
        dataset: bytes, *, allow_replace: bool = False
    ) -> None:
        """Store newer credentials for the target network mid-migration."""
        interloper = dict(tlv_parser.parse_tlv(TARGET))
        interloper[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
            MeshcopTLVType.ACTIVETIMESTAMP, seconds=2000
        )
        await async_add_dataset(hass, "other", tlv_parser.encode_tlv(interloper))

    with (
        patch(
            "python_otbr_api.OTBR.set_pending_dataset_tlvs",
            side_effect=store_newer_dataset,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(insecure))

    assert exc_info.value.translation_key == "dataset_discarded"

    # The store kept the newer credentials ...
    stored = next(
        entry
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )
    assert _timestamp_parts_seconds(stored.tlv) == 2000
    # ... and the preferred pointer and repair issues still followed the
    # network the mesh is switching to.
    assert store.datasets[store.preferred_dataset].extended_pan_id.lower() == (
        "1111111122222222"
    )
    assert issue_registry.async_get_issue(
        domain="otbr", issue_id=f"insecure_thread_network_{otbr_config_entry_multipan}"
    )


def _timestamp_parts_seconds(tlv: str) -> int:
    """Return the active timestamp seconds of a dataset."""
    stamp = tlv_parser.parse_tlv(tlv)[MeshcopTLVType.ACTIVETIMESTAMP]
    assert isinstance(stamp, Timestamp)
    return stamp.seconds


async def test_migrations_of_one_mesh_do_not_share_a_timestamp(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test two migrations of the same mesh get distinct timestamps.

    A second border router on the same mesh may still report the old active
    dataset and no pending one, even once the first migration's delay has
    expired. Targeting a different network, nothing in the router's or the
    store's state would separate the two stamps.
    """
    mock_pending_endpoint(aioclient_mock)
    other_target = dict(tlv_parser.parse_tlv(TARGET))
    other_target[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("3333333344444444")
    )
    other_target[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1003
    )

    await call_migrate(hass, dataset=TARGET)
    freezer.tick(301)
    await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))

    stamps = [
        tlv_parser.parse_tlv(put[2])[MeshcopTLVType.ACTIVETIMESTAMP].seconds
        for put in pending_calls(aioclient_mock)
    ]
    assert len(stamps) == 2
    assert stamps[0] != stamps[1]
    assert stamps == sorted(stamps)


async def test_issued_timestamps_survive_a_restart(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the per-mesh timestamp floor is not lost with a restart.

    The pending dataset takes its delay to reach the other routers, and a
    restart in that window leaves them still reporting the old active dataset.
    Only what was written to disk separates the next migration's stamp from
    the one already in flight.
    """
    mock_pending_endpoint(aioclient_mock)
    other_target = dict(tlv_parser.parse_tlv(TARGET))
    other_target[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("3333333344444444")
    )
    other_target[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1003
    )

    await call_migrate(hass, dataset=TARGET)
    # Written through before the router was, not on the lazy save timer.
    (source_xpan,) = hass_storage[ISSUED_TIMESTAMPS_STORAGE_KEY]["data"]

    # A restart drops everything held in memory; the file stays, and so does
    # the propagation window it records.
    del hass.data[ISSUED_TIMESTAMPS_KEY]
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))
    assert exc_info.value.translation_key == "migration_in_flight"

    freezer.tick(301)
    await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))

    stamps = [
        tlv_parser.parse_tlv(put[2])[MeshcopTLVType.ACTIVETIMESTAMP].seconds
        for put in pending_calls(aioclient_mock)
    ]
    assert len(stamps) == 2
    assert stamps[0] < stamps[1]
    record = hass_storage[ISSUED_TIMESTAMPS_STORAGE_KEY]["data"][source_xpan]
    assert record["timestamp"] == [stamps[1], 0]


async def test_preferred_dataset_replaced_while_reading_the_router(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_border_agent_id: AsyncMock,
) -> None:
    """Test a superseded preferred dataset is refused before anything is sent.

    The default target is a snapshot of the preferred dataset. Sending it
    after another writer replaced it would put credentials on the mesh that
    Home Assistant has already superseded -- stamped newer, so the newer ones
    would be lost.
    """
    mock_pending_endpoint(aioclient_mock)
    await async_add_dataset(hass, "test", TARGET)
    store = await async_get_store(hass)
    # Setup already imported the router's own network, so pick the target.
    store.preferred_dataset = next(
        entry.id
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )

    border_agent_id = get_border_agent_id.return_value

    async def replace_preferred_dataset() -> bytes:
        """Rotate the preferred network's key while the router is read."""
        rotated = dict(tlv_parser.parse_tlv(TARGET))
        rotated[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
            MeshcopTLVType.NETWORKKEY, bytes.fromhex("99999999888888887777777766666666")
        )
        rotated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
            MeshcopTLVType.ACTIVETIMESTAMP, seconds=1010
        )
        await async_add_dataset(hass, "panel", tlv_parser.encode_tlv(rotated))
        return border_agent_id

    get_border_agent_id.side_effect = replace_preferred_dataset

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass)

    assert exc_info.value.translation_key == "preferred_dataset_changed"
    # Nothing reached the router, so the rotated credentials still stand.
    assert not pending_calls(aioclient_mock)
    stored = next(
        entry
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )
    assert tlv_parser.parse_tlv(stored.tlv)[MeshcopTLVType.NETWORKKEY].data.hex() == (
        "99999999888888887777777766666666"
    )


async def test_preferred_dataset_replaced_while_writing_the_router_is_reported(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A replacement landing between the check and the write is reported.

    The dataset store takes no lock, so no check on this side can be the last
    thing before the write; the snapshot is compared again once the write is
    done. The mesh is migrating to the snapshot and cannot be called back,
    so the bookkeeping runs and the failure is raised after it.
    """
    mock_pending_endpoint(aioclient_mock)
    await async_add_dataset(hass, "test", TARGET)
    store = await async_get_store(hass)
    store.preferred_dataset = next(
        entry.id
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )
    rotated = dict(tlv_parser.parse_tlv(TARGET))
    rotated[MeshcopTLVType.NETWORKKEY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.NETWORKKEY, bytes.fromhex("99999999888888887777777766666666")
    )
    rotated[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1010
    )

    issued = await async_get_issued_timestamps(hass)
    record_and_save = issued.async_set

    async def rotate_while_saving(*args: Any, **kwargs: Any) -> None:
        await record_and_save(*args, **kwargs)
        await async_add_dataset(hass, "panel", tlv_parser.encode_tlv(rotated))

    with (
        patch.object(issued, "async_set", rotate_while_saving),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await call_migrate(hass)

    assert exc_info.value.translation_key == "preferred_dataset_superseded"
    # The snapshot went out; the store keeps the newer rotation.
    assert len(pending_calls(aioclient_mock)) == 1
    stored = next(
        entry
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )
    assert tlv_parser.parse_tlv(stored.tlv)[MeshcopTLVType.NETWORKKEY].data.hex() == (
        "99999999888888887777777766666666"
    )


async def test_timestamp_watermark_is_per_mesh(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
) -> None:
    """Test one mesh's timestamps do not raise the floor for another.

    A shared watermark would let a network with a high timestamp push every
    other network's stamps up, and eventually exhaust them.
    """
    mock_pending_endpoint(aioclient_mock)
    high = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    high[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=900_000
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(tlv_parser.encode_tlv(high))

    # A migration of the high-timestamp mesh ...
    await call_migrate(hass, dataset=TARGET)

    # ... must not push a migration of an unrelated mesh up with it. Both the
    # source and the target differ, so nothing but a shared watermark could.
    other_source = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    other_source[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("5555555566666666")
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(
        tlv_parser.encode_tlv(other_source)
    )
    other_target = dict(tlv_parser.parse_tlv(TARGET))
    other_target[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("7777777788888888")
    )

    await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))

    stamps = [
        tlv_parser.parse_tlv(put[2])[MeshcopTLVType.ACTIVETIMESTAMP].seconds
        for put in pending_calls(aioclient_mock)
    ]
    assert stamps[0] == 900_001
    # The second mesh's own timestamps are small; it keeps its own floor.
    assert stamps[1] == 1004


async def test_channel_pinned_by_another_router_on_the_mesh(
    hass: HomeAssistant,
    multiprotocol_addon_manager_mock: Mock,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a pinned router on the mesh is respected through another router.

    The pending dataset reaches every router on the network, so migrating
    through a router that shares no radio would still move one that does.
    """
    mock_pending_endpoint(aioclient_mock)
    # The router the migration is handed to speaks over its serial path.
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 25

    # Target the router that is not sharing its radio; the multiprotocol one
    # is on the same network and pinned to another channel.
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await call_migrate(hass, dataset=TARGET, config_entry=thread_entry.entry_id)

    assert exc_info.value.translation_key == "channel_conflict"
    assert not pending_calls(aioclient_mock)


async def test_every_pinned_router_on_the_mesh_has_a_say(
    hass: HomeAssistant,
    second_router: OTBRConfigEntry,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Two routers pinned to different channels are both held to the target.

    Through the pinned router itself, the other pinned one on the mesh used
    to go unasked; each pin the target misses is named.
    """
    on_25 = dict(tlv_parser.parse_tlv(TARGET))
    on_25[MeshcopTLVType.CHANNEL] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.CHANNEL, bytes.fromhex("000019")
    )

    async def pin(hass: HomeAssistant, url: str) -> int:
        return 15 if url == second_router.data["url"] else 25

    with patch(
        "homeassistant.components.otbr.services.get_allowed_channel", side_effect=pin
    ):
        with pytest.raises(ServiceValidationError) as exc_info:
            await call_migrate(
                hass,
                dataset=tlv_parser.encode_tlv(on_25),
                config_entry=otbr_config_entry_multipan,
            )
        assert exc_info.value.translation_key == "channel_conflict"
        assert exc_info.value.translation_placeholders == {
            "target_channel": "25",
            "allowed_channel": "15",
        }

        with pytest.raises(ServiceValidationError) as exc_info:
            await call_migrate(
                hass, dataset=TARGET, config_entry=otbr_config_entry_multipan
            )
        assert exc_info.value.translation_placeholders == {
            "target_channel": "15",
            "allowed_channel": "25",
        }

    assert not pending_calls(aioclient_mock)


async def test_unreadable_pinned_router_refuses_the_migration(
    hass: HomeAssistant,
    multiprotocol_addon_manager_mock: Mock,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a pinned router that cannot be read is a failure, not skipped.

    Its REST API being down says nothing about its radio, which may still be
    on this mesh and would follow the pending dataset off the shared channel.
    A failure, not a validation error: nothing about the call was wrong.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 25

    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    pinned_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert pinned_entry is not None

    with (
        patch.object(
            pinned_entry.runtime_data,
            "get_active_dataset_tlvs",
            side_effect=HomeAssistantError("unreachable"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await call_migrate(hass, dataset=TARGET, config_entry=thread_entry.entry_id)

    assert not isinstance(exc_info.value, ServiceValidationError)
    assert exc_info.value.translation_key == "pinned_router_unreachable"
    assert exc_info.value.translation_placeholders == {"router": pinned_entry.title}
    assert not pending_calls(aioclient_mock)


async def test_a_pinned_router_without_a_network_name_refuses_the_migration(
    hass: HomeAssistant,
    multiprotocol_addon_manager_mock: Mock,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a pinned router whose dataset names no network is a failure.

    Without an extended PAN ID the dataset says nothing about which mesh the
    radio is on, so it cannot be waved through as another mesh.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 25
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    pinned_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert pinned_entry is not None
    nameless = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    del nameless[MeshcopTLVType.EXTPANID]

    with (
        patch.object(
            pinned_entry.runtime_data,
            "get_active_dataset_tlvs",
            return_value=bytes.fromhex(tlv_parser.encode_tlv(nameless)),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await call_migrate(hass, dataset=TARGET, config_entry=thread_entry.entry_id)

    assert exc_info.value.translation_key == "pinned_router_unreachable"
    assert not pending_calls(aioclient_mock)


async def test_unloaded_pinned_router_refuses_the_migration(
    hass: HomeAssistant,
    multiprotocol_addon_manager_mock: Mock,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a pinned router whose entry is not loaded is an error, not skipped.

    A failed setup or an unload does not stop the radio, which may still be
    on this mesh and would follow the pending dataset off the shared channel.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 25

    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    assert await hass.config_entries.async_unload(otbr_config_entry_multipan)
    pinned_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert pinned_entry is not None

    with pytest.raises(ServiceValidationError) as exc_info:
        await call_migrate(hass, dataset=TARGET, config_entry=thread_entry.entry_id)

    assert exc_info.value.translation_key == "pinned_router_not_loaded"
    assert exc_info.value.translation_placeholders == {"router": pinned_entry.title}
    assert not pending_calls(aioclient_mock)


async def test_an_unloaded_pinned_router_on_the_target_channel_is_no_obstacle(
    hass: HomeAssistant,
    multiprotocol_addon_manager_mock: Mock,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A pin the target meets needs no reading: it holds on any mesh."""
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15

    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    assert await hass.config_entries.async_unload(otbr_config_entry_multipan)

    response = await call_migrate(
        hass, dataset=TARGET, config_entry=thread_entry.entry_id
    )

    assert response["status"] == "migrating"
    assert len(pending_calls(aioclient_mock)) == 1


async def test_a_source_network_without_an_extended_pan_id_is_refused(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A router whose active dataset names no network is not migrated.

    Every guarantee of a migration is keyed by the extended PAN ID of the
    network being left; without one the action would have to go without
    them and still report success. OpenThread does not count such a router
    as commissioned, so the dataset is one the router should not have
    returned.
    """
    mock_pending_endpoint(aioclient_mock)
    nameless = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    del nameless[MeshcopTLVType.EXTPANID]

    with (
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs",
            return_value=bytes.fromhex(tlv_parser.encode_tlv(nameless)),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await call_migrate(hass, dataset=TARGET)

    assert exc_info.value.translation_key == "router_dataset_invalid"
    assert not pending_calls(aioclient_mock)


async def test_a_router_that_could_not_be_reached_hands_back_the_window(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A connection that never came up wrote nothing.

    Such a router cannot be asked what it holds either, and assuming it
    holds the dataset would refuse every retry for the delay while nothing
    propagates.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(
        f"{BASE_URL}/.well-known/thread/br-rest", status=HTTPStatus.NOT_FOUND
    )
    unreachable = aiohttp.ClientConnectorError(
        ConnectionKey("core-silabs-multiprotocol", 8081, False, True, None, None, None),
        OSError("connection refused"),
    )
    # This action's check and the library's find no pending dataset; the
    # router is gone by the write and stays gone.
    answers: list[None] = [None, None]

    async def pending_get(method, url, data):
        if answers:
            answers.pop()
            return AiohttpClientMockResponse(method, url, status=HTTPStatus.NO_CONTENT)
        return AiohttpClientMockResponse(method, url, exc=unreachable)

    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", side_effect=pending_get)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", exc=unreachable)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)

    mock_pending_endpoint(aioclient_mock)
    assert (await call_migrate(hass, dataset=TARGET))["status"] == "migrating"


async def test_a_router_that_cannot_be_asked_keeps_the_window(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A dropped connection over a router that cannot be asked keeps the window.

    The write may have landed, and an answer that would say otherwise is
    not to be had; refusing retries for the delay is the safe side.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(
        f"{BASE_URL}/.well-known/thread/br-rest", status=HTTPStatus.NOT_FOUND
    )
    answers: list[None] = [None, None]

    async def pending_get(method, url, data):
        if answers:
            answers.pop()
            return AiohttpClientMockResponse(method, url, status=HTTPStatus.NO_CONTENT)
        return AiohttpClientMockResponse(method, url, exc=aiohttp.ClientError)

    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", side_effect=pending_get)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", exc=aiohttp.ClientError)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET, delay=600)

    mock_pending_endpoint(aioclient_mock)
    freezer.tick(595)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "5"}


async def test_a_channel_change_marks_the_mesh_as_migrating(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A channel change through one router is a migration in flight for the mesh.

    A migration through another router on the mesh, which has not learned
    the change yet, is refused for the delay and stamped above the change
    once it is over.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    with (
        patch("python_otbr_api.OTBR.set_channel"),
        patch(
            "python_otbr_api.OTBR.get_active_dataset",
            return_value=python_otbr_api.ActiveDataSet(
                channel=16,
                extended_pan_id="F642646DA209B1C0",
                active_timestamp=python_otbr_api.Timestamp(seconds=1, ticks=0),
            ),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=300)
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET, config_entry=thread_entry.entry_id)
    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "300"}
    assert not pending_calls(aioclient_mock)

    # A target no newer than the network: only the record separates the stamps.
    same_age = dict(tlv_parser.parse_tlv(TARGET))
    same_age[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1
    )
    freezer.tick(300)
    await call_migrate(
        hass,
        dataset=tlv_parser.encode_tlv(same_age),
        config_entry=thread_entry.entry_id,
    )
    stamp = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[0][2])[
        MeshcopTLVType.ACTIVETIMESTAMP
    ]
    assert stamp.seconds == 3


async def test_the_issued_timestamps_are_loaded_once(hass: HomeAssistant) -> None:
    """Two first uses at once share one record.

    Loading yields to the event loop; a second instance built meanwhile
    would hold records the first never sees and erases with its next save.
    """

    async def yielding_load(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0)

    with patch(
        "homeassistant.components.otbr.util.Store.async_load",
        side_effect=yielding_load,
    ):
        first, second = await asyncio.gather(
            async_get_issued_timestamps(hass), async_get_issued_timestamps(hass)
        )

    assert first is second


async def test_tlvs_the_router_would_drop_are_not_stored(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A TLV outside the operational dataset is neither sent nor stored.

    The router keeps only the components; a stored copy carrying more would
    disagree with the router's at every setup and have it discarded.
    """
    mock_pending_endpoint(aioclient_mock)
    extended = dict(tlv_parser.parse_tlv(TARGET))
    extended[MeshcopTLVType.THREAD_DOMAIN_NAME] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.THREAD_DOMAIN_NAME, b"DefaultDomain"
    )

    await call_migrate(hass, dataset=tlv_parser.encode_tlv(extended))

    puts = pending_calls(aioclient_mock)
    assert tlv_parser.parse_tlv(puts[0][2]) == expected_pending(TARGET, 1004, 300000)
    store = await async_get_store(hass)
    stored = next(
        entry
        for entry in store.datasets.values()
        if entry.extended_pan_id.lower() == "1111111122222222"
    )
    assert MeshcopTLVType.THREAD_DOMAIN_NAME not in stored.dataset


async def test_a_wake_up_channel_the_router_added_is_not_a_change(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
) -> None:
    """The router adds a wake-up channel to a dataset without one.

    Re-sending that dataset would push a five minute pending dataset with
    nothing new in it, and block every other write for the delay.
    """
    mock_pending_endpoint(aioclient_mock)
    reported = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    reported[MeshcopTLVType.WAKEUP_CHANNEL] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.WAKEUP_CHANNEL, bytes.fromhex("000010")
    )
    get_active_dataset_tlvs.return_value = bytes.fromhex(
        tlv_parser.encode_tlv(reported)
    )

    response = await call_migrate(hass, dataset=DATASET_CH16.hex())

    assert response == {"status": "already_on_network"}
    assert not pending_calls(aioclient_mock)


async def test_the_legacy_beacons_flag_is_not_a_change(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """OpenThread cannot keep the Beacons flag; a target carrying it is a no-op."""
    mock_pending_endpoint(aioclient_mock)
    flagged = dict(tlv_parser.parse_tlv(DATASET_CH16.hex()))
    policy = bytearray(flagged[MeshcopTLVType.SECURITYPOLICY].data)
    policy[2] |= dataset_store.SECURITY_POLICY_BEACONS_FLAG
    flagged[MeshcopTLVType.SECURITYPOLICY] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.SECURITYPOLICY, bytes(policy)
    )

    response = await call_migrate(hass, dataset=tlv_parser.encode_tlv(flagged))

    assert response == {"status": "already_on_network"}
    assert not pending_calls(aioclient_mock)


async def test_an_unparseable_router_dataset_is_refused(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    get_active_dataset_tlvs: AsyncMock,
) -> None:
    """A router returning a dataset that does not parse is not migrated."""
    mock_pending_endpoint(aioclient_mock)
    # A timestamp TLV announcing eight bytes and carrying none.
    get_active_dataset_tlvs.return_value = bytes.fromhex("0e08")

    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)

    assert exc_info.value.translation_key == "router_dataset_invalid"
    assert not pending_calls(aioclient_mock)


async def test_a_target_without_a_timestamp_is_stamped_above_the_network(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A target carrying no timestamp is stamped from the network being left."""
    mock_pending_endpoint(aioclient_mock)
    unstamped = dict(tlv_parser.parse_tlv(TARGET))
    del unstamped[MeshcopTLVType.ACTIVETIMESTAMP]

    await call_migrate(hass, dataset=tlv_parser.encode_tlv(unstamped))

    stamp = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[0][2])[
        MeshcopTLVType.ACTIVETIMESTAMP
    ]
    assert (stamp.seconds, stamp.ticks) == (2, 0)


async def test_a_refused_write_hands_back_the_previous_window(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A refusal puts back what the last migration of the mesh recorded.

    Its stamp is still the floor for the next one; dropped instead, the
    next migration would reissue a stamp the mesh has already seen.
    """
    mock_pending_endpoint(aioclient_mock)
    other_target = dict(tlv_parser.parse_tlv(TARGET))
    other_target[MeshcopTLVType.EXTPANID] = tlv_parser.MeshcopTLVItem(
        MeshcopTLVType.EXTPANID, bytes.fromhex("3333333344444444")
    )
    await call_migrate(hass, dataset=TARGET)
    (source_xpan,) = hass_storage[ISSUED_TIMESTAMPS_STORAGE_KEY]["data"]
    freezer.tick(301)

    mock_pending_endpoint(aioclient_mock, put_status=HTTPStatus.PRECONDITION_FAILED)
    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))

    record = hass_storage[ISSUED_TIMESTAMPS_STORAGE_KEY]["data"][source_xpan]
    assert record["timestamp"] == [1004, 0]
    mock_pending_endpoint(aioclient_mock)
    await call_migrate(hass, dataset=tlv_parser.encode_tlv(other_target))
    stamp = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[0][2])[
        MeshcopTLVType.ACTIVETIMESTAMP
    ]
    assert stamp.seconds == 1005


@pytest.mark.parametrize(
    "pinned_active",
    [
        bytes.fromhex(
            tlv_parser.encode_tlv(
                {
                    **tlv_parser.parse_tlv(DATASET_CH16.hex()),
                    MeshcopTLVType.EXTPANID: tlv_parser.MeshcopTLVItem(
                        MeshcopTLVType.EXTPANID, bytes.fromhex("5555666677778888")
                    ),
                }
            )
        ),
        None,
    ],
    ids=["another_mesh", "no_mesh"],
)
async def test_a_pinned_router_off_this_mesh_does_not_pin_it(
    hass: HomeAssistant,
    multiprotocol_addon_manager_mock: Mock,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
    pinned_active: bytes | None,
) -> None:
    """A pinned router that is not on the mesh has no say over its channel."""
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 25
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    pinned_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert pinned_entry is not None

    with patch.object(
        pinned_entry.runtime_data, "get_active_dataset_tlvs", return_value=pinned_active
    ):
        response = await call_migrate(
            hass, dataset=TARGET, config_entry=thread_entry.entry_id
        )

    assert response["status"] == "migrating"
    assert len(pending_calls(aioclient_mock)) == 1


async def test_an_unpinned_router_is_not_asked_before_the_write(
    hass: HomeAssistant,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Only a pinned router is asked which network it is on before the write."""
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.get(
        "/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.NO_CONTENT
    )
    aioclient_mock.put("/dev/ttyAMA1/node/dataset/pending", status=HTTPStatus.CREATED)
    thread_entry = next(
        entry
        for entry in hass.config_entries.async_loaded_entries("otbr")
        if entry.entry_id != otbr_config_entry_multipan
    )
    other_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert other_entry is not None
    puts_seen: list[int] = []

    async def record_and_answer() -> bytes:
        puts_seen.append(len(pending_calls(aioclient_mock)))
        return DATASET_CH16

    with patch.object(
        other_entry.runtime_data,
        "get_active_dataset_tlvs",
        side_effect=record_and_answer,
    ):
        response = await call_migrate(
            hass, dataset=TARGET, config_entry=thread_entry.entry_id
        )

    assert response["status"] == "migrating"
    # Read once, by the repair-issue refresh after the write.
    assert puts_seen == [1]


async def test_an_ignored_router_is_skipped(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An ignored discovery has no URL to judge a channel pin by."""
    mock_pending_endpoint(aioclient_mock)
    MockConfigEntry(domain="otbr", data={}, source=SOURCE_IGNORE).add_to_hass(hass)

    response = await call_migrate(hass, dataset=TARGET)

    assert response["status"] == "migrating"
