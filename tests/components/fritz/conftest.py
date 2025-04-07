"""Common stuff for Fritz!Tools tests."""

import logging
from unittest.mock import MagicMock, patch

from fritzconnection.core.processor import Service
from fritzconnection.lib.fritzhosts import FritzHosts
import pytest

from .const import (
    MOCK_FB_SERVICES,
    MOCK_HOST_ATTRIBUTES_DATA,
    MOCK_MESH_DATA,
    MOCK_MODELNAME,
)

LOGGER = logging.getLogger(__name__)


class FritzServiceMock(Service):
    """Service mocking."""

    def __init__(self, serviceId: str, actions: dict) -> None:
        """Init Service mock."""
        super().__init__()
        self._actions = actions
        self.serviceId = serviceId


class FritzConnectionMock:
    """FritzConnection mocking."""

    def __init__(self, services) -> None:
        """Init Mocking class."""
        self.modelname = MOCK_MODELNAME
        self.call_action = self._call_action
        self._services = services
        self.services = {
            srv: FritzServiceMock(serviceId=srv, actions=actions)
            for srv, actions in services.items()
        }
        LOGGER.debug("-" * 80)
        LOGGER.debug("FritzConnectionMock - services: %s", self.services)

    def call_action_side_effect(self, side_effect=None) -> None:
        """Set or unset a side_effect for call_action."""
        if side_effect is not None:
            self.call_action = MagicMock(side_effect=side_effect)
        else:
            self.call_action = self._call_action

    def override_services(self, services) -> None:
        """Overrire services data."""
        self._services = services

    def _call_action(self, service: str, action: str, **kwargs):
        LOGGER.debug(
            "_call_action service: %s, action: %s, **kwargs: %s",
            service,
            action,
            {**kwargs},
        )
        if ":" in service:
            service, number = service.split(":", 1)
            service = service + number
        elif not service[-1].isnumeric():
            service = service + "1"

        if kwargs:
            if (index := kwargs.get("NewIndex")) is None:
                index = next(iter(kwargs.values()))

            return self._services[service][action][index]
        return self._services[service][action]


@pytest.fixture(name="fc_data")
def fc_data_mock():
    """Fixture for default fc_data."""
    return MOCK_FB_SERVICES


@pytest.fixture
def fc_class_mock(fc_data):
    """Fixture that sets up a mocked FritzConnection class."""
    with patch(
        "homeassistant.components.fritz.coordinator.FritzConnection", autospec=True
    ) as result:
        result.return_value = FritzConnectionMock(fc_data)
        yield result


@pytest.fixture
def fh_class_mock():
    """Fixture that sets up a mocked FritzHosts class."""
    with patch(
        "homeassistant.components.fritz.coordinator.FritzHosts",
        new=FritzHosts,
    ) as result:
        result.get_mesh_topology = MagicMock(return_value=MOCK_MESH_DATA)
        result.get_hosts_attributes = MagicMock(return_value=MOCK_HOST_ATTRIBUTES_DATA)
        yield result
