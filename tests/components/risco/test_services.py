"""Tests for the Risco services."""

from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.risco import DOMAIN
from homeassistant.components.risco.const import SERVICE_SET_TIME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_TIME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import TEST_CLOUD_CONFIG

from tests.common import MockConfigEntry


async def test_set_time_service(
    hass: HomeAssistant, setup_risco_local, local_config_entry
) -> None:
    """Test the set_time service."""
    with patch("homeassistant.components.risco.RiscoLocal.set_time") as mock:
        time_str = "2025-02-21T12:00:00"
        time = datetime.fromisoformat(time_str)
        data = {
            ATTR_CONFIG_ENTRY_ID: local_config_entry.entry_id,
            ATTR_TIME: time_str,
        }

        await hass.services.async_call(
            DOMAIN, SERVICE_SET_TIME, service_data=data, blocking=True
        )

        mock.assert_called_once_with(time)


@pytest.mark.freeze_time("2025-02-21T12:00:00Z")
async def test_set_time_service_with_no_time(
    hass: HomeAssistant, setup_risco_local, local_config_entry
) -> None:
    """Test the set_time service when no time is provided."""
    with patch("homeassistant.components.risco.RiscoLocal.set_time") as mock_set_time:
        data = {
            "config_entry_id": local_config_entry.entry_id,
        }

        await hass.services.async_call(
            DOMAIN, SERVICE_SET_TIME, service_data=data, blocking=True
        )

        mock_set_time.assert_called_once_with(datetime.now())


async def test_set_time_service_with_invalid_entry(
    hass: HomeAssistant, setup_risco_local
) -> None:
    """Test the set_time service with an invalid config entry."""
    data = {
        ATTR_CONFIG_ENTRY_ID: "invalid_entry_id",
    }

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_TIME, service_data=data, blocking=True
        )
    assert err.value.translation_key == "service_config_entry_not_found"


async def test_set_time_service_with_not_loaded_entry(
    hass: HomeAssistant, setup_risco_local, local_config_entry
) -> None:
    """Test the set_time service with a config entry that is not loaded."""
    await hass.config_entries.async_unload(local_config_entry.entry_id)
    await hass.async_block_till_done()

    assert local_config_entry.state is ConfigEntryState.NOT_LOADED

    data = {
        ATTR_CONFIG_ENTRY_ID: local_config_entry.entry_id,
    }

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_TIME, service_data=data, blocking=True
        )
    assert err.value.translation_key == "service_config_entry_not_loaded"


async def test_set_time_service_with_cloud_entry(
    hass: HomeAssistant, setup_risco_local
) -> None:
    """Test the set_time service with a cloud config entry."""
    cloud_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-cloud",
        data=TEST_CLOUD_CONFIG,
    )
    cloud_entry.add_to_hass(hass)
    cloud_entry.mock_state(hass, ConfigEntryState.LOADED)

    data = {
        ATTR_CONFIG_ENTRY_ID: cloud_entry.entry_id,
    }

    with pytest.raises(
        ServiceValidationError, match="This service only works with local"
    ):
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_TIME, service_data=data, blocking=True
        )
