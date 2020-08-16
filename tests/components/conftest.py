"""Fixtures for component testing."""
import pytest

from homeassistant.components import zeroconf

from tests.async_mock import patch

zeroconf.orig_install_multiple_zeroconf_catcher = (
    zeroconf.install_multiple_zeroconf_catcher
)
zeroconf.install_multiple_zeroconf_catcher = lambda zc: None


@pytest.fixture(autouse=True)
def prevent_io():
    """Fixture to prevent certain I/O from happening."""
    with patch(
        "homeassistant.components.http.ban.async_load_ip_bans_config", return_value=[],
    ):
        yield
