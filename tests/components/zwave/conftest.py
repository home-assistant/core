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
            "homeassistant.components.zwave.__init__.group": base_mock.group,
            "homeassistant.components.zwave.__init__.network": base_mock.network,
            "homeassistant.components.zwave.node_entity.network": base_mock.network,
            "homeassistant.components.zwave.__init__.option": base_mock.option,
            "homeassistant.components.zwave.config_flow.option": base_mock.option,
        },
    ):
        yield base_mock
