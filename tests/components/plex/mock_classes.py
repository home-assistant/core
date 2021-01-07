"""Mock classes used in tests."""

GDM_SERVER_PAYLOAD = [
    {
        "data": {
            "Content-Type": "plex/media-server",
            "Name": "plextest",
            "Port": "32400",
            "Resource-Identifier": "1234567890123456789012345678901234567890",
            "Updated-At": "157762684800",
            "Version": "1.0",
        },
        "from": ("1.2.3.4", 32414),
    }
]

GDM_CLIENT_PAYLOAD = [
    {
        "data": {
            "Content-Type": "plex/media-player",
            "Device-Class": "stb",
            "Name": "plexamp",
            "Port": "36000",
            "Product": "Plexamp",
            "Protocol": "plex",
            "Protocol-Capabilities": "timeline,playback,playqueues,playqueues-creation",
            "Protocol-Version": "1",
            "Resource-Identifier": "client-2",
            "Version": "1.1.0",
        },
        "from": ("1.2.3.10", 32412),
    },
    {
        "data": {
            "Content-Type": "plex/media-player",
            "Device-Class": "pc",
            "Name": "Chrome",
            "Port": "32400",
            "Product": "Plex Web",
            "Protocol": "plex",
            "Protocol-Capabilities": "timeline,playback,navigation,mirror,playqueues",
            "Protocol-Version": "3",
            "Resource-Identifier": "client-1",
            "Version": "4.40.1",
        },
        "from": ("1.2.3.4", 32412),
    },
    {
        "data": {
            "Content-Type": "plex/media-player",
            "Device-Class": "mobile",
            "Name": "SHIELD Android TV",
            "Port": "32500",
            "Product": "Plex for Android (TV)",
            "Protocol": "plex",
            "Protocol-Capabilities": "timeline,playback,navigation,mirror,playqueues,provider-playback",
            "Protocol-Version": "1",
            "Resource-Identifier": "client-999",
            "Updated-At": "1597686153",
            "Version": "8.5.0.19697",
        },
        "from": ("1.2.3.11", 32412),
    },
]


class MockGDM:
    """Mock a GDM instance."""

    def __init__(self, disabled=False):
        """Initialize the object."""
        self.entries = []
        self.disabled = disabled

    def scan(self, scan_for_clients=False):
        """Mock the scan call."""
        if self.disabled:
            return

        if scan_for_clients:
            self.entries = GDM_CLIENT_PAYLOAD
        else:
            self.entries = GDM_SERVER_PAYLOAD
