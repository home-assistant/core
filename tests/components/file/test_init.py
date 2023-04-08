"""The tests for the file component."""
import os
from unittest.mock import call, mock_open, patch

import pytest

from homeassistant.components import file
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


@pytest.mark.parametrize(
    "mode",
    [
        None,
        "w",
        "x",
        "a",
    ],
)
async def test_file_write(hass: HomeAssistant, mode: str) -> None:
    """Test the notify file output."""
    filename = "mock_file"
    content = "one, two, testing, testing"
    with assert_setup_component(1):
        assert await async_setup_component(
            hass,
            file.DOMAIN,
            {"file": {"allowlist_write_dirs": [hass.config.path()]}},
        )

    m_open = mock_open()
    with patch("homeassistant.components.file.open", m_open, create=True):
        args = {"content": content, "filename": filename}
        if mode is not None:
            args["mode"] = mode
        await hass.services.async_call("file", "write", args, blocking=True)

        full_filename = os.path.join(hass.config.path(), filename)
        assert m_open.call_count == 1
        assert m_open.call_args == call(
            full_filename, mode if mode is not None else "w", encoding="utf8"
        )
        assert m_open.return_value.write.call_count == 1


async def test_file_write_allowlist(hass: HomeAssistant) -> None:
    """Test the allowlist."""
    content = "one, two, testing, testing"
    with assert_setup_component(1):
        assert await async_setup_component(
            hass,
            file.DOMAIN,
            {"file": {"allowlist_write_dirs": ["inner"]}},
        )

    with pytest.raises(ValueError):
        args = {"content": content, "filename": "mock_file"}
        await hass.services.async_call("file", "write", args, blocking=True)
