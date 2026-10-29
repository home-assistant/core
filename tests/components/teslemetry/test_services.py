"""Test the Teslemetry services."""

from datetime import time
from unittest.mock import patch

from aiopowerwall import (
    PowerwallCommandError,
    PowerwallConnectionError,
    PowerwallError,
    PowerwallNotSupportedError,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.teslemetry.const import (
    CONF_SITE_ID,
    DOMAIN,
    SUBENTRY_TYPE_ENERGY_SITE,
)
from homeassistant.components.teslemetry.services import (
    ATTR_DAYS_OF_WEEK,
    ATTR_DEPARTURE_TIME,
    ATTR_DURATION,
    ATTR_ENABLE,
    ATTR_END_OFF_PEAK_TIME,
    ATTR_END_TIME,
    ATTR_GPS,
    ATTR_OFF_PEAK_CHARGING_ENABLED,
    ATTR_OFF_PEAK_CHARGING_WEEKDAYS,
    ATTR_ONE_TIME,
    ATTR_PIN,
    ATTR_POWER,
    ATTR_PRECONDITION_TIME,
    ATTR_PRECONDITIONING_ENABLED,
    ATTR_PRECONDITIONING_WEEKDAYS,
    ATTR_START_TIME,
    ATTR_TOU_SETTINGS,
    SERVICE_ADD_CHARGE_SCHEDULE,
    SERVICE_ADD_PRECONDITION_SCHEDULE,
    SERVICE_DISPATCH_BATTERY_POWER,
    SERVICE_NAVIGATE_ATTR_GPS_REQUEST,
    SERVICE_REMOVE_CHARGE_SCHEDULE,
    SERVICE_REMOVE_PRECONDITION_SCHEDULE,
    SERVICE_RESUME_BATTERY_OPERATION,
    SERVICE_SET_SCHEDULED_CHARGING,
    SERVICE_SET_SCHEDULED_DEPARTURE,
    SERVICE_SPEED_LIMIT,
    SERVICE_TIME_OF_USE,
    SERVICE_VALET_MODE,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import (
    ATTR_ID,
    ATTR_LOCATION,
    ATTR_NAME,
    ATTR_TIME,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import mock_config_entry, setup_platform
from .const import COMMAND_ERROR, COMMAND_OK

lat = -27.9699373
lon = 153.3726526

SITE_ID = 123456

# aiopowerwall's PowerwallClient parses the PEM at construction time, so tests
# that build one need a real (if undersized, for speed) RSA key rather than
# arbitrary bytes.
_TEST_RSA_KEY_PEM = rsa.generate_private_key(
    public_exponent=65537, key_size=1024
).private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)

LOCAL_BATTERY_SERVICES = [
    pytest.param(
        SERVICE_DISPATCH_BATTERY_POWER,
        {ATTR_POWER: -5000, ATTR_DURATION: 1800},
        "dispatch_battery_power",
        id="dispatch_battery_power",
    ),
    pytest.param(
        SERVICE_RESUME_BATTERY_OPERATION,
        {},
        "resume_battery_operation",
        id="resume_battery_operation",
    ),
]


PAIRED_SITE = ConfigSubentryData(
    subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
    unique_id=str(SITE_ID),
    title="Energy Site",
    data={
        CONF_SITE_ID: SITE_ID,
        CONF_HOST: "192.168.91.1",
        CONF_PASSWORD: "abcde",
    },
)


async def _setup_site(
    hass: HomeAssistant, subentries: list[ConfigSubentryData]
) -> MockConfigEntry:
    """Set up an entry whose energy site has the given local-control subentry."""
    entry = mock_config_entry()
    entry = MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=subentries,
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_services(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the custom services are correct."""

    await setup_platform(hass)

    # Get a vehicle device ID
    vehicle_device = entity_registry.async_get("sensor.test_charging").device_id
    energy_device = entity_registry.async_get(
        "sensor.energy_site_battery_power"
    ).device_id

    # Test set_scheduled_charging with enable=False (time should default to 0)
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.set_scheduled_charging",
        return_value=COMMAND_OK,
    ) as set_scheduled_charging_off:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: False,
            },
            blocking=True,
        )
        set_scheduled_charging_off.assert_called_once_with(enable=False, time=0)

    # Test set_scheduled_departure with enable=False (times should default to 0)
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.set_scheduled_departure",
        return_value=COMMAND_OK,
    ) as set_scheduled_departure_off:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: False,
            },
            blocking=True,
        )
        set_scheduled_departure_off.assert_called_once_with(
            False, False, False, 0, False, False, 0
        )

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
                ATTR_TOU_SETTINGS: {"utility": "test"},
            },
            blocking=True,
        )
        set_time_of_use.assert_called_once_with({"utility": "test"})

    # Test that tariff_content_v2 wrapper is unwrapped before passing to SDK
    with patch(
        "tesla_fleet_api.teslemetry.EnergySite.time_of_use_settings",
        return_value=COMMAND_OK,
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
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the custom services handle bad data."""

    await setup_platform(hass)
    vehicle_device = entity_registry.async_get("sensor.test_charging").device_id

    # Bad device ID - verify translation key is used
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_ATTR_GPS_REQUEST,
            {
                CONF_DEVICE_ID: "nope",
                ATTR_GPS: {CONF_LATITUDE: lat, CONF_LONGITUDE: lon},
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "service_device_not_found"

    # Test set_scheduled_charging validation error (enable=True but no time)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_CHARGING,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_ENABLE: True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "set_scheduled_charging_time"

    # Test set_scheduled_departure validation error
    # (preconditioning_enabled=True but no departure_time)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_PRECONDITIONING_ENABLED: True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "set_scheduled_departure_preconditioning"

    # Test set_scheduled_departure validation error
    # (off_peak_charging_enabled=True but no end_off_peak_time)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULED_DEPARTURE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_OFF_PEAK_CHARGING_ENABLED: True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "set_scheduled_departure_off_peak"

    energy_device = entity_registry.async_get(
        "sensor.energy_site_battery_power"
    ).device_id

    # Vehicle-only service targeting an energy-site device -> no vehicle match
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_ATTR_GPS_REQUEST,
            {
                CONF_DEVICE_ID: energy_device,
                ATTR_GPS: {CONF_LATITUDE: lat, CONF_LONGITUDE: lon},
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "no_vehicle_data_for_device"

    # Energy-only service targeting a vehicle device -> no energy-site match
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: vehicle_device,
                ATTR_TOU_SETTINGS: {"utility": "test"},
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "no_energy_site_data_for_device"

    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "unrelated")},
    )

    # Teslemetry service targeting a device with no Teslemetry config entry
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_ATTR_GPS_REQUEST,
            {
                CONF_DEVICE_ID: other_device.id,
                ATTR_GPS: {CONF_LATITUDE: lat, CONF_LONGITUDE: lon},
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "service_device_wrong_domain"


@pytest.mark.parametrize(
    ("service", "data", "method", "expected_args"),
    [
        pytest.param(
            SERVICE_DISPATCH_BATTERY_POWER,
            {ATTR_POWER: -5000, ATTR_DURATION: 1800},
            "dispatch_battery_power",
            (-5000, 1800),
            id="dispatch_battery_power",
        ),
        pytest.param(
            SERVICE_DISPATCH_BATTERY_POWER,
            {ATTR_POWER: 10000, ATTR_DURATION: 1800},
            "dispatch_battery_power",
            (10000, 1800),
            id="dispatch_battery_power_10kw",
        ),
        pytest.param(
            SERVICE_DISPATCH_BATTERY_POWER,
            {ATTR_POWER: 100000, ATTR_DURATION: 1800},
            "dispatch_battery_power",
            (100000, 1800),
            id="dispatch_battery_power_max",
        ),
        pytest.param(
            SERVICE_RESUME_BATTERY_OPERATION,
            {},
            "resume_battery_operation",
            (),
            id="resume_battery_operation",
        ),
    ],
)
async def test_local_battery_services(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service: str,
    data: dict[str, int],
    method: str,
    expected_args: tuple[int, ...],
) -> None:
    """Test the local battery services call the paired gateway."""
    entry = await _setup_site(hass, [PAIRED_SITE])
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(SITE_ID)), entry.entry_id
    )
    assert device

    with patch(f"aiopowerwall.PowerwallClient.{method}") as mock_method:
        await hass.services.async_call(
            DOMAIN,
            service,
            {CONF_DEVICE_ID: device.id, **data},
            blocking=True,
        )
    mock_method.assert_awaited_once_with(*expected_args)


@pytest.mark.parametrize(("service", "data", "method"), LOCAL_BATTERY_SERVICES)
@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(
            PowerwallNotSupportedError("dispatch_battery_power", 12, ""),
            "local_command_not_supported",
            id="not_supported",
        ),
        pytest.param(
            PowerwallCommandError("dispatch_battery_power", 3, "invalid"),
            "local_command_failed",
            id="command_error",
        ),
        pytest.param(
            PowerwallCommandError(
                "dispatch_battery_power",
                11,
                "power 10100.000000 exceeds discharge limit 10000",
            ),
            "local_command_out_of_range",
            id="out_of_range",
        ),
        pytest.param(
            PowerwallConnectionError("unreachable"),
            "local_command_failed",
            id="connection_error",
        ),
    ],
)
async def test_local_battery_services_errors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service: str,
    data: dict[str, int],
    method: str,
    error: PowerwallError,
    translation_key: str,
) -> None:
    """Test the local battery services translate gateway errors."""
    entry = await _setup_site(hass, [PAIRED_SITE])
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(SITE_ID)), entry.entry_id
    )
    assert device

    with (
        patch(f"aiopowerwall.PowerwallClient.{method}", side_effect=error),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {CONF_DEVICE_ID: device.id, **data},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key
    assert not exc_info.value.translation_placeholders


async def test_dispatch_battery_power_out_of_range_message(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the gateway's own out of range text is logged, not shown to the user."""
    entry = await _setup_site(hass, [PAIRED_SITE])
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(SITE_ID)), entry.entry_id
    )
    assert device

    with (
        patch(
            "aiopowerwall.PowerwallClient.dispatch_battery_power",
            side_effect=PowerwallCommandError(
                "dispatch_battery_power",
                11,
                "power 10100.000000 exceeds discharge limit 10000",
            ),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DISPATCH_BATTERY_POWER,
            {CONF_DEVICE_ID: device.id, ATTR_POWER: 10100, ATTR_DURATION: 1800},
            blocking=True,
        )
    assert str(exc_info.value) == (
        "The Powerwall gateway rejected the requested power, "
        "change the power value and try again"
    )
    assert "exceeds discharge limit" not in str(exc_info.value)
    assert "power 10100.000000 exceeds discharge limit 10000" in caplog.text


@pytest.mark.parametrize(("service", "data", "method"), LOCAL_BATTERY_SERVICES)
@pytest.mark.parametrize(
    "subentries",
    [
        pytest.param([], id="not_added"),
        pytest.param(
            [
                ConfigSubentryData(
                    subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
                    unique_id=str(SITE_ID),
                    title="Energy Site",
                    data={CONF_SITE_ID: SITE_ID},
                )
            ],
            id="added_without_credentials",
        ),
    ],
)
async def test_local_battery_services_not_paired(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service: str,
    data: dict[str, int],
    method: str,
    subentries: list[ConfigSubentryData],
) -> None:
    """Test the local battery services reject a site without a local gateway."""
    entry = await _setup_site(hass, subentries)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(SITE_ID)), entry.entry_id
    )
    assert device

    with (
        patch(f"aiopowerwall.PowerwallClient.{method}") as mock_method,
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {CONF_DEVICE_ID: device.id, **data},
            blocking=True,
        )
    assert exc_info.value.translation_key == "no_local_powerwall"
    mock_method.assert_not_called()


@pytest.mark.parametrize(
    ("power", "duration"),
    [
        pytest.param(5000, 0, id="duration_too_short"),
        pytest.param(5000, 86401, id="duration_too_long"),
        pytest.param(-100001, 1800, id="charge_power_too_high"),
        pytest.param(100001, 1800, id="discharge_power_too_high"),
    ],
)
async def test_dispatch_battery_power_out_of_range(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    power: int,
    duration: int,
) -> None:
    """Test a power or duration outside the allowed range is rejected."""
    entry = await _setup_site(hass, [PAIRED_SITE])
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(SITE_ID)), entry.entry_id
    )
    assert device

    with (
        patch("aiopowerwall.PowerwallClient.dispatch_battery_power") as mock_method,
        pytest.raises(probatio.Invalid),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DISPATCH_BATTERY_POWER,
            {CONF_DEVICE_ID: device.id, ATTR_POWER: power, ATTR_DURATION: duration},
            blocking=True,
        )
    mock_method.assert_not_called()
