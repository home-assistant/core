"""Notify tests for the Google Mail integration."""

from unittest.mock import patch

import pytest
from voluptuous.error import Invalid

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import BUILD, ComponentSetup


async def test_notify(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test service call draft email."""
    await setup_integration()

    with patch(BUILD) as mock_client:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "example_gmail_com",
            {
                "title": "Test",
                "message": "test email",
                "target": "text@example.com",
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 5

    with patch(BUILD) as mock_client:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "example_gmail_com",
            {
                "title": "Test",
                "message": "test email",
                "target": "text@example.com",
                "data": {"send": False},
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 5


async def test_notify_voluptuous_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test voluptuous error thrown when drafting email."""
    await setup_integration()

    with pytest.raises(ValueError) as ex:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "example_gmail_com",
            {
                "title": "Test",
                "message": "test email",
            },
            blocking=True,
        )
    assert ex.match("recipient address required")

    with pytest.raises(Invalid) as ex:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "example_gmail_com",
            {
                "title": "Test",
            },
            blocking=True,
        )
    assert ex.getrepr("required key not provided")
