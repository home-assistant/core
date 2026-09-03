"""Test the Open Thread Border Router actions."""

import asyncio
from http import HTTPStatus
import re
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from python_otbr_api import tlv_parser
from python_otbr_api.tlv_parser import DelayTimer, MeshcopTLVType, Timestamp

from homeassistant.components.otbr import (
    silabs_multiprotocol as otbr_silabs_multiprotocol,
)
from homeassistant.components.otbr.util import (
    INSECURE_NETWORK_KEYS,
    ISSUED_TIMESTAMPS_KEY,
    ISSUED_TIMESTAMPS_STORAGE_KEY,
    async_get_dataset_lock,
)
from homeassistant.components.thread import (
    async_add_dataset,
    async_get_store,
    dataset_store,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from . import BASE_URL, DATASET_CH16

from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

# A different network from the one under test: ts 1003, channel 15. Carries
# every network-defining TLV plus a wakeup-channel TLV (0x4a) to prove
# unrelated fields survive the migration untouched.
TARGET = (
    "0e080000000003eb0000000300000f4a0300001035060004001fffe002081111111122222222"
    "0708fd111111222222220510aaaaaaaaaaaaaaaabbbbbbbbbbbbbbbb030f4f70656e546872"
    "6561642048412032010212340410ccccccccccccccccdddddddddddddddd0c0402a0f7f8"
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
) -> None:
    """Mock the router's pending-dataset endpoint."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    if in_flight is None:
        aioclient_mock.get(
            f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT
        )
    else:
        aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", text=in_flight)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", status=put_status)


def pending_calls(aioclient_mock: AiohttpClientMocker) -> list:
    """Return the PUT calls the router received."""
    return [call for call in aioclient_mock.mock_calls if call[0] == "PUT"]


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
    the request, a 60s delay behind an 8s request would have ended while the
    mesh was still counting down.
    """
    mock_pending_endpoint(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r".*/api/actions$"), status=HTTPStatus.OK)
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)

    async def slow_put(method, url, data):
        freezer.tick(8)
        return AiohttpClientMockResponse(method, url, status=HTTPStatus.CREATED)

    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", side_effect=slow_put)
    await call_migrate(hass, dataset=TARGET, delay=60)

    mock_pending_endpoint(aioclient_mock)
    freezer.tick(55)
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
    aioclient_mock.get(f"{BASE_URL}/node/dataset/pending", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{BASE_URL}/node/dataset/pending", exc=aiohttp.ClientError)

    with pytest.raises(HomeAssistantError):
        await call_migrate(hass, dataset=TARGET)

    # The retry is a normal migration, not a refusal.
    mock_pending_endpoint(aioclient_mock)
    response = await call_migrate(hass, dataset=TARGET)

    assert response["status"] == "migrating"


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
        await call_migrate(hass, dataset=TARGET, delay=60)

    # The write may have landed as late as the moment the connection died,
    # so the window is measured from there, not from before the request.
    mock_pending_endpoint(aioclient_mock)
    freezer.tick(55)
    with pytest.raises(HomeAssistantError) as exc_info:
        await call_migrate(hass, dataset=TARGET)
    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "5"}


async def test_delay_is_applied(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A non-default delay reaches the router and the response."""
    mock_pending_endpoint(aioclient_mock)

    response = await call_migrate(hass, dataset=TARGET, delay=60)

    assert response["delay"] == 60
    puts = pending_calls(aioclient_mock)
    assert tlv_parser.parse_tlv(puts[0][2]) == expected_pending(TARGET, 1004, 60000)


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
    aioclient_mock.clear_requests()
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
    aioclient_mock.clear_requests()

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

    await call_migrate(hass, dataset=TARGET, delay=60)
    freezer.tick(30)

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


async def test_channel_change_waits_for_dataset_lock(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
) -> None:
    """A channel change cannot write while a migration holds the lock."""
    with (
        patch("python_otbr_api.OTBR.set_channel") as set_channel,
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


async def test_ticks_count_in_the_comparison(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A dataset newer only by ticks is still out-stamped."""
    mock_pending_endpoint(aioclient_mock)
    stored = dict(tlv_parser.parse_tlv(TARGET))
    stored[MeshcopTLVType.ACTIVETIMESTAMP] = Timestamp.from_values(
        MeshcopTLVType.ACTIVETIMESTAMP, seconds=1003, ticks=42
    )
    await async_add_dataset(hass, "test", tlv_parser.encode_tlv(stored))

    await call_migrate(hass, dataset=TARGET)

    stamp = tlv_parser.parse_tlv(pending_calls(aioclient_mock)[0][2])[
        MeshcopTLVType.ACTIVETIMESTAMP
    ]
    assert (stamp.seconds, stamp.ticks) == (1004, 0)


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
    get_active_dataset_tlvs: AsyncMock,
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
        return DATASET_CH16

    get_active_dataset_tlvs.side_effect = replace_preferred_dataset

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


async def test_unreadable_pinned_router_refuses_the_migration(
    hass: HomeAssistant,
    multiprotocol_addon_manager_mock: Mock,
    otbr_config_entry_thread: None,
    otbr_config_entry_multipan: str,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a pinned router that cannot be read is an error, not skipped.

    Its REST API being down says nothing about its radio, which may still be
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
    pinned_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert pinned_entry is not None

    with (
        patch.object(
            pinned_entry.runtime_data,
            "get_active_dataset_tlvs",
            side_effect=HomeAssistantError("unreachable"),
        ),
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await call_migrate(hass, dataset=TARGET, config_entry=thread_entry.entry_id)

    assert exc_info.value.translation_key == "pinned_router_unreachable"
    assert exc_info.value.translation_placeholders == {"router": pinned_entry.title}
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

    assert exc_info.value.translation_key == "pinned_router_unreachable"
    assert exc_info.value.translation_placeholders == {"router": pinned_entry.title}
    assert not pending_calls(aioclient_mock)
