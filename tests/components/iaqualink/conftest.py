"""Configuration for iAqualink tests."""

import random
from unittest.mock import AsyncMock, PropertyMock, patch

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkDevice
from iaqualink.system import AqualinkSystem
import pytest

from homeassistant.components.iaqualink import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_USERNAME = "test@example.com"
MOCK_PASSWORD = "password"
MOCK_DATA = {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD}


def async_returns(x):
    """Return value-returning async mock."""
    return AsyncMock(return_value=x)


def async_raises(x):
    """Return exception-raising async mock."""
    return AsyncMock(side_effect=x)


@pytest.fixture(name="client")
def client_fixture():
    """Create client fixture."""
    return AqualinkClient(username=MOCK_USERNAME, password=MOCK_PASSWORD)


def get_aqualink_system(aqualink, cls=None, data=None):
    """Create aqualink system."""
    if cls is None:
        cls = AqualinkSystem

    if data is None:
        data = {}

    num = random.randint(0, 99999)
    data["serial_number"] = f"SN{num:05}"

    return cls(aqualink=aqualink, data=data)


def get_aqualink_device(system, name, cls=None, data=None):
    """Create aqualink device."""
    if cls is None:
        cls = AqualinkDevice

        # AqualinkDevice doesn't implement some of the properties since it's left to
        # sub-classes for them to do. Provide a basic implementation here for the
        # benefits of the test suite.
        attrs = {
            "name": name,
            "manufacturer": "Jandy",
            "model": "Device",
            "label": name.upper(),
        }

        for k, v in attrs.items():
            patcher = patch.object(cls, k, new_callable=PropertyMock)
            mock = patcher.start()
            mock.return_value = v

    if data is None:
        data = {}

    data["name"] = name

    return cls(system=system, data=data)


@pytest.fixture(name="config_data")
def config_data_fixture():
    """Create hass config fixture."""
    return MOCK_DATA


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: MOCK_DATA}


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
    )
