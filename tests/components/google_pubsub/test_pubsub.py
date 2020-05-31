"""The tests for the Google Pub/Sub component."""
from datetime import datetime

from homeassistant.components.google_pubsub import DateTimeJSONEncoder as victim


class TestDateTimeJSONEncoder:
    """Bundle for DateTimeJSONEncoder tests."""

    def test_datetime(self):
        """Test datetime encoding."""
        time = datetime(2019, 1, 13, 12, 30, 5)
        assert victim().encode(time) == '"2019-01-13T12:30:05"'

    def test_no_datetime(self):
        """Test integer encoding."""
        assert victim().encode(42) == "42"

    def test_nested(self):
        """Test dictionary encoding."""
        assert victim().encode({"foo": "bar"}) == '{"foo": "bar"}'
