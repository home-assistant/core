"""Test config."""

import asyncio
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from .test_common import get_default_config


async def test_enable_proactive_mode_in_parallel(hass: HomeAssistant) -> None:
    """Test enabling proactive mode does not happen in parallel."""
    config = get_default_config(hass)

    with patch(
        "homeassistant.components.alexa.config.async_enable_proactive_mode"
    ) as mock_enable_proactive_mode:
        await asyncio.gather(
            config.async_enable_proactive_mode(), config.async_enable_proactive_mode()
        )

    mock_enable_proactive_mode.assert_awaited_once()


async def test_disable_proactive_mode_invokes_unsubscribe(hass: HomeAssistant) -> None:
    """Calling async_disable_proactive_mode should execute the stored unsubscribe."""
    config = get_default_config(hass)

    called = {"n": 0}

    def _unsub():
        called["n"] += 1

    # Simulate proactive mode previously enabled
    config._unsub_proactive_report = _unsub  # attribute already used in the module

    await config.async_disable_proactive_mode()

    assert called["n"] == 1
