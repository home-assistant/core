"""Tests for the Hisense AEH-W4A1 init file."""

from unittest.mock import patch

from pyaehw4a1 import exceptions

from homeassistant.components import hinen
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_configuring_hinen_not_creates_entry_for_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test that specifying config will not create an entry."""
    with (
        patch(
            "homeassistant.components.hinen.config_flow.AehW4a1.check",
            side_effect=exceptions.ConnectionError,
        ),
        patch(
            "homeassistant.components.hinen.async_setup_entry",
            return_value=True,
        ) as mock_setup,
    ):
        await async_setup_component(
            hass,
            hinen.DOMAIN,
            {"hinen": {"ip_address": ["1.2.3.4"]}},
        )
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0
