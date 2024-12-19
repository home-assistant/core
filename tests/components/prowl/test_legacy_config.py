"""Test the legacy services.yaml configuration."""

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_legacy_config(
    hass: HomeAssistant,
    configure_prowl_through_yaml,
) -> None:
    """Test sending a notification message via Prowl."""
    # Assert that Notifications got loaded successfully.
    assert hass.services.has_service(NOTIFY_DOMAIN, NOTIFY_DOMAIN)
