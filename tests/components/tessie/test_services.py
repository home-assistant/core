"""Test the Tessie services."""

from unittest.mock import patch

import pytest

from homeassistant.components.tessie.const import DOMAIN
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


async def test_set_scheduled_charging(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the set_scheduled_charging service."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    # Test enable with time
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

    # Test disable (no time needed)
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

    # Test enable without time raises validation error
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

    # Test command failure response
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


async def test_set_scheduled_departure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the set_scheduled_departure service."""
    await setup_platform(hass, [Platform.SENSOR])

    vehicle_device = entity_registry.async_get("sensor.test_battery_level").device_id

    # Test full parameters
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

    # Test disable only
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

    # Test preconditioning enabled without departure_time raises error
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

    # Test off_peak enabled without end_off_peak_time raises error
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

    # Test command failure response
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
