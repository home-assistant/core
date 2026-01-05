"""Test the Teslemetry services."""

from datetime import time
from unittest.mock import patch

import pytest

from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.components.teslemetry.services import (
    ATTR_DAYS_OF_WEEK,
    ATTR_DEPARTURE_TIME,
    ATTR_ENABLE,
    ATTR_END_OFF_PEAK_TIME,
    ATTR_END_TIME,
    ATTR_GPS,
    ATTR_ID,
    ATTR_LOCATION,
    ATTR_NAME,
    ATTR_OFF_PEAK_CHARGING_ENABLED,
    ATTR_OFF_PEAK_CHARGING_WEEKDAYS,
    ATTR_ONE_TIME,
    ATTR_PIN,
    ATTR_PRECONDITION_TIME,
    ATTR_PRECONDITIONING_ENABLED,
    ATTR_PRECONDITIONING_WEEKDAYS,
    ATTR_START_TIME,
    ATTR_TIME,
    ATTR_TOU_SETTINGS,
    SERVICE_ADD_CHARGE_SCHEDULE,
    SERVICE_ADD_PRECONDITION_SCHEDULE,
    SERVICE_NAVIGATE_ATTR_GPS_REQUEST,
    SERVICE_REMOVE_CHARGE_SCHEDULE,
    SERVICE_REMOVE_PRECONDITION_SCHEDULE,
    SERVICE_SET_SCHEDULED_CHARGING,
    SERVICE_SET_SCHEDULED_DEPARTURE,
    SERVICE_SPEED_LIMIT,
    SERVICE_TIME_OF_USE,
    SERVICE_VALET_MODE,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_platform
from .const import COMMAND_ERROR, COMMAND_OK

lat = -27.9699373
lon = 153.3726526


async def test_services(
    hass: HomeAssistant,
) -> None:
    """Tests that the custom services are correct."""

    await setup_platform(hass)
    entity_registry = er.async_get(hass)

    # Get a vehicle device ID
    vehicle_device = entity_registry.async_get("sensor.test_charging").device_id
    energy_device = entity_registry.async_get(
        "sensor.energy_site_battery_power"
    ).device_id

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.navigation_gps_request",
        return_value=COMMAND_OK,
    ) as navigation_gps_request:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_ATTR_GPS_REQUEST,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_GPS: {CONF_LATITUDE: lat, CONF_LONGITUDE: lon},
            },
            blocking=True,
        )
        navigation_gps_request.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.set_scheduled_charging",
        return_value=COMMAND_OK,
    ) as set_scheduled_charging:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_TIME: "06:00",  # 6:00 AM
            },
            blocking=True,
        )
        set_scheduled_charging.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.set_scheduled_departure",
        return_value=COMMAND_OK,
    ) as set_scheduled_departure:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_PRECONDITIONING_ENABLED: True,
                ATTR_PRECONDITIONING_WEEKDAYS: False,
                ATTR_DEPARTURE_TIME: "06:00",  # 6:00 AM
                ATTR_OFF_PEAK_CHARGING_ENABLED: True,
                ATTR_OFF_PEAK_CHARGING_WEEKDAYS: False,
                ATTR_END_OFF_PEAK_TIME: "05:00",  # 5:00 AM
            },
            blocking=True,
        )
        set_scheduled_departure.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.set_valet_mode",
        return_value=COMMAND_OK,
    ) as set_valet_mode:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_VALET_MODE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_PIN: 1234,
            },
            blocking=True,
        )
        set_valet_mode.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.speed_limit_activate",
        return_value=COMMAND_OK,
    ) as speed_limit_activate:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SPEED_LIMIT,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
                ATTR_PIN: 1234,
            },
            blocking=True,
        )
        speed_limit_activate.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.speed_limit_deactivate",
        return_value=COMMAND_OK,
    ) as speed_limit_deactivate:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SPEED_LIMIT,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: False,
                ATTR_PIN: 1234,
            },
            blocking=True,
        )
        speed_limit_deactivate.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.EnergySite.time_of_use_settings",
        return_value=COMMAND_OK,
    ) as set_time_of_use:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                ATTR_TOU_SETTINGS: {},
            },
            blocking=True,
        )
        set_time_of_use.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.add_charge_schedule",
        return_value=COMMAND_OK,
    ) as add_charge_schedule:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CHARGE_SCHEDULE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_DAYS_OF_WEEK: ["Monday", "Tuesday"],
                ATTR_ENABLE: True,
                ATTR_LOCATION: {CONF_LATITUDE: lat, CONF_LONGITUDE: lon},
                ATTR_START_TIME: time(7, 0, 0),  # 7:00 AM
                ATTR_END_TIME: time(18, 0, 0),  # 6:00 PM
                ATTR_ONE_TIME: False,
                ATTR_NAME: "Test Schedule",
            },
            blocking=True,
        )
        add_charge_schedule.assert_called_once()

    # Test add_charge_schedule with minimal required parameters
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.add_charge_schedule",
        return_value=COMMAND_OK,
    ) as add_charge_schedule_minimal:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CHARGE_SCHEDULE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_DAYS_OF_WEEK: ["Monday", "Tuesday"],
                ATTR_ENABLE: True,
            },
            blocking=True,
        )
        add_charge_schedule_minimal.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.remove_charge_schedule",
        return_value=COMMAND_OK,
    ) as remove_charge_schedule:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_CHARGE_SCHEDULE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ID: 123,
            },
            blocking=True,
        )
        remove_charge_schedule.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.add_precondition_schedule",
        return_value=COMMAND_OK,
    ) as add_precondition_schedule:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRECONDITION_SCHEDULE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_DAYS_OF_WEEK: ["Monday", "Tuesday"],
                ATTR_ENABLE: True,
                ATTR_LOCATION: {CONF_LATITUDE: lat, CONF_LONGITUDE: lon},
                ATTR_PRECONDITION_TIME: time(7, 0, 0),  # 7:00 AM
                ATTR_ONE_TIME: False,
                ATTR_NAME: "Test Precondition Schedule",
            },
            blocking=True,
        )
        add_precondition_schedule.assert_called_once()

    # Test add_precondition_schedule with minimal required parameters
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.add_precondition_schedule",
        return_value=COMMAND_OK,
    ) as add_precondition_schedule_minimal:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRECONDITION_SCHEDULE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_DAYS_OF_WEEK: ["Monday", "Tuesday"],
                ATTR_ENABLE: True,
                ATTR_PRECONDITION_TIME: time(8, 0, 0),  # 8:00 AM
            },
            blocking=True,
        )
        add_precondition_schedule_minimal.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.remove_precondition_schedule",
        return_value=COMMAND_OK,
    ) as remove_precondition_schedule:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_PRECONDITION_SCHEDULE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ID: 123,
            },
            blocking=True,
        )
        remove_precondition_schedule.assert_called_once()

    with (
        patch(
            "tesla_fleet_api.teslemetry.EnergySite.time_of_use_settings",
            return_value=COMMAND_ERROR,
        ) as set_time_of_use,
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


async def test_service_validation_errors(
    hass: HomeAssistant,
) -> None:
    """Tests that the custom services handle bad data."""

    await setup_platform(hass)

    # Bad device ID
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_ATTR_GPS_REQUEST,
            {
                CONF_DEVICE_ID: "nope",
                ATTR_GPS: {CONF_LATITUDE: lat, CONF_LONGITUDE: lon},
            },
            blocking=True,
        )
