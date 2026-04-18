"""Common fixtures for the Flipper IR tests."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from homeassistant.components.flipper_ir.const import CONF_COMMANDS, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

VALID_IR_FILE = b"""Filetype: IR signals file
Version: 1
#
name: Power
type: parsed
protocol: NEC
address: 00 00 00 00
command: 45 00 00 00
#
name: Vol_up
type: parsed
protocol: NEC
address: 00 00 00 00
command: 46 00 00 00
#
name: Vol_down
type: parsed
protocol: NEC
address: 00 00 00 00
command: 47 00 00 00
"""


@pytest.fixture
def mock_ir_content() -> bytes:
    """Return mock Flipper IR file content."""
    return VALID_IR_FILE


@pytest.fixture
def mock_process_uploaded_file(
    tmp_path: Path, mock_ir_content: bytes
) -> Generator[MagicMock]:
    """Mock a Flipper IR file upload."""
    file_id = str(uuid4())

    @contextmanager
    def _mock_process_uploaded_file(
        hass: HomeAssistant, uploaded_file_id: str
    ) -> Iterator[Path]:
        file_path = tmp_path / uploaded_file_id
        file_path.write_bytes(mock_ir_content)
        yield file_path

    with patch(
        "homeassistant.components.flipper_ir.config_flow.process_uploaded_file",
        side_effect=_mock_process_uploaded_file,
    ) as mock_upload:
        mock_upload.file_id = file_id
        yield mock_upload


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry with some Flipper IR commands."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living Room TV",
        data={
            CONF_NAME: "Living Room TV",
            CONF_COMMANDS: [
                {"name": "Power", "type": "parsed", "protocol": "NEC"},
                {"name": "Vol_up", "type": "parsed", "protocol": "NEC"},
                {"name": "Vol_down", "type": "parsed", "protocol": "NEC"},
            ],
        },
    )
