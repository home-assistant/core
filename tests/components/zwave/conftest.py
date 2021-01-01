"""Fixtures for Z-Wave tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.zwave import const

from tests.components.light.conftest import mock_light_profiles  # noqa
from tests.mock.zwave import MockNetwork, MockNode, MockOption, MockValue


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
def mock_discovery():
    """Mock discovery."""
    discovery = MagicMock()
    discovery.async_load_platform = AsyncMock(return_value=None)
    yield discovery


@pytest.fixture
def mock_import_module():
    """Mock import module."""
    platform = MagicMock()
    mock_device = MagicMock()
    mock_device.name = "test_device"
    platform.get_device.return_value = mock_device

    import_module = MagicMock()
    import_module.return_value = platform
    yield import_module


@pytest.fixture
def mock_values():
    """Mock values."""
    node = MockNode()
    mock_schema = {
        const.DISC_COMPONENT: "mock_component",
        const.DISC_VALUES: {
            const.DISC_PRIMARY: {const.DISC_COMMAND_CLASS: ["mock_primary_class"]},
            "secondary": {const.DISC_COMMAND_CLASS: ["mock_secondary_class"]},
            "optional": {
                const.DISC_COMMAND_CLASS: ["mock_optional_class"],
                const.DISC_OPTIONAL: True,
            },
        },
    }
    value_class = MagicMock()
    value_class.primary = MockValue(
        command_class="mock_primary_class", node=node, value_id=1000
    )
    value_class.secondary = MockValue(command_class="mock_secondary_class", node=node)
    value_class.duplicate_secondary = MockValue(
        command_class="mock_secondary_class", node=node
    )
    value_class.optional = MockValue(command_class="mock_optional_class", node=node)
    value_class.no_match_value = MockValue(command_class="mock_bad_class", node=node)

    yield (node, value_class, mock_schema)
