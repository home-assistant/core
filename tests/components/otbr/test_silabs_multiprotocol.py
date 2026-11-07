"""Test OTBR Silicon Labs Multiprotocol support."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from python_otbr_api import (
    ActiveDataSet,
    OTBRError,
    PendingDatasetOutcomeUnknownError,
    PendingDatasetRejectedError,
    Timestamp,
    tlv_parser,
)

from homeassistant.components.otbr import (
    silabs_multiprotocol as otbr_silabs_multiprotocol,
)
from homeassistant.components.otbr.util import (
    PROPAGATION_WINDOWS_STORAGE_KEY,
    PROPAGATION_WINDOWS_STORAGE_VERSION,
    async_get_propagation_windows,
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


def _dataset_without(tag: tlv_parser.MeshcopTLVType) -> bytes:
    """Return DATASET_CH16 without one of its TLVs."""
    dataset = tlv_parser.parse_tlv(DATASET_CH16.hex())
    dataset.pop(tag)
    return bytes.fromhex(tlv_parser.encode_tlv(dataset))


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


def sent_pending(
    mock: AsyncMock,
) -> dict[tlv_parser.MeshcopTLVType | int, tlv_parser.MeshcopTLVItem]:
    """Return the pending dataset handed to the router."""
    mock.assert_awaited_once()
    return tlv_parser.parse_tlv(mock.await_args.args[0].hex())


async def test_async_change_channel(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test async_change_channel."""

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_CH16.hex()

    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending,
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)
    sent = sent_pending(mock_set_pending)
    assert sent[tlv_parser.MeshcopTLVType.CHANNEL].channel == 15
    assert sent[
        tlv_parser.MeshcopTLVType.DELAYTIMER
    ] == tlv_parser.DelayTimer.from_milliseconds(5 * 300 * 1000)

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
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs"),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    windows = await async_get_propagation_windows(hass)
    assert windows.seconds_left("f642646da209b1c0") == 5 * 300


async def test_async_change_channel_refuses_while_a_change_propagates(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    otbr_config_entry_multipan: str,
) -> None:
    """A change still propagating on the mesh refuses another."""
    hass_storage[PROPAGATION_WINDOWS_STORAGE_KEY] = {
        "version": PROPAGATION_WINDOWS_STORAGE_VERSION,
        "data": {"f642646da209b1c0": dt_util.utcnow().timestamp() + 300},
    }

    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "dataset_propagating"
    assert exc_info.value.translation_placeholders == {"remaining": "300"}
    mock_set_pending.assert_not_awaited()


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_async_change_channel_stores_what_an_unanswered_write_left(
    hass: HomeAssistant,
) -> None:
    """A change whose outcome is unknown still stores what the router holds."""
    with (
        patch(
            "python_otbr_api.OTBR.set_pending_dataset_tlvs",
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
    windows = await async_get_propagation_windows(hass)
    assert windows.seconds_left("f642646da209b1c0") == 5 * 300


async def test_an_unanswered_change_the_router_does_not_hold_yet_is_not_stored(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """A change the router neither answered nor holds yet is not stored."""
    with (
        patch(
            "python_otbr_api.OTBR.set_pending_dataset_tlvs",
            side_effect=PendingDatasetOutcomeUnknownError("no answer"),
        ),
        patch("python_otbr_api.OTBR.get_pending_dataset_tlvs", return_value=None),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "pending_dataset_unanswered"
    store = await dataset_store.async_get_store(hass)
    assert [entry.tlv for entry in store.datasets.values()] == [DATASET_CH16.hex()]
    windows = await async_get_propagation_windows(hass)
    assert windows.seconds_left("f642646da209b1c0") == 5 * 300


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_router_behind_the_store_is_refused(hass: HomeAssistant) -> None:
    """A router running an older dataset than the one stored is refused unsent."""
    newer = tlv_parser.parse_tlv(DATASET_CH16.hex())
    newer[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP] = tlv_parser.Timestamp.from_values(
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP, seconds=10
    )
    await dataset_store.async_add_dataset(hass, "otbr", tlv_parser.encode_tlv(newer))

    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "router_dataset_outdated"
    mock_set_pending.assert_not_awaited()
    windows = await async_get_propagation_windows(hass)
    assert windows.seconds_left("f642646da209b1c0") == 0


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_change_the_store_will_not_record_is_reported(
    hass: HomeAssistant,
) -> None:
    """A newer dataset stored during the write is reported."""
    newer = tlv_parser.parse_tlv(DATASET_CH16.hex())
    newer[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP] = tlv_parser.Timestamp.from_values(
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP, seconds=10
    )

    async def store_newer(_dataset: bytes) -> None:
        await dataset_store.async_add_dataset(
            hass, "otbr", tlv_parser.encode_tlv(newer)
        )

    with (
        patch(
            "python_otbr_api.OTBR.set_pending_dataset_tlvs", side_effect=store_newer
        ) as mock_set_pending,
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=bytes.fromhex(DATASET_CH16_PENDING),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    mock_set_pending.assert_awaited_once()
    assert exc_info.value.translation_key == "dataset_discarded"
    store = await dataset_store.async_get_store(hass)
    (stored,) = (tlv_parser.parse_tlv(entry.tlv) for entry in store.datasets.values())
    assert stored[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP].seconds == 10


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_an_answered_change_is_stored_as_sent_when_the_router_cannot_be_read(
    hass: HomeAssistant,
) -> None:
    """A read failing after the router answered does not fail the change."""
    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs"),
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


async def test_an_unanswered_change_is_reported_when_the_router_cannot_be_read(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """An unanswered change is reported as such when the router cannot be read."""
    with (
        patch(
            "python_otbr_api.OTBR.set_pending_dataset_tlvs",
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
    store = await dataset_store.async_get_store(hass)
    assert [entry.tlv for entry in store.datasets.values()] == [DATASET_CH16.hex()]
    windows = await async_get_propagation_windows(hass)
    assert windows.seconds_left("f642646da209b1c0") == 5 * 300


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_channel_outside_the_thread_band_is_refused(
    hass: HomeAssistant,
) -> None:
    """A channel outside 11 to 26 is refused before anything is read or built."""
    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending,
        patch("python_otbr_api.OTBR.get_active_dataset_tlvs") as mock_get_active,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 27, delay=5 * 300)

    assert exc_info.value.translation_key == "invalid_channel"
    assert exc_info.value.translation_placeholders == {"channel": "27"}
    mock_set_pending.assert_not_awaited()
    mock_get_active.assert_not_awaited()


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_network_whose_timestamp_is_exhausted_is_refused(
    hass: HomeAssistant,
) -> None:
    """A timestamp that cannot go up any further refuses the change unsent."""
    exhausted = tlv_parser.parse_tlv(DATASET_CH16.hex())
    exhausted[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP] = (
        tlv_parser.Timestamp.from_values(
            tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP, seconds=2**48 - 1
        )
    )
    with (
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs",
            return_value=bytes.fromhex(tlv_parser.encode_tlv(exhausted)),
        ),
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "timestamp_exhausted"
    mock_set_pending.assert_not_awaited()


async def test_async_change_channel_no_pending(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test async_change_channel when the pending dataset already expired."""

    store = await dataset_store.async_get_store(hass)
    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == DATASET_CH16.hex()

    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending,
        # Read before the write, then read back once the change has applied.
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs",
            side_effect=[DATASET_CH16, bytes.fromhex(DATASET_CH16_PENDING)],
        ),
        patch(
            "python_otbr_api.OTBR.get_pending_dataset_tlvs",
            return_value=None,
        ),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)
    sent = sent_pending(mock_set_pending)
    assert sent[tlv_parser.MeshcopTLVType.CHANNEL].channel == 15
    assert sent[
        tlv_parser.MeshcopTLVType.DELAYTIMER
    ] == tlv_parser.DelayTimer.from_milliseconds(5 * 300 * 1000)

    pending_dataset = tlv_parser.parse_tlv(DATASET_CH16_PENDING)
    pending_dataset.pop(tlv_parser.MeshcopTLVType.DELAYTIMER)

    assert len(store.datasets) == 1
    assert list(store.datasets.values())[0].tlv == tlv_parser.encode_tlv(
        pending_dataset
    )


async def test_async_change_channel_stores_what_the_leader_was_given(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """A router that registers with the leader holds no pending copy yet."""
    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs"),
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

    with patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending:
        await otbr_silabs_multiprotocol.async_change_channel(hass, 16, delay=0)
    mock_set_pending.assert_not_awaited()


async def test_async_change_channel_non_matching_url(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """Test async_change_channel when otbr is not configured."""
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    config_entry.runtime_data.url = OTBR_NON_MULTIPAN_URL
    with patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending:
        await otbr_silabs_multiprotocol.async_change_channel(hass, 16, delay=0)
    mock_set_pending.assert_not_awaited()


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


@pytest.mark.parametrize(
    "active_tlvs",
    [
        bytes.fromhex("0E0800000000"),
        _dataset_without(tlv_parser.MeshcopTLVType.EXTPANID),
    ],
    ids=["truncated", "no_extended_pan_id"],
)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_router_dataset_naming_no_network_is_refused(
    hass: HomeAssistant, get_active_dataset_tlvs: AsyncMock, active_tlvs: bytes
) -> None:
    """A router whose active dataset names no network is refused unsent."""
    get_active_dataset_tlvs.return_value = active_tlvs
    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "router_dataset_invalid"
    mock_set_pending.assert_not_awaited()


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_router_without_an_active_timestamp_is_behind_the_store(
    hass: HomeAssistant, get_active_dataset_tlvs: AsyncMock
) -> None:
    """A router reporting no active timestamp is behind any stored one."""
    get_active_dataset_tlvs.return_value = _dataset_without(
        tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP
    )
    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs") as mock_set_pending,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == "router_dataset_outdated"
    mock_set_pending.assert_not_awaited()


@pytest.mark.parametrize(
    ("api_version", "pending", "window", "stored_channel"),
    [
        ("0.6.0", None, 5 * 300, 16),
        ("0.5.0", bytes.fromhex(DATASET_CH16_PENDING), 5 * 300, 15),
        ("0.5.0", None, 0, 16),
        (OTBRError("down"), None, 5 * 300, 16),
    ],
    ids=["leader_registering", "holds_pending", "holds_none", "unreachable"],
)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_dropped_change_keeps_its_window_while_it_may_propagate(
    hass: HomeAssistant,
    api_version: str | Exception,
    pending: bytes | None,
    window: int,
    stored_channel: int,
) -> None:
    """A change whose connection dropped asks the router what it holds."""
    with (
        patch(
            "python_otbr_api.OTBR.set_pending_dataset_tlvs",
            side_effect=aiohttp.ServerDisconnectedError(),
        ),
        patch("python_otbr_api.OTBR.get_api_version", side_effect=[api_version]),
        patch("python_otbr_api.OTBR.get_pending_dataset_tlvs", return_value=pending),
        pytest.raises(HomeAssistantError),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    windows = await async_get_propagation_windows(hass)
    assert windows.seconds_left("f642646da209b1c0") == window
    store = await dataset_store.async_get_store(hass)
    (stored,) = (tlv_parser.parse_tlv(entry.tlv) for entry in store.datasets.values())
    assert stored[tlv_parser.MeshcopTLVType.CHANNEL].channel == stored_channel


@pytest.mark.parametrize(
    ("reason", "translation_key"),
    [
        ("not attached", "pending_dataset_refused_reason"),
        ("", "pending_dataset_refused"),
    ],
)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_rejected_change_hands_its_window_back(
    hass: HomeAssistant, reason: str, translation_key: str
) -> None:
    """A change the router or the leader rejected is reported, its reason if any."""
    with (
        patch(
            "python_otbr_api.OTBR.set_pending_dataset_tlvs",
            side_effect=PendingDatasetRejectedError(reason),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    assert exc_info.value.translation_key == translation_key
    windows = await async_get_propagation_windows(hass)
    assert windows.seconds_left("f642646da209b1c0") == 0


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_change_timing_out_before_the_write_hands_its_window_back(
    hass: HomeAssistant,
) -> None:
    """A timeout before the write leaves no window behind."""
    with (
        patch(
            "python_otbr_api.OTBR.set_pending_dataset_tlvs", side_effect=TimeoutError
        ),
        pytest.raises(HomeAssistantError),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    windows = await async_get_propagation_windows(hass)
    assert windows.seconds_left("f642646da209b1c0") == 0


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_an_answered_change_the_router_holds_no_copy_of_is_stored_as_sent(
    hass: HomeAssistant, get_active_dataset_tlvs: AsyncMock
) -> None:
    """An answered change is stored as sent while the router holds no copy."""
    get_active_dataset_tlvs.side_effect = [DATASET_CH16, None]
    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs"),
        patch("python_otbr_api.OTBR.get_pending_dataset_tlvs", return_value=None),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 15, delay=5 * 300)

    store = await dataset_store.async_get_store(hass)
    (stored,) = (tlv_parser.parse_tlv(entry.tlv) for entry in store.datasets.values())
    assert stored[tlv_parser.MeshcopTLVType.CHANNEL].channel == 15
    assert stored[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP].seconds == 2


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_a_same_channel_change_is_stored_with_its_timestamp(
    hass: HomeAssistant,
) -> None:
    """Read back on the same channel, the router's old active dataset is not the change."""
    with (
        patch("python_otbr_api.OTBR.set_pending_dataset_tlvs"),
        patch("python_otbr_api.OTBR.get_pending_dataset_tlvs", return_value=None),
    ):
        await otbr_silabs_multiprotocol.async_change_channel(hass, 16, delay=5 * 300)

    store = await dataset_store.async_get_store(hass)
    (stored,) = (tlv_parser.parse_tlv(entry.tlv) for entry in store.datasets.values())
    assert stored[tlv_parser.MeshcopTLVType.CHANNEL].channel == 16
    assert stored[tlv_parser.MeshcopTLVType.ACTIVETIMESTAMP].seconds == 2
