"""Tests for the Onkyo integration."""

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from aioonkyo import ReceiverInfo

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

RECEIVER_INFO = ReceiverInfo(
    host="192.168.0.101",
    ip="192.168.0.101",
    model_name="TX-NR7100",
    identifier="0009B0123456",
)

RECEIVER_INFO_2 = ReceiverInfo(
    host="192.168.0.102",
    ip="192.168.0.102",
    model_name="TX-RZ50",
    identifier="0009B0ABCDEF",
)


@contextmanager
def mock_discovery(receiver_infos: Iterable[ReceiverInfo] | None) -> Generator[None]:
    """Mock discovery functions."""

    async def get_info(host: str) -> ReceiverInfo | None:
        """Get receiver info by host."""
        for info in receiver_infos:
            if info.host == host:
                return info
        return None

    def get_infos(host: str) -> MagicMock:
        """Get receiver infos from broadcast."""
        discover_mock = MagicMock()
        discover_mock.__aiter__.return_value = receiver_infos
        return discover_mock

    discover_kwargs = {}
    interview_kwargs = {}
    if receiver_infos is None:
        discover_kwargs["side_effect"] = OSError
        interview_kwargs["side_effect"] = OSError
    else:
        discover_kwargs["new"] = get_infos
        interview_kwargs["new"] = get_info

    with (
        patch(
            "homeassistant.components.onkyo.receiver.aioonkyo.discover",
            **discover_kwargs,
        ),
        patch(
            "homeassistant.components.onkyo.receiver.aioonkyo.interview",
            **interview_kwargs,
        ),
    ):
        yield


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the component."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
