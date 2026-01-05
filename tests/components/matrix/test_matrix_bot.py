"""Configure and test MatrixBot."""

from homeassistant.components.matrix import MatrixBot
from homeassistant.components.matrix.const import (
    DOMAIN,
    SERVICE_REACT,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import TEST_NOTIFIER_NAME


async def test_services(hass: HomeAssistant, matrix_bot: MatrixBot) -> None:
    """Test hass/MatrixBot state."""

    services = hass.services.async_services()

    # Verify that the matrix service is registered
    assert (matrix_service := services.get(DOMAIN))
    assert SERVICE_SEND_MESSAGE in matrix_service
    assert SERVICE_REACT in matrix_service

    # Verify that the matrix notifier is registered
    assert (notify_service := services.get(NOTIFY_DOMAIN))
    assert TEST_NOTIFIER_NAME in notify_service
