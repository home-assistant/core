"""Mock classes used in tests."""

MOCK_HOST_1 = "1.2.3.4"
MOCK_PORT_1 = "32400"
MOCK_HOST_2 = "4.3.2.1"
MOCK_PORT_2 = "32400"


class MockAvailableServer:  # pylint: disable=too-few-public-methods
    """Mock avilable server objects."""

    def __init__(self, name, client_id):
        """Initialize the object."""
        self.name = name
        self.clientIdentifier = client_id  # pylint: disable=invalid-name
        self.provides = ["server"]


class MockConnection:  # pylint: disable=too-few-public-methods
    """Mock a single account resource connection object."""

    def __init__(self, ssl):
        """Initialize the object."""
        prefix = "https" if ssl else "http"
        self.httpuri = f"{prefix}://{MOCK_HOST_1}:{MOCK_PORT_1}"
        self.uri = "{prefix}://{MOCK_HOST_2}:{MOCK_PORT_2}"
        self.local = True


class MockConnections:  # pylint: disable=too-few-public-methods
    """Mock a list of resource connections."""

    def __init__(self, ssl=False):
        """Initialize the object."""
        self.connections = [MockConnection(ssl)]
