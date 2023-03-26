"""Provide common mystrom fixtures and mocks."""


class ResponseMock:
    """Mock class for aiohttp response."""

    def __init__(self, json: dict, status: int):
        """Initialize the response mock."""
        self._json = json
        self.status = status

    @property
    def headers(self) -> dict:
        """Headers of the response."""
        return {"Content-Type": "application/json"}

    async def json(self) -> dict:
        """Return the json content of the response."""
        return self._json

    async def __aexit__(self, exc_type, exc, tb):
        """Exit."""
        pass

    async def __aenter__(self):
        """Enter."""
        return self
