from datetime import datetime

from homeassistant.components.google_pubsub import (
    DateTimeJSONEncoder as victim)


class TestDateTimeJSONEncoder(object):

    def test_datetime(self):
        time = datetime(2019, 1, 13, 12, 30, 5)
        assert victim().encode(time) == '"2019-01-13T12:30:05.000000"'

    def test_no_datetime(self):
        assert victim().encode(42) == '42'

    def test_nested(self):
        assert victim().encode({'foo': 'bar'}) == '{"foo": "bar"}'
