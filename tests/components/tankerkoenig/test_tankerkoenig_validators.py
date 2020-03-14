"""The tests for the custom tankerkoenig validators."""
import unittest
import uuid

import pytest
import voluptuous as vol

from homeassistant.components.tankerkoenig import uuid4_string


class TestUUID4StringValidator(unittest.TestCase):
    """Test the UUID4 string custom validator."""

    def test_uuid4_string(caplog):
        """Test string uuid validation."""
        schema = vol.Schema(uuid4_string)

        for value in ["Not a hex string", "0", 0]:
            with pytest.raises(vol.Invalid):
                schema(value)

        with pytest.raises(vol.Invalid):
            # the third block should start with 4
            schema("a03d31b2-2eee-2acc-bb90-eec40be6ed23")

        with pytest.raises(vol.Invalid):
            # the fourth block should start with 8-a
            schema("a03d31b2-2eee-4acc-1b90-eec40be6ed23")

        _str = str(uuid.uuid4())
        assert schema(_str) == _str
        assert schema(_str.upper()) == _str
