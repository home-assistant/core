"""Test the Discovergy integration."""
from tests.components.discovergy.const import GET_METERS, LAST_READING, LAST_READING_GAS


class MockDiscovergy:
    """Mock Discovergy class."""

    _thrown_error: Exception | None = None

    async def meters(self):
        """Return mock meters."""
        return GET_METERS

    async def meter_last_reading(self, meter_id: str):
        """Return mock meter last reading."""
        if self._thrown_error:
            raise self._thrown_error
        return (
            LAST_READING_GAS
            if meter_id == "d81a652fe0824f9a9d336016587d3b9d"
            else LAST_READING
        )

    def set_thrown_exception(self, exception: Exception) -> None:
        """Set thrown exception for testing purposes."""
        self._thrown_error = exception
