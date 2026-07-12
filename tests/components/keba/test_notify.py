"""Tests for the KEBA charging station notify platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant

NOTIFY_ENTITY_ID = "notify.kc_p30_display"


@pytest.mark.usefixtures("init_integration")
async def test_notify_entity_created(hass: HomeAssistant) -> None:
    """Test that the notify entity is created."""
    assert hass.states.get(NOTIFY_ENTITY_ID) is not None


@pytest.mark.usefixtures("init_integration")
async def test_notify_send_message(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test that sending a message calls set_text with spaces replaced by $."""
    await hass.services.async_call(
        "notify",
        "send_message",
        {"entity_id": NOTIFY_ENTITY_ID, "message": "hello world"},
        blocking=True,
    )
    mock_keba.set_text.assert_called_once_with("hello$world", 2.0, 10.0)
