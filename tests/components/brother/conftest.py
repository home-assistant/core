"""Test fixtures for brother."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from brother import BrotherSensors
import pytest

from homeassistant.components.brother.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TYPE

from tests.common import MockConfigEntry

BROTHER_DATA = BrotherSensors(
    belt_unit_remaining_life=97,
    belt_unit_remaining_pages=48436,
    black_counter=None,
    black_drum_counter=1611,
    black_drum_remaining_life=92,
    black_drum_remaining_pages=16389,
    black_ink_remaining=None,
    black_ink_status=None,
    black_ink=None,
    black_toner_remaining=75,
    black_toner_status=1,
    black_toner=80,
    bw_counter=709,
    color_counter=902,
    cyan_counter=None,
    cyan_drum_counter=1611,
    cyan_drum_remaining_life=92,
    cyan_drum_remaining_pages=16389,
    cyan_ink_remaining=None,
    cyan_ink_status=None,
    cyan_ink=None,
    cyan_toner_remaining=10,
    cyan_toner_status=1,
    cyan_toner=10,
    drum_counter=986,
    drum_remaining_life=92,
    drum_remaining_pages=11014,
    drum_status=1,
    duplex_unit_pages_counter=538,
    fuser_remaining_life=97,
    fuser_unit_remaining_pages=None,
    image_counter=None,
    laser_remaining_life=None,
    laser_unit_remaining_pages=48389,
    magenta_counter=None,
    magenta_drum_counter=1611,
    magenta_drum_remaining_life=92,
    magenta_drum_remaining_pages=16389,
    magenta_ink_remaining=None,
    magenta_ink_status=None,
    magenta_ink=None,
    magenta_toner_remaining=8,
    magenta_toner_status=2,
    magenta_toner=10,
    page_counter=986,
    pf_kit_1_remaining_life=98,
    pf_kit_1_remaining_pages=48741,
    pf_kit_mp_remaining_life=None,
    pf_kit_mp_remaining_pages=None,
    status="waiting",
    uptime=datetime(2024, 3, 3, 15, 4, 24, tzinfo=UTC),
    yellow_counter=None,
    yellow_drum_counter=1611,
    yellow_drum_remaining_life=92,
    yellow_drum_remaining_pages=16389,
    yellow_ink_remaining=None,
    yellow_ink_status=None,
    yellow_ink=None,
    yellow_toner_remaining=2,
    yellow_toner_status=2,
    yellow_toner=10,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.brother.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_brother_client() -> Generator[AsyncMock, None, None]:
    """Mock Brother client."""
    with (
        patch("homeassistant.components.brother.Brother", autospec=True) as mock_client,
        patch(
            "homeassistant.components.brother.config_flow.Brother",
            new=mock_client,
        ),
    ):
        client = mock_client.create.return_value
        client.async_update.return_value = BROTHER_DATA
        client.serial = "0123456789"
        client.mac = "AA:BB:CC:DD:EE:FF"
        client.model = "HL-L2340DW"
        client.firmware = "1.2.3"

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HL-L2340DW 0123456789",
        unique_id="0123456789",
        data={CONF_HOST: "localhost", CONF_TYPE: "laser"},
    )
