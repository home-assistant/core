"""Common fixtures for the HDFury tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hdfury.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.123"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hdfury.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="000123456789",
        data={
            CONF_HOST: TEST_HOST,
        },
    )


@pytest.fixture(autouse=True)
def mock_hdfury_client() -> Generator[AsyncMock]:
    """Mock a HDFury client."""
    with (
        patch(
            "homeassistant.components.hdfury.config_flow.HDFuryAPI",
            autospec=True,
        ) as mock_cf_client,
        patch(
            "homeassistant.components.hdfury.coordinator.HDFuryAPI",
            autospec=True,
        ) as mock_coord_client,
    ):
        # Config flow client
        cf_client = mock_cf_client.return_value
        cf_client.get_board = AsyncMock(
            return_value={
                "hostname": "VRROOM-02",
                "ipaddress": "192.168.1.123",
                "serial": "000123456789",
                "pcbv": "3",
                "version": "FW: 0.61",
            }
        )

        # Coordinator client
        coord_client = mock_coord_client.return_value
        coord_client.get_board = cf_client.get_board
        coord_client.get_info = AsyncMock(
            return_value={
                "portseltx0": "0",
                "portseltx1": "4",
                "opmode": "0",
                "RX0": "4K59.937 593MHz 422 BT2020 12b 2.2",
                "RX1": "no signal",
                "TX0": "4K59.937 593MHz 422 BT2020 12b 2.2",
                "TX1": "4K59.937 593MHz 422 BT2020 12b 2.2",
                "AUD0": "bitstream 48kHz",
                "AUD1": "bitstream 48kHz",
                "AUDOUT": "bitstream 48kHz",
                "EARCRX": "eARC/ARC not active",
                "SINK0": "LG TV SSCR2: 4K120 444 FRL6 VRR DSC ALLM DV HDR10 HLG",
                "EDIDA0": "MAT Atmos, DD Atmos, DD, DTS:X+IMAX, DTSHD, DTS, LPCM 2.0 192kHz 24b",
                "SINK1": "Signify FCD: 4K60 444 DV HDR10+ HLG",
                "EDIDA1": "DD, DTS, LPCM 2.0 48kHz 24b",
                "SINK2": "Bose CineMate: 4K60 420 ",
                "EDIDA2": "DD, DTS, LPCM 7.1 96kHz 24b",
            }
        )
        coord_client.get_config = AsyncMock(
            return_value={
                "cec": "1",
                "cec0en": "1",
                "cec1en": "1",
                "cec2en": "1",
                "cec3en": "1",
                "autosw": "1",
                "iractive": "1",
                "tx0plus5": "1",
                "tx1plus5": "1",
                "htpcmode0": "0",
                "htpcmode1": "0",
                "htpcmode2": "0",
                "htpcmode3": "0",
                "mutetx0": "1",
                "mutetx1": "1",
                "relay": "0",
                "macaddr": "c7:1c:df:9d:f6:40",
                "oled": "1",
            }
        )

        yield coord_client
