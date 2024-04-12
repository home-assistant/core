"""Configure and test MatrixBot."""

from homeassistant.components.matrix import (
    DOMAIN as MATRIX_DOMAIN,
    SERVICE_SEND_MESSAGE,
    MatrixBot,
)
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import TEST_NOTIFIER_NAME


async def test_services(hass: HomeAssistant, matrix_bot: MatrixBot):
    """Test hass/MatrixBot state."""

    services = hass.services.async_services()

    # Verify that the matrix service is registered
    matrix_service = services.get(MATRIX_DOMAIN)
    assert matrix_service
    assert SERVICE_SEND_MESSAGE in matrix_service

    # Verify that the matrix notifier is registered
    notify_service = services.get(NOTIFY_DOMAIN)
    assert notify_service
    assert TEST_NOTIFIER_NAME in notify_service
