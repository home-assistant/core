"""Configure py.test."""
from asynctest import patch
import pytest

from .const import UNIQUE_ID


@pytest.fixture(name="vizio_connect", autouse=False)
def vizio_connect_fixture():
    """Mock valid vizio device and entry setup."""
    with patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.validate_ha_config",
        return_value=True,
    ), patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.get_unique_id",
        return_value=UNIQUE_ID,
    ):
        yield


@pytest.fixture(name="vizio_bypass_setup", autouse=False)
def vizio_bypass_setup_fixture():
    """Mock component setup."""
    with patch("homeassistant.components.vizio.async_setup_entry", return_value=True):
        yield


@pytest.fixture(name="vizio_bypass_update", autouse=False)
def vizio_bypass_update_fixture():
    """Mock component update."""
    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.can_connect",
        return_value=True,
    ), patch("homeassistant.components.vizio.media_player.VizioDevice.async_update"):
        yield


@pytest.fixture(name="vizio_guess_device_type", autouse=False)
def vizio_guess_device_type_fixture():
    """Mock vizio async_guess_device_type function."""
    with patch(
        "homeassistant.components.vizio.config_flow.async_guess_device_type",
        return_value="speaker",
    ):
        yield


@pytest.fixture(name="vizio_cant_connect", autouse=False)
def vizio_cant_connect_fixture():
    """Mock vizio device cant connect."""
    with patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.validate_ha_config",
        return_value=False,
    ):
        yield
