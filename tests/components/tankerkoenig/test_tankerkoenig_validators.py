"""The tests for the custom tankerkoenig validators."""
import unittest
import uuid

import pytest
import voluptuous as vol

from homeassistant.components.tankerkoenig import uuid_string


class TestUUIDStringValidator(unittest.TestCase):
    """Test the UUID string custom validator."""

    def test_uuid_string(caplog):
        """Test string uuid validation."""
        schema = vol.Schema(uuid_string)

        for value in ["Not a hex string", "0", 0]:
            with pytest.raises(vol.Invalid):
                schema(value)

        _str = str(uuid.uuid())
        assert schema(_str) == _str
        assert schema(_str.upper()) == _str
