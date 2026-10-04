"""Test OTBR Silicon Labs Multiprotocol support."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_otbr_api import ActiveDataSet, Timestamp, tlv_parser

from homeassistant.components.otbr import (
    silabs_multiprotocol as otbr_silabs_multiprotocol,
)
from homeassistant.components.otbr.util import async_get_issued_timestamps
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
