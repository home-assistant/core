"""Test the Tessie services."""

from unittest.mock import patch

import pytest
from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.components.tessie.const import DOMAIN
from homeassistant.components.tessie.models import TessieData
from homeassistant.components.tessie.services import (
    ATTR_DEPARTURE_TIME,
    ATTR_ENABLE,
    ATTR_END_OFF_PEAK_TIME,
    ATTR_OFF_PEAK_CHARGING_ENABLED,
    ATTR_OFF_PEAK_CHARGING_WEEKDAYS,
    ATTR_PRECONDITIONING_ENABLED,
    ATTR_PRECONDITIONING_WEEKDAYS,
    ATTR_TIME,
    SERVICE_SET_SCHEDULED_CHARGING,
    SERVICE_SET_SCHEDULED_DEPARTURE,
)
from homeassistant.const import CONF_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import TEST_RESPONSE, setup_platform

TEST_RESPONSE_ERROR = {"result": False, "reason": "reason_why"}


async def test_set_scheduled_charging_enable_with_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test enabling scheduled charging with a time."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with patch(
        "homeassistant.components.tessie.services.set_scheduled_charging",
        return_value=TEST_RESPONSE,
    ) as mock_call:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_TIME: "10:00",
            },
            blocking=True,
        )
        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs["timeMins"] == 600
        assert call_kwargs.kwargs["enable"] is True


async def test_set_scheduled_charging_disable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling scheduled charging without a time."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with patch(
        "homeassistant.components.tessie.services.set_scheduled_charging",
        return_value=TEST_RESPONSE,
    ) as mock_call:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: False,
            },
            blocking=True,
        )
        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs["timeMins"] == 0
        assert call_kwargs.kwargs["enable"] is False


async def test_set_scheduled_charging_enable_without_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test enabling scheduled charging without a time raises error."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
            },
            blocking=True,
        )


async def test_set_scheduled_charging_command_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test scheduled charging command failure raises error."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with (
        patch(
            "homeassistant.components.tessie.services.set_scheduled_charging",
            return_value=TEST_RESPONSE_ERROR,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_TIME: "10:00",
            },
            blocking=True,
        )


async def test_set_scheduled_charging_invalid_device(
    hass: HomeAssistant,
) -> None:
    """Test scheduled charging with invalid device raises error."""
    await setup_platform(hass, [Platform.SENSOR])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: "invalid_device_id",
                ATTR_ENABLE: True,
                ATTR_TIME: "10:00",
            },
            blocking=True,
        )


async def test_set_scheduled_charging_tesla_fleet_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test scheduled charging API error raises HomeAssistantError."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with (
        patch(
            "homeassistant.components.tessie.services.set_scheduled_charging",
            side_effect=TeslaFleetError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_TIME: "10:00",
            },
            blocking=True,
        )


async def test_set_scheduled_charging_vehicle_not_in_runtime_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test scheduled charging with a missing vehicle in runtime data."""
    mock_entry = await setup_platform(hass, [Platform.SENSOR])

    assert (config_entry := hass.config_entries.async_get_entry(mock_entry.entry_id))
    runtime_data = config_entry.runtime_data
    config_entry.runtime_data = TessieData([], runtime_data.energysites)

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_TIME: "10:00",
            },
            blocking=True,
        )


async def test_set_scheduled_departure_full_params(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test scheduled departure with all parameters."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with patch(
        "homeassistant.components.tessie.services.set_scheduled_departure",
        return_value=TEST_RESPONSE,
    ) as mock_call:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_PRECONDITIONING_ENABLED: True,
                ATTR_PRECONDITIONING_WEEKDAYS: False,
                ATTR_DEPARTURE_TIME: "07:30",
                ATTR_OFF_PEAK_CHARGING_ENABLED: True,
                ATTR_OFF_PEAK_CHARGING_WEEKDAYS: False,
                ATTR_END_OFF_PEAK_TIME: "06:00",
            },
            blocking=True,
        )
        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs["departure_time_mins"] == 450
        assert call_kwargs.kwargs["end_off_peak_time_mins"] == 360
        assert call_kwargs.kwargs["enable"] is True
        assert call_kwargs.kwargs["preconditioning_enabled"] is True
        assert call_kwargs.kwargs["off_peak_charging_enabled"] is True


async def test_set_scheduled_departure_disable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling scheduled departure."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with patch(
        "homeassistant.components.tessie.services.set_scheduled_departure",
        return_value=TEST_RESPONSE,
    ) as mock_call:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: False,
            },
            blocking=True,
        )
        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs["enable"] is False
        assert call_kwargs.kwargs["departure_time_mins"] == 0
        assert call_kwargs.kwargs["end_off_peak_time_mins"] == 0


async def test_set_scheduled_departure_vehicle_not_in_runtime_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test scheduled departure with a missing vehicle in runtime data."""
    mock_entry = await setup_platform(hass, [Platform.SENSOR])

    assert (config_entry := hass.config_entries.async_get_entry(mock_entry.entry_id))
    runtime_data = config_entry.runtime_data
    config_entry.runtime_data = TessieData([], runtime_data.energysites)

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: False,
            },
            blocking=True,
        )


async def test_set_scheduled_departure_preconditioning_without_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test preconditioning without departure time raises error."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_PRECONDITIONING_ENABLED: True,
            },
            blocking=True,
        )


async def test_set_scheduled_departure_off_peak_without_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test off-peak charging without end time raises error."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_OFF_PEAK_CHARGING_ENABLED: True,
            },
            blocking=True,
        )


async def test_set_scheduled_departure_command_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test scheduled departure command failure raises error."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with (
        patch(
            "homeassistant.components.tessie.services.set_scheduled_departure",
            return_value=TEST_RESPONSE_ERROR,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: False,
            },
            blocking=True,
        )


async def test_set_scheduled_departure_invalid_device(
    hass: HomeAssistant,
) -> None:
    """Test scheduled departure with invalid device raises error."""
    await setup_platform(hass, [Platform.SENSOR])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: "invalid_device_id",
                ATTR_ENABLE: False,
            },
            blocking=True,
        )


async def test_set_scheduled_departure_tesla_fleet_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test scheduled departure API error raises HomeAssistantError."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    with (
        patch(
            "homeassistant.components.tessie.services.set_scheduled_departure",
            side_effect=TeslaFleetError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: False,
            },
            blocking=True,
        )
