"""Global fixtures for custom integration."""

import pytest
import pytest_socket


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield


def enable_external_sockets():
    pytest_socket.enable_socket()
