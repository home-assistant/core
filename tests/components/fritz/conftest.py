"""Common stuff for AVM Fritz!Box tests."""
from unittest.mock import patch

import pytest

from . import FritzConnectionMock


@pytest.fixture()
def fc_class_mock():
    """Fixture that sets up a mocked FritzConnection class."""
    with patch("fritzconnection.FritzConnection", autospec=True) as result:
        result.return_value = FritzConnectionMock()
        yield result
