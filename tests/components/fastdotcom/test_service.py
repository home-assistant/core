"""Test Fastdotcom service."""

from unittest.mock import patch

import pytest

from homeassistant.components.fastdotcom.const import DEFAULT_NAME, DOMAIN, SERVICE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_service(hass: HomeAssistant) -> None:
    """Test the Fastdotcom service."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com", return_value=0
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "0"

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com", return_value=5.0
    ):
        await hass.services.async_call(DOMAIN, SERVICE_NAME, blocking=True)

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "5.0"


async def test_service_unloaded_entry(hass: HomeAssistant) -> None:
    """Test service called when config entry unloaded."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com", return_value=0
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry
    await config_entry.async_unload(hass)

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(DOMAIN, SERVICE_NAME, blocking=True)

    assert "Fast.com is not loaded" in str(exc)


async def test_service_removed_entry(hass: HomeAssistant) -> None:
    """Test service called when config entry was removed and HA was not restarted yet."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com", return_value=0
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry
    await hass.config_entries.async_remove(config_entry.entry_id)

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(DOMAIN, SERVICE_NAME, blocking=True)

    assert "No Fast.com config entries found" in str(exc)
