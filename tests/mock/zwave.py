"""Mock helpers for Z-Wave component."""
from unittest.mock import MagicMock

from pydispatch import dispatcher


def value_changed(value):
    """Fire a value changed."""
    dispatcher.send(
        MockNetwork.SIGNAL_VALUE_CHANGED,
        value=value,
        node=value.node,
        network=value.node._network
    )


def node_changed(node):
    """Fire a node changed."""
    dispatcher.send(
        MockNetwork.SIGNAL_NODE,
        node=node,
        network=node._network
    )


def notification(node_id, network=None):
    """Fire a notification."""
    dispatcher.send(
        MockNetwork.SIGNAL_NOTIFICATION,
        args={'nodeId': node_id},
        network=network
    )


class MockOption(MagicMock):
    """Mock Z-Wave options."""

    def __init__(self, device=None, config_path=None, user_path=None,
                 cmd_line=None):
        """Initialize a Z-Wave mock options."""
        super().__init__()
        self.device = device
        self.config_path = config_path
        self.user_path = user_path
        self.cmd_line = cmd_line

    def _get_child_mock(self, **kw):
        """Create child mocks with right MagicMock class."""
        return MagicMock(**kw)


class MockNetwork(MagicMock):
    """Mock Z-Wave network."""

    SIGNAL_NETWORK_FAILED = 'mock_NetworkFailed'
    SIGNAL_NETWORK_STARTED = 'mock_NetworkStarted'
    SIGNAL_NETWORK_READY = 'mock_NetworkReady'
    SIGNAL_NETWORK_STOPPED = 'mock_NetworkStopped'
    SIGNAL_NETWORK_RESETTED = 'mock_DriverResetted'
    SIGNAL_NETWORK_AWAKED = 'mock_DriverAwaked'
    SIGNAL_DRIVER_FAILED = 'mock_DriverFailed'
    SIGNAL_DRIVER_READY = 'mock_DriverReady'
    SIGNAL_DRIVER_RESET = 'mock_DriverReset'
    SIGNAL_DRIVER_REMOVED = 'mock_DriverRemoved'
    SIGNAL_GROUP = 'mock_Group'
    SIGNAL_NODE = 'mock_Node'
    SIGNAL_NODE_ADDED = 'mock_NodeAdded'
    SIGNAL_NODE_EVENT = 'mock_NodeEvent'
    SIGNAL_NODE_NAMING = 'mock_NodeNaming'
    SIGNAL_NODE_NEW = 'mock_NodeNew'
    SIGNAL_NODE_PROTOCOL_INFO = 'mock_NodeProtocolInfo'
    SIGNAL_NODE_READY = 'mock_NodeReady'
    SIGNAL_NODE_REMOVED = 'mock_NodeRemoved'
    SIGNAL_SCENE_EVENT = 'mock_SceneEvent'
    SIGNAL_VALUE = 'mock_Value'
    SIGNAL_VALUE_ADDED = 'mock_ValueAdded'
    SIGNAL_VALUE_CHANGED = 'mock_ValueChanged'
    SIGNAL_VALUE_REFRESHED = 'mock_ValueRefreshed'
    SIGNAL_VALUE_REMOVED = 'mock_ValueRemoved'
    SIGNAL_POLLING_ENABLED = 'mock_PollingEnabled'
    SIGNAL_POLLING_DISABLED = 'mock_PollingDisabled'
    SIGNAL_CREATE_BUTTON = 'mock_CreateButton'
    SIGNAL_DELETE_BUTTON = 'mock_DeleteButton'
    SIGNAL_BUTTON_ON = 'mock_ButtonOn'
    SIGNAL_BUTTON_OFF = 'mock_ButtonOff'
    SIGNAL_ESSENTIAL_NODE_QUERIES_COMPLETE = \
        'mock_EssentialNodeQueriesComplete'
    SIGNAL_NODE_QUERIES_COMPLETE = 'mock_NodeQueriesComplete'
    SIGNAL_AWAKE_NODES_QUERIED = 'mock_AwakeNodesQueried'
    SIGNAL_ALL_NODES_QUERIED = 'mock_AllNodesQueried'
    SIGNAL_ALL_NODES_QUERIED_SOME_DEAD = 'mock_AllNodesQueriedSomeDead'
    SIGNAL_MSG_COMPLETE = 'mock_MsgComplete'
    SIGNAL_NOTIFICATION = 'mock_Notification'
    SIGNAL_CONTROLLER_COMMAND = 'mock_ControllerCommand'
    SIGNAL_CONTROLLER_WAITING = 'mock_ControllerWaiting'

    STATE_STOPPED = 0
    STATE_FAILED = 1
    STATE_RESETTED = 3
    STATE_STARTED = 5
    STATE_AWAKED = 7
    STATE_READY = 10

    def __init__(self, options=None, *args, **kwargs):
        """Initialize a Z-Wave mock network."""
        super().__init__()
        self.options = options
        self.state = MockNetwork.STATE_STOPPED


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
                 manufacturer_name='Test Manufacturer',
                 product_name='Test Product',
                 network=None,
                 **kwargs):
        """Initialize a Z-Wave mock node."""
        super().__init__()
        self.node_id = node_id
        self.name = name
        self.manufacturer_id = manufacturer_id
        self.product_id = product_id
        self.product_type = product_type
        self.manufacturer_name = manufacturer_name
        self.product_name = product_name
        self.can_wake_up_value = can_wake_up_value
        self._command_classes = command_classes or []
        if network is not None:
            self._network = network
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
                 node=None,
                 instance=0,
                 index=0,
                 value_id=None,
                 **kwargs):
        """Initialize a Z-Wave mock value."""
        super().__init__()
        self.label = label
        self.node = node
        self.instance = instance
        self.index = index
        if value_id is None:
            MockValue._mock_value_id += 1
            value_id = MockValue._mock_value_id
        self.value_id = value_id
        for attr_name in kwargs:
            setattr(self, attr_name, kwargs[attr_name])

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
