"""Common fixtures for the Onkyo tests."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aioonkyo import Code, Instruction, Kind, Receiver, Status, Zone, status
import pytest

from homeassistant.components.onkyo.const import DOMAIN

from . import RECEIVER_INFO, RECEIVER_INFO_2, mock_discovery

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_default_discovery() -> Generator[None]:
    """Mock the discovery functions with default info."""
    with (
        patch.multiple(
            "homeassistant.components.onkyo.receiver",
            DEVICE_INTERVIEW_TIMEOUT=1,
            DEVICE_DISCOVERY_TIMEOUT=1,
        ),
        mock_discovery([RECEIVER_INFO, RECEIVER_INFO_2]),
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock integration setup."""
    with patch(
        "homeassistant.components.onkyo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connect() -> Generator[AsyncMock]:
    """Mock an Onkyo connect."""
    with patch(
        "homeassistant.components.onkyo.receiver.connect",
    ) as connect:
        yield connect.return_value.__aenter__


INITIAL_MESSAGES = [
    status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.ON
    ),
    status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.ZONE2), None, status.Power.Param.ON
    ),
    status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.ZONE3), None, status.Power.Param.STANDBY
    ),
    status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.ON
    ),
    status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.ZONE2), None, status.Power.Param.ON
    ),
    status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.ZONE3), None, status.Power.Param.STANDBY
    ),
    status.Volume(Code.from_kind_zone(Kind.VOLUME, Zone.ZONE2), None, 50),
    status.Muting(
        Code.from_kind_zone(Kind.MUTING, Zone.MAIN), None, status.Muting.Param.OFF
    ),
    status.InputSource(
        Code.from_kind_zone(Kind.INPUT_SOURCE, Zone.MAIN),
        None,
        status.InputSource.Param("24"),
    ),
    status.InputSource(
        Code.from_kind_zone(Kind.INPUT_SOURCE, Zone.ZONE2),
        None,
        status.InputSource.Param("00"),
    ),
    status.ListeningMode(
        Code.from_kind_zone(Kind.LISTENING_MODE, Zone.MAIN),
        None,
        status.ListeningMode.Param("01"),
    ),
    status.ListeningMode(
        Code.from_kind_zone(Kind.LISTENING_MODE, Zone.ZONE2),
        None,
        status.ListeningMode.Param("00"),
    ),
    status.HDMIOutput(
        Code.from_kind_zone(Kind.HDMI_OUTPUT, Zone.MAIN),
        None,
        status.HDMIOutput.Param.MAIN,
    ),
    status.TunerPreset(Code.from_kind_zone(Kind.TUNER_PRESET, Zone.MAIN), None, 1),
    status.AudioInformation(
        Code.from_kind_zone(Kind.AUDIO_INFORMATION, Zone.MAIN),
        None,
        auto_phase_control_phase="Normal",
    ),
    status.VideoInformation(
        Code.from_kind_zone(Kind.VIDEO_INFORMATION, Zone.MAIN),
        None,
        input_color_depth="24bit",
    ),
    status.FLDisplay(Code.from_kind_zone(Kind.FL_DISPLAY, Zone.MAIN), None, "LALALA"),
    status.NotAvailable(
        Code.from_kind_zone(Kind.AUDIO_INFORMATION, Zone.MAIN),
        None,
        Kind.AUDIO_INFORMATION,
    ),
    status.NotAvailable(
        Code.from_kind_zone(Kind.VIDEO_INFORMATION, Zone.MAIN),
        None,
        Kind.VIDEO_INFORMATION,
    ),
    status.Raw(None, None),
]


@pytest.fixture
def read_queue() -> asyncio.Queue[Status | None]:
    """Read messages queue."""
    return asyncio.Queue()


@pytest.fixture
def writes() -> list[Instruction]:
    """Written messages."""
    return []


@pytest.fixture
def mock_receiver(
    mock_connect: AsyncMock,
    read_queue: asyncio.Queue[Status | None],
    writes: list[Instruction],
) -> AsyncMock:
    """Mock an Onkyo receiver."""
    receiver_class = AsyncMock(Receiver, auto_spec=True)
    receiver = receiver_class.return_value

    for message in INITIAL_MESSAGES:
        read_queue.put_nowait(message)

    async def read() -> Status:
        return await read_queue.get()

    async def write(message: Instruction) -> None:
        writes.append(message)

    receiver.read = read
    receiver.write = write

    mock_connect.return_value = receiver

    return receiver


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    data = {"host": RECEIVER_INFO.host}
    options = {
        "volume_resolution": 80,
        "max_volume": 100,
        "input_sources": {"12": "TV", "24": "FM Radio"},
        "listening_modes": {"00": "Stereo", "04": "THX"},
    }

    return MockConfigEntry(
        domain=DOMAIN,
        title=RECEIVER_INFO.model_name,
        unique_id=RECEIVER_INFO.identifier,
        data=data,
        options=options,
    )
