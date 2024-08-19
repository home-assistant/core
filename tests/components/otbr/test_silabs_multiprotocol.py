"""Test OTBR Silicon Labs Multiprotocol support."""

from collections.abc import Generator
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, patch

import pytest
from python_otbr_api import ActiveDataSet, tlv_parser

from homeassistant.components import otbr
from homeassistant.components.otbr import (
    silabs_multiprotocol as otbr_silabs_multiprotocol,
)
from homeassistant.components.thread import dataset_store
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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


ADDON_DISCOVERY_INFO = {
    "config": {
        "addon": "Silicon Labs Multiprotocol",
        "host": "core-silabs-multiprotocol",
        "port": 8081,
    },
    "uuid": "1234",
}


ADDON_DISCOVERY_INFO_OTHER_UUID = {
    "config": {
        "addon": "Silicon Labs Multiprotocol",
        "host": "core-silabs-multiprotocol",
        "port": 8081,
    },
    "uuid": "4321",
}


@pytest.fixture(name="discovery_info")
def discovery_info_fixture() -> Any:
    """Return the discovery info from the supervisor."""
    return DEFAULT


@pytest.fixture(name="get_addon_discovery_info", autouse=True)
def get_addon_discovery_info_fixture(discovery_info: Any) -> Generator[AsyncMock]:
    """Mock get add-on discovery info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_discovery_info",
        return_value=discovery_info,
    ) as get_addon_discovery_info:
        yield get_addon_discovery_info


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO])
async def test_async_change_channel(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test test_async_change_channel."""

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


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO])
async def test_async_change_channel_no_pending(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test test_async_change_channel when the pending dataset already expired."""

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


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO])
async def test_async_change_channel_no_update(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test test_async_change_channel when we didn't get a dataset from the OTBR."""

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


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO_OTHER_UUID])
async def test_async_change_channel_non_matching_uuid(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test async_change_channel when otbr is not configured."""
    with patch("python_otbr_api.OTBR.set_channel") as mock_set_channel:
        await otbr_silabs_multiprotocol.async_change_channel(hass, 16, delay=0)
    mock_set_channel.assert_not_awaited()


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO])
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


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO])
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


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO])
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
        await otbr_silabs_multiprotocol.async_get_channel(hass)
    mock_get_active_dataset.assert_not_awaited()


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO_OTHER_UUID])
async def test_async_get_channel_non_matching_uuid(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test async_change_channel when otbr is not configured."""
    with patch("python_otbr_api.OTBR.get_active_dataset") as mock_get_active_dataset:
        assert await otbr_silabs_multiprotocol.async_get_channel(hass) is None
    mock_get_active_dataset.assert_not_awaited()


@pytest.mark.parametrize(
    ("url", "expected"),
    [(OTBR_MULTIPAN_URL, True), (OTBR_NON_MULTIPAN_URL, False)],
)
@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO])
async def test_async_using_multipan(
    hass: HomeAssistant, otbr_config_entry_multipan, url: str, expected: bool
) -> None:
    """Test async_change_channel when otbr is not configured."""
    data: otbr.OTBRData = hass.data[otbr.DOMAIN]
    data.url = url

    assert await otbr_silabs_multiprotocol.async_using_multipan(hass) is expected


async def test_async_using_multipan_no_otbr(hass: HomeAssistant) -> None:
    """Test async_change_channel when otbr is not configured."""

    assert await otbr_silabs_multiprotocol.async_using_multipan(hass) is False


@pytest.mark.parametrize("discovery_info", [ADDON_DISCOVERY_INFO_OTHER_UUID])
async def test_async_using_multipan_non_matching_uuid(
    hass: HomeAssistant, otbr_config_entry_multipan
) -> None:
    """Test async_change_channel when otbr is not configured."""
    assert await otbr_silabs_multiprotocol.async_using_multipan(hass) is False
