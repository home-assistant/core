"""Mock helpers for Z-Wave component."""
from unittest.mock import MagicMock

from pydispatch import dispatcher

SIGNAL_VALUE_CHANGED = 'mock_value_changed'


def value_changed(value):
    """Fire a value changed."""
    dispatcher.send(
        SIGNAL_VALUE_CHANGED,
        value=value,
        node=value.node,
        network=value.node._network
    )


class MockNode(MagicMock):
    """Mock Z-Wave node."""

    def __init__(self, *,
                 node_id='567',
                 name='Mock Node',
                 manufacturer_id='ABCD',
                 product_id='123',
                 command_classes=None):
        """Initialize a Z-Wave mock node."""
        super().__init__()
        self.node_id = node_id
        self.name = name
        self.manufacturer_id = manufacturer_id
        self.product_id = product_id
        self._command_classes = command_classes or []

    def has_command_class(self, command_class):
        """Test if mock has a command class."""
        return command_class in self._command_classes

    def _get_child_mock(self, **kw):
        """Create child mocks with right MagicMock class."""
        return MagicMock(**kw)


class MockValue(MagicMock):
    """Mock Z-Wave value."""

    _mock_value_id = 1234

    def __init__(self, *,
                 label='Mock Value',
                 data=None,
                 node=None,
                 instance=0,
                 index=0,
                 value_id=None):
        """Initialize a Z-Wave mock value."""
        super().__init__()
        self.label = label
        self.data = data
        self.node = node
        self.instance = instance
        self.index = 0
        if value_id is None:
            MockValue._mock_value_id += 1
            value_id = MockValue._mock_value_id
        self.value_id = value_id

    def _get_child_mock(self, **kw):
        """Create child mocks with right MagicMock class."""
        return MagicMock(**kw)
