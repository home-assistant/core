"""Test config."""

import asyncio
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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


async def test_smart_home_entity_config_expose_power_controller(
    hass: HomeAssistant,
) -> None:
    """Test standalone Alexa config accepts expose_power_controller."""
    assert await async_setup_component(
        hass,
        "alexa",
        {
            "alexa": {
                "smart_home": {
                    "entity_config": {
                        "climate.test": {"expose_power_controller": False}
                    }
                }
            }
        },
    )
