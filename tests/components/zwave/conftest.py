"""Fixtures for Z-Wave tests."""
from unittest.mock import MagicMock, patch

import pytest

from tests.mock.zwave import MockNetwork, MockOption


@pytest.fixture
def mock_openzwave():
    """Mock out Open Z-Wave."""
    base_mock = MagicMock()
    libopenzwave = base_mock.libopenzwave
    libopenzwave.__file__ = "test"
    base_mock.network.ZWaveNetwork = MockNetwork
    base_mock.option.ZWaveOption = MockOption

    with patch.dict(
        "sys.modules",
        {
            "libopenzwave": libopenzwave,
            "openzwave.group": base_mock.group,
            "openzwave.network": base_mock.network,
            "openzwave.option": base_mock.option,
        },
    ):
        yield base_mock
