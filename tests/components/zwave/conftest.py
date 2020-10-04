"""Fixtures for Z-Wave tests."""
import pytest

from homeassistant.components.zwave import node_entity

from tests.async_mock import MagicMock, patch
from tests.mock.zwave import MockNetwork, MockNode, MockOption


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
            "openzwave.option": base_mock.option,
            "openzwave.network": base_mock.network,
            "openzwave.group": base_mock.group,
        },
    ):
        yield base_mock


@pytest.fixture
def mock_node():
    """Provide mock z-wave node."""
    node = MockNode(
        query_stage="Dynamic",
        is_awake=True,
        is_ready=False,
        is_failed=False,
        is_info_received=True,
        max_baud_rate=40000,
        is_zwave_plus=False,
        capabilities=[],
        neighbors=[],
        location=None,
    )
    yield node


@pytest.fixture
def mock_entity(mock_node):
    """Provide mock z-wave node entity."""
    yield node_entity.ZWaveNodeEntity(mock_node, MagicMock())
