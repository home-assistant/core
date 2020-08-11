"""conftest for zeroconf."""
import pytest

from homeassistant.components import zeroconf

from tests.async_mock import patch

zeroconf.orig_install_multiple_zeroconf_catcher = (
    zeroconf.install_multiple_zeroconf_catcher
)
zeroconf.install_multiple_zeroconf_catcher = lambda zc: None


@pytest.fixture
def mock_zeroconf():
    """Mock zeroconf."""
    with patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc:
        yield mock_zc.return_value
