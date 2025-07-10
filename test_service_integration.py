#!/usr/bin/env python3
"""Simple test script to verify NS integration services are registered."""

import asyncio
import logging
import tempfile

from homeassistant.components.nederlandse_spoorwegen import (
    DOMAIN as NEDERLANDSE_SPOORWEGEN_DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

_LOGGER = logging.getLogger(__name__)


async def test_services():
    """Test that NS services are properly registered."""

    # Create a temporary directory for config
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = temp_dir

        # Initialize Home Assistant
        hass = HomeAssistant(config_dir)
        hass.config.config_dir = config_dir

        try:
            # Setup the NS component
            result = await async_setup_component(
                hass, NEDERLANDSE_SPOORWEGEN_DOMAIN, {}
            )

            if result:
                # Check if services are registered
                if hass.services.has_service(
                    NEDERLANDSE_SPOORWEGEN_DOMAIN, "add_route"
                ):
                    _LOGGER.info("Add_route service is registered")
                else:
                    _LOGGER.warning("Add_route service is NOT registered")

                if hass.services.has_service(
                    NEDERLANDSE_SPOORWEGEN_DOMAIN, "remove_route"
                ):
                    _LOGGER.info("Remove_route service is registered")
                else:
                    _LOGGER.warning("Remove_route service is NOT registered")

                # List all NS services
                services = hass.services.async_services().get(
                    NEDERLANDSE_SPOORWEGEN_DOMAIN, {}
                )

                _LOGGER.info("Available NS services: %s", list(services.keys()))

            else:
                _LOGGER.error("Nederlandse Spoorwegen component setup failed")

        finally:
            await hass.async_stop()


if __name__ == "__main__":
    asyncio.run(test_services())
