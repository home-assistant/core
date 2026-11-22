"""Common test tools for the Hikvision integration."""

from collections.abc import Callable
from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hikvision import STREAM_WATCH
from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Hikvision integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def image_channel_with(path: str, element: str) -> str:
    """Return an image channel document with one setting, nested as its path says.

    `element` follows the tag: its attributes, then `>` and the value.
    """
    *groups, leaf = path.split("/")
    document = f"<{leaf}{element}</{leaf}>"
    for group in reversed(groups):
        document = f"<{group}>{document}</{group}>"
    return (
        '<ImageChannel version="2.0" '
        f'xmlns="http://www.hikvision.com/ver20/XMLSchema">{document}</ImageChannel>'
    )


def entity_callbacks(camera: MagicMock) -> list[Callable[[str], None]]:
    """Return the callbacks the entities registered with pyHik, in order.

    Not the watch of the stream, which every setup registers first.
    """
    return [
        call.args[0]
        for call in camera.add_update_callback.call_args_list
        if not call.args[1].endswith(f".{STREAM_WATCH}")
    ]
