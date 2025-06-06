"""Mock classes for testing."""


class MockButton:
    """Mock button class."""

    def __init__(self, name) -> None:
        """Mock class constructor."""
        self.id = name
        self.name = name


class MockDevice:
    """Mock device class."""

    def __init__(self, id="TestDevice", name="TestDevice") -> None:
        """Mock class constructor."""
        self.id = id
        self.name = name
        self.buttons = [
            MockButton("Button 1"),
            MockButton("Button 2"),
            MockButton("Button 3"),
        ]
