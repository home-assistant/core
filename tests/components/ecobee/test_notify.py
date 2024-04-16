"""Test Ecobee notify service."""

from unittest.mock import MagicMock

from homeassistant.components.ecobee import DOMAIN
from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.core import HomeAssistant

from .common import setup_platform

THERMOSTAT_ID = 0


async def test_notify_entity_service(
    hass: HomeAssistant,
    mock_ecobee: MagicMock,
) -> None:
    """Test the notify entity service."""
    await setup_platform(hass, NOTIFY_DOMAIN)

    entity_id = "notify.ecobee"
    state = hass.states.get("notify.ecobee")
    assert state is not None
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        service_data={"entity_id": entity_id, "message": "It is too cold!"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_ecobee.send_message.assert_called_with(THERMOSTAT_ID, "It is too cold!")


async def test_legacy_notify_service(
    hass: HomeAssistant,
    mock_ecobee: MagicMock,
) -> None:
    """Test the legacy notify service."""
    await setup_platform(hass, NOTIFY_DOMAIN)

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        service_data={"message": "It is too cold!", "target": THERMOSTAT_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_ecobee.send_message.assert_called_with(THERMOSTAT_ID, "It is too cold!")
    mock_ecobee.send_message.reset_mock()
