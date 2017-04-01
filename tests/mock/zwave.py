"""Mock helpers for Z-Wave component."""
from unittest.mock import MagicMock

from pydispatch import dispatcher

SIGNAL_VALUE_CHANGED = 'mock_value_changed'
SIGNAL_NODE = 'mock_node'
SIGNAL_NOTIFICATION = 'mock_notification'


def value_changed(value):
    """Fire a value changed."""
    dispatcher.send(
        SIGNAL_VALUE_CHANGED,
        value=value,
        node=value.node,
        network=value.node._network
    )


def node_changed(node):
    """Fire a node changed."""
    dispatcher.send(
        SIGNAL_NODE,
        node=node,
        network=node._network
    )


def notification(node_id, network=None):
    """Fire a notification."""
    dispatcher.send(
        SIGNAL_NOTIFICATION,
        args={'nodeId': node_id},
        network=network
    )


class MockNode(MagicMock):
    """Mock Z-Wave node."""

    def __init__(self, *,
                 node_id='567',
                 name='Mock Node',
                 manufacturer_id='ABCD',
                 product_id='123',
                 product_type='678',
                 command_classes=None,
                 can_wake_up_value=True,
                 **kwargs):
        """Initialize a Z-Wave mock node."""
        super().__init__()
        self.node_id = node_id
        self.name = name
        self.manufacturer_id = manufacturer_id
        self.product_id = product_id
        self.product_type = product_type
        self.can_wake_up_value = can_wake_up_value
        self._command_classes = command_classes or []
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])

    def has_command_class(self, command_class):
        """Test if mock has a command class."""
        return command_class in self._command_classes

    def get_battery_level(self):
        """Return mock battery level."""
        return 42

    def can_wake_up(self):
        """Return whether the node can wake up."""
        return self.can_wake_up_value

    def _get_child_mock(self, **kw):
        """Create child mocks with right MagicMock class."""
        return MagicMock(**kw)


class MockValue(MagicMock):
    """Mock Z-Wave value."""

    _mock_value_id = 1234

    def __init__(self, *,
                 label='Mock Value',
                 data=None,
                 data_items=None,
                 node=None,
                 instance=0,
                 index=0,
                 command_class=None,
                 units=None,
                 type=None,
                 value_id=None):
        """Initialize a Z-Wave mock value."""
        super().__init__()
        self.label = label
        self.data = data
        self.data_items = data_items
        self.node = node
        self.instance = instance
        self.index = index
        self.command_class = command_class
        self.units = units
        self.type = type
        if value_id is None:
            MockValue._mock_value_id += 1
            value_id = MockValue._mock_value_id
        self.value_id = value_id

    def _get_child_mock(self, **kw):
        """Create child mocks with right MagicMock class."""
        return MagicMock(**kw)

    def refresh(self):
        """Mock refresh of node value."""
        value_changed(self)


class MockEntityValues():
    """Mock Z-Wave entity values."""

    def __init__(self, **kwargs):
        """Initialize the mock zwave values."""
        self.primary = None
        self.wakeup = None
        self.battery = None
        self.power = None
        for name in kwargs:
            setattr(self, name, kwargs[name])

    def __iter__(self):
        """Allow iteration over all values."""
        return iter(self.__dict__.values())
