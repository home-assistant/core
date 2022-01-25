"""Fixtures for Flashforge integration tests."""


from itertools import cycle
from unittest.mock import MagicMock, patch

import pytest

from .const_response import (
    MACHINE_INFO,
    PROGRESS_PRINTING,
    PROGRESS_READY,
    STATUS_PRINTING,
    STATUS_READY,
    TEMP_PRINTING,
    TEMP_READY,
)


@pytest.fixture
def mock_printer_network() -> MagicMock:
    """Change the values that the printer responds with."""
    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        network = mock_network.return_value
        network.sendInfoRequest.return_value = MACHINE_INFO
        network.sendStatusRequest.side_effect = cycle([STATUS_READY, STATUS_PRINTING])
        network.sendTempRequest.side_effect = cycle([TEMP_READY, TEMP_PRINTING])
        network.sendProgressRequest.side_effect = cycle(
            [PROGRESS_READY, PROGRESS_PRINTING]
        )

        yield network


@pytest.fixture
def mock_printer_discovery() -> MagicMock:
    """Mock printer discovery."""
    with patch("ffpp.Discovery.getPrinters", autospec=True) as get_printers:
        get_printers.return_value = [("Adventurer4", "192.168.0.64")]
        yield get_printers
