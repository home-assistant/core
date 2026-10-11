"""Test OTBR Silicon Labs Multiprotocol support."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_otbr_api import (
    ActiveDataSet,
    PendingDatasetOutcomeUnknownError,
    Timestamp,
    tlv_parser,
)

from homeassistant.components.otbr import (
    silabs_multiprotocol as otbr_silabs_multiprotocol,
)
from homeassistant.components.otbr.util import (
    _Migration,
    _Record,
    async_get_issued_timestamps,
)
from homeassistant.components.thread import dataset_store
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from . import DATASET_CH16

OTBR_MULTIPAN_URL = "http://core-silabs-multiprotocol:8081"
OTBR_NON_MULTIPAN_URL = "/dev/ttyAMA1"
DATASET_CH16_PENDING = (
    "0E080000000000020000"  # ACTIVETIMESTAMP
    "340400006699"  # DELAYTIMER
    "000300000F"  # CHANNEL
    "35060004001FFFE0"  # CHANNELMASK
    "0208F642646DA209B1C0"  # EXTPANID
    "0708FDF57B5A0FE2AAF6"  # MESHLOCALPREFIX
    "0510DE98B5BA1A528FEE049D4B4B01835375"  # NETWORKKEY
    "030D4F70656E546872656164204841"  # NETWORKNAME
    "010225A4"  # PANID
    "0410F5DD18371BFD29E1A601EF6FFAD94C03"  # PSKC
    "0C0402A0F7F8"  # SECURITYPOLICY
)


@pytest.fixture(autouse=True)
def mock_supervisor_client(supervisor_client: AsyncMock) -> None:
    """Mock supervisor client."""


@pytest.fixture(autouse=True)
def router_on_its_network() -> Generator[None]:
    """Have the router report the network of DATASET_CH16 as its active one."""
    with patch(
        "python_otbr_api.OTBR.get_active_dataset",
        return_value=ActiveDataSet(
            channel=16,
            extended_pan_id="F642646DA209B1C0",
            active_timestamp=Timestamp(seconds=1, ticks=0),
        ),
    ):
        yield


async def test_async_change_channel(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test async_change_channel."""

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_CH16.hex()

    with (
        patch("python_otbr_api.OTBR.set_channel") as mock_set_channel,
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)
    mock_set_channel.assert_awaited_once_with(15, delay=5 * 300 * 1000)

    pending_dataset = tlv_parser.parse_tlv(DATASET_CH16_PENDING)
    pending_dataset.pop(tlv_parser.MeshcopTLVType.DELAYTIMER)

    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == tlv_parser.encode_tlv(
        pending_dataset
    )


async def test_async_change_channel_records_the_window(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """The change is recorded as propagating on the mesh for its delay."""
    with (
        patch("python_otbr_api.OTBR.set_channel"),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    issued = await async_get_issued_timestamps(hass)
    assert issued.get("f642646da209b1c0") == (2, 0)
    assert issued.seconds_in_flight("f642646da209b1c0") == 5 * 300


async def test_async_change_channel_keeps_the_floor_of_a_missed_migration(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """A change through a router that missed a migration lowers nothing.

    The router still reports the active dataset the mesh migrated away
    from, so the library stamps its change just above that. The record
    keeps the migration's stamp as the floor and only moves the window.
    """
    issued = await async_get_issued_timestamps(hass)
    await issued.async_set(
        "f642646da209b1c0", (1004, 0), until=dt_util.utcnow().timestamp() - 1
    )

    with (
        patch("python_otbr_api.OTBR.set_channel"),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert issued.get("f642646da209b1c0") == (1004, 0)
    assert issued.seconds_in_flight("f642646da209b1c0") == 5 * 300


async def test_async_change_channel_refuses_while_the_mesh_is_migrating(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """A migration in flight on the mesh refuses the channel change.

    This router has not learned the migration yet; its channel change would
    supersede it for the whole mesh.
    """
    issued = await async_get_issued_timestamps(hass)
    await issued.async_set(
        "f642646da209b1c0", (2, 0), until=dt_util.utcnow().timestamp() + 300
    )

    with (
        patch("python_otbr_api.OTBR.set_channel") as mock_set_channel,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "300"}
    mock_set_channel.assert_not_awaited()


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_async_change_channel_refuses_while_a_mesh_is_arriving(
    hass: HomeAssistant,
) -> None:
    """A channel change waits for a mesh migrating onto this network.

    That mesh was sent the network on its current channel. The migration's
    record keeps its target and its deadline, which is what says the network
    is still receiving.
    """
    issued = await async_get_issued_timestamps(hass)
    arrives = dt_util.utcnow().timestamp() + 300
    await issued.async_restore(
        "1111111122222222",
        _Record(
            (1004, 0),
            arrives,
            _Migration("f642646da209b1c0", None, arrives, DATASET_CH16.hex()),
        ),
    )

    with (
        patch("python_otbr_api.OTBR.set_channel") as mock_set_channel,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "migration_in_flight"
    assert exc_info.value.translation_placeholders == {"remaining": "300"}
    mock_set_channel.assert_not_awaited()


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_async_change_channel_frees_the_target_of_a_recorded_migration(
    hass: HomeAssistant,
) -> None:
    """A later channel change does not hold the network a migration moved to.

    Through a router that missed the migration, the change moves this
    network's window, not the migration's own deadline, which has passed:
    nothing is arriving at the target any more, and it would otherwise be
    refused writes for the whole delay.
    """
    issued = await async_get_issued_timestamps(hass)
    passed = dt_util.utcnow().timestamp() - 1
    await issued.async_restore(
        "f642646da209b1c0",
        _Record(
            (1004, 0),
            passed,
            _Migration("1111111122222222", None, passed, DATASET_CH16.hex()),
        ),
    )

    with (
        patch("python_otbr_api.OTBR.set_channel"),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert issued.seconds_in_flight("f642646da209b1c0") == 5 * 300
    assert issued.seconds_in_flight("1111111122222222") == 0


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_async_change_channel_keeps_a_migration_still_to_be_settled(
    hass: HomeAssistant,
) -> None:
    """A channel change leaves an unanswered migration's record in place.

    The router it was handed to may yet be found on the target, which is
    what settles it; a change through another router must not forget it,
    nor hold the target on the record's account.
    """
    issued = await async_get_issued_timestamps(hass)
    passed = dt_util.utcnow().timestamp() - 1
    await issued.async_restore(
        "f642646da209b1c0",
        _Record(
            (1004, 0),
            passed,
            _Migration("1111111122222222", "router", passed, DATASET_CH16.hex()),
        ),
    )

    with (
        patch("python_otbr_api.OTBR.set_channel"),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert issued.migration_source("1111111122222222", "router") == "f642646da209b1c0"
    assert issued.seconds_in_flight("1111111122222222") == 0


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_async_change_channel_stores_what_an_unanswered_write_left(
    hass: HomeAssistant,
) -> None:
    """A change whose outcome is unknown still stores what the router holds.

    The write may have landed; the pending dataset the router then holds is
    what the mesh moves to, and the store must not keep the old channel. The
    unknown outcome stays the error reported.
    """
    with (
        patch(
            "python_otbr_api.OTBR.set_channel",
            side_effect=PendingDatasetOutcomeUnknownError("no answer"),
        ),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "pending_dataset_unanswered"
    store = await dataset_store.async_get_store(hass)
    pending_dataset = tlv_parser.parse_tlv(DATASET_CH16_PENDING)
    pending_dataset.pop(tlv_parser.MeshcopTLVType.DELAYTIMER)
    assert [entry.tlv for entry in store.datasets.values()] == [
        tlv_parser.encode_tlv(pending_dataset)
    ]
    issued = await async_get_issued_timestamps(hass)
    assert issued.seconds_in_flight("f642646da209b1c0") == 5 * 300


async def test_an_unanswered_change_the_router_does_not_hold_yet_is_kept(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """A change the router neither answered nor holds yet is kept to be settled.

    A router that registers with the leader holds the dataset only once the
    leader hands it back, so nothing shows whether the write landed. The
    store keeps the old channel rather than one the mesh may never move to,
    and the dataset sent is kept on the network's record for this router,
    found running it, to settle -- as an unanswered migration is.
    """
    with (
        patch(
            "python_otbr_api.OTBR.set_channel",
            side_effect=PendingDatasetOutcomeUnknownError("no answer"),
        ),
        patch("python_otbr_api.OTBR.get_pending_dataset_tlvs", return_value=None),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "pending_dataset_unanswered"
    store = await dataset_store.async_get_store(hass)
    assert [entry.tlv for entry in store.datasets.values()] == [DATASET_CH16.hex()]
    issued = await async_get_issued_timestamps(hass)
    assert (
        issued.migration_source("f642646da209b1c0", otbr_config_entry_multipan)
        == "f642646da209b1c0"
    )
    assert (sent := issued.sent("f642646da209b1c0")) is not None
    moved = tlv_parser.parse_tlv(sent)
    assert moved[tlv_parser.MeshcopTLVType.CHANNEL].channel == 15
    assert moved[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP].seconds == 2
    assert issued.seconds_in_flight("f642646da209b1c0") == 5 * 300


async def test_an_answered_change_settles_one_the_router_never_answered(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """A change the router answers settles an earlier one it never answered.

    The new pending dataset is built from the router's active dataset, which
    shows whatever the earlier write did, and the store follows this write.
    """
    issued = await async_get_issued_timestamps(hass)
    passed = dt_util.utcnow().timestamp() - 1
    await issued.async_restore(
        "f642646da209b1c0",
        _Record(
            (2, 0),
            passed,
            _Migration(
                "f642646da209b1c0",
                otbr_config_entry_multipan,
                passed,
                DATASET_CH16_PENDING,
            ),
        ),
    )

    with (
        patch("python_otbr_api.OTBR.set_channel"),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert issued.sent("f642646da209b1c0") is None
    assert issued.seconds_in_flight("f642646da209b1c0") == 5 * 300


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_an_unanswered_change_leaves_an_unsettled_migration_in_place(
    hass: HomeAssistant,
) -> None:
    """The record of a migration still to be settled is not taken over.

    Its router may yet be found on the target; the change through this
    router, which missed that migration, cannot be kept as well.
    """
    issued = await async_get_issued_timestamps(hass)
    passed = dt_util.utcnow().timestamp() - 1
    await issued.async_restore(
        "f642646da209b1c0",
        _Record(
            (1004, 0),
            passed,
            _Migration("1111111122222222", "router", passed, DATASET_CH16.hex()),
        ),
    )

    with (
        patch(
            "python_otbr_api.OTBR.set_channel",
            side_effect=PendingDatasetOutcomeUnknownError("no answer"),
        ),
        patch("python_otbr_api.OTBR.get_pending_dataset_tlvs", return_value=None),
        pytest.raises(HomeAssistantError),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert issued.migration_source("1111111122222222", "router") == "f642646da209b1c0"
    assert issued.sent("f642646da209b1c0") == DATASET_CH16.hex()


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_change_the_store_will_not_record_is_reported(
    hass: HomeAssistant,
) -> None:
    """A dataset the store keeps a newer one over is reported, as a migration's is.

    The mesh moves to the channel regardless; a success would say the store
    follows it.
    """
    newer = tlv_parser.parse_tlv(DATASET_CH16.hex())
    newer[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP] = tlv_parser.Timestamp.from_values(
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP, seconds=10
    )
    await dataset_store.async_add_dataset(hass, "otbr", tlv_parser.encode_tlv(newer))

    with (
        patch("python_otbr_api.OTBR.set_channel") as mock_set_channel,
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    mock_set_channel.assert_awaited_once()
    assert exc_info.value.translation_key == "dataset_discarded"
    store = await dataset_store.async_get_store(hass)
    (stored,) = (tlv_parser.parse_tlv(entry.tlv) for entry in store.datasets.values())
    assert stored[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP].seconds == 10


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_an_answered_change_is_stored_as_sent_when_the_router_cannot_be_read(
    hass: HomeAssistant,
) -> None:
    """A read failing after the router answered does not fail the change.

    The dataset sent is what the mesh will run: it is stored, and the change
    is reported as the success it is.
    """
    with (
        patch("python_otbr_api.OTBR.set_channel"),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            side_effect=HomeAssistantError("down"),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    store = await dataset_store.async_get_store(hass)
    (stored,) = (tlv_parser.parse_tlv(entry.tlv) for entry in store.datasets.values())
    assert stored[tlv_parser.MeshcopTLVType.CHANNEL].channel == 15
    assert stored[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP].seconds == 2
    issued = await async_get_issued_timestamps(hass)
    assert issued.sent("f642646da209b1c0") is None


async def test_an_unanswered_change_is_kept_before_the_router_is_read(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """The dataset sent is on the record even when the router cannot be read.

    An unanswered write may have landed; a read failing on top of it must
    not lose what the router it was handed to can later be found running.
    """
    with (
        patch(
            "python_otbr_api.OTBR.set_channel",
            side_effect=PendingDatasetOutcomeUnknownError("no answer"),
        ),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            side_effect=HomeAssistantError("down"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "pending_dataset_unanswered"
    issued = await async_get_issued_timestamps(hass)
    assert (
        issued.migration_source("f642646da209b1c0", otbr_config_entry_multipan)
        == "f642646da209b1c0"
    )
    assert (sent := issued.sent("f642646da209b1c0")) is not None
    assert tlv_parser.parse_tlv(sent)[tlv_parser.MeshcopTLVType.CHANNEL].channel == 15


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_channel_outside_the_thread_band_is_refused(
    hass: HomeAssistant,
) -> None:
    """A channel outside 11 to 26 is refused before anything is read or built."""
    with (
        patch("python_otbr_api.OTBR.set_channel") as mock_set_channel,
        patch("python_otbr_api.OTBR.get_active_dataset_tlvs") as mock_get_active,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 27, delay=5 * 300)

    assert exc_info.value.translation_key == "invalid_channel"
    assert exc_info.value.translation_placeholders == {"channel": "27"}
    mock_set_channel.assert_not_awaited()
    mock_get_active.assert_not_awaited()


async def test_async_change_channel_no_pending(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test async_change_channel when the pending dataset already expired."""

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_CH16.hex()

    with (
        patch("python_otbr_api.OTBR.set_channel") as mock_set_channel,
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=None,
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)
    mock_set_channel.assert_awaited_once_with(15, delay=5 * 300 * 1000)

    pending_dataset = tlv_parser.parse_tlv(DATASET_CH16_PENDING)
    pending_dataset.pop(tlv_parser.MeshcopTLVType.DELAYTIMER)

    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == tlv_parser.encode_tlv(
        pending_dataset
    )


async def test_async_change_channel_stores_what_the_leader_was_given(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """A router that registers with the leader holds no pending copy yet.

    Its active dataset still has the old channel, so what the change wrote is
    stored: the active dataset on the new channel, stamped one above.
    """
    with (
        patch("python_otbr_api.OTBR.set_channel"),
        patch("python_otbr_api.OTBR.get_pending_dataset_tlvs", return_value=None),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    store = await dataset_store.async_get_store(hass)
    (stored,) = (tlv_parser.parse_tlv(entry.tlv) for entry in store.datasets.values())
    assert stored[tlv_parser.MeshcopTLVType.CHANNEL].channel == 15
    assert stored[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP].seconds == 2
    assert tlv_parser.MeshcopTLVType.DELAYTIMER not in stored


async def test_async_change_channel_no_update(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test async_change_channel when we didn't get a dataset from the OTBR."""

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_CH16.hex()

    with (
        patch("python_otbr_api.OTBR.set_channel") as mock_set_channel,
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs",
            return_value=None,
        ),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=None,
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)
    mock_set_channel.assert_awaited_once_with(15, delay=5 * 300 * 1000)

    assert list(store.datasets.values())[0].tlv == DATASET_CH16.hex()


async def test_async_change_channel_no_otbr(hass: HomeAssistant) -> None:
    """Test async_change_channel when otbr is not configured."""

    with patch("python_otbr_api.OTBR.set_channel") as mock_set_channel:
        await otbr_silabs_multiprotocol.async_change_channel(hass, 16, delay=0)
    mock_set_channel.assert_not_awaited()


async def test_async_change_channel_non_matching_url(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """Test async_change_channel when otbr is not configured."""
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    config_entry.runtime_data.url = OTBR_NON_MULTIPAN_URL
    with patch("python_otbr_api.OTBR.set_channel") as mock_set_channel:
        await otbr_silabs_multiprotocol.async_change_channel(hass, 16, delay=0)
    mock_set_channel.assert_not_awaited()


async def test_async_get_channel(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test test_async_get_channel."""

    with patch(
        "python_otbr_api.OTBR.get_active_dataset",
        return_value=ActiveDataSet(channel=11),
    ) as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) == 11
    mock_get_active_dataset.assert_awaited_once_with()


async def test_async_get_channel_no_dataset(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test test_async_get_channel."""

    with patch(
        "python_otbr_api.OTBR.get_active_dataset",
        return_value=None,
    ) as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) is None
    mock_get_active_dataset.assert_awaited_once_with()


async def test_async_get_channel_error(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test test_async_get_channel."""

    with patch(
        "python_otbr_api.OTBR.get_active_dataset",
        side_effect=HomeAssistantError,
    ) as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) is None
    mock_get_active_dataset.assert_awaited_once_with()


async def test_async_get_channel_no_otbr(hass: HomeAssistant) -> None:
    """Test test_async_get_channel when otbr is not configured."""

    with patch("python_otbr_api.OTBR.get_active_dataset") as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) is None
    mock_get_active_dataset.assert_not_awaited()


async def test_async_get_channel_non_matching_url(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """Test async_change_channel when otbr is not configured."""
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    config_entry.runtime_data.url = OTBR_NON_MULTIPAN_URL
    with patch("python_otbr_api.OTBR.get_active_dataset") as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) is None
    mock_get_active_dataset.assert_not_awaited()


@pytest.mark.parametrize(
    ("url", "expected"),
    [(OTBR_MULTIPAN_URL, True), (OTBR_NON_MULTIPAN_URL, False)],
)
async def test_async_using_multipan(
    hass: HomeAssistant, otbr_config_entry_multipan: str, url: str, expected: bool
) -> None:
    """Test async_change_channel when otbr is not configured."""
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    config_entry.runtime_data.url = url

    assert await otbr_silabs_multiprotocol.async_using_multipan(hass) is expected


async def test_async_using_multipan_no_otbr(hass: HomeAssistant) -> None:
    """Test async_change_channel when otbr is not configured."""

    assert await otbr_silabs_multiprotocol.async_using_multipan(hass) is False


async def test_async_using_multipan_non_matching_url(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """Test async_change_channel when otbr is not configured."""
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    config_entry.runtime_data.url = OTBR_NON_MULTIPAN_URL
    assert await otbr_silabs_multiprotocol.async_using_multipan(hass) is False
