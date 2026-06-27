"""Test the Tesla Fleet services."""

from unittest.mock import patch

import pytest

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.services import (
    ATTR_TOU_SETTINGS,
    SERVICE_TIME_OF_USE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_platform
from .const import COMMAND_ERROR, RESPONSE_OK

from tests.common import MockConfigEntry


async def test_time_of_use(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the time_of_use service call against an energy site device."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get("sensor.energy_site_grid_power").device_id

    # Service is registered after setup.
    assert hass.services.has_service(DOMAIN, SERVICE_TIME_OF_USE)

    # Successful call — payload passed through verbatim.
    with patch(
        "tesla_fleet_api.tesla.EnergySite.time_of_use_settings",
        return_value=RESPONSE_OK,
    ) as set_time_of_use:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                ATTR_TOU_SETTINGS: {"utility": "test"},
            },
            blocking=True,
        )
        set_time_of_use.assert_called_once_with({"utility": "test"})

    # tariff_content_v2 wrapper is stripped before the call.
    with patch(
        "tesla_fleet_api.tesla.EnergySite.time_of_use_settings",
        return_value=RESPONSE_OK,
    ) as set_time_of_use:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                ATTR_TOU_SETTINGS: {
                    "tariff_content_v2": {"utility": "test"},
                },
            },
            blocking=True,
        )
        set_time_of_use.assert_called_once_with({"utility": "test"})

    # Tesla API returns an error response — the service raises HomeAssistantError.
    with (
        patch(
            "tesla_fleet_api.tesla.EnergySite.time_of_use_settings",
            return_value=COMMAND_ERROR,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                ATTR_TOU_SETTINGS: {},
            },
            blocking=True,
        )


async def test_time_of_use_invalid_device(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test that an unknown device_id raises ServiceValidationError."""
    await setup_platform(hass, normal_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: "not-a-real-device",
                ATTR_TOU_SETTINGS: {},
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "invalid_device"


async def test_time_of_use_entry_not_loaded(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test calling the service after the config entry is unloaded."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get("sensor.energy_site_grid_power").device_id

    assert await hass.config_entries.async_unload(normal_config_entry.entry_id)
    await hass.async_block_till_done()
    assert normal_config_entry.state is ConfigEntryState.NOT_LOADED

    # Service stays registered at domain level, but the entry is gone.
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                ATTR_TOU_SETTINGS: {},
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "entry_not_loaded"


async def test_time_of_use_missing_scope(
    hass: HomeAssistant,
    readonly_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the service rejects an entry without the energy commands scope."""
    await setup_platform(hass, readonly_config_entry)

    energy_device = entity_registry.async_get("sensor.energy_site_grid_power").device_id

    with (
        patch(
            "tesla_fleet_api.tesla.EnergySite.time_of_use_settings"
        ) as set_time_of_use,
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                ATTR_TOU_SETTINGS: {},
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "missing_scope_energy_cmds"
    set_time_of_use.assert_not_called()
