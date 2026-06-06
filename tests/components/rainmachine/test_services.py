"""Test RainMachine services."""

from unittest.mock import AsyncMock

import pytest
from regenmaschine.errors import RainMachineError

from homeassistant.components.rainmachine import DOMAIN
from homeassistant.components.rainmachine.services import (
    CONF_WEATHER,
    SERVICE_NAME_PAUSE_WATERING,
    SERVICE_NAME_PUSH_FLOW_METER_DATA,
    SERVICE_NAME_PUSH_WEATHER_DATA,
    SERVICE_NAME_RESTRICT_WATERING,
    SERVICE_NAME_STOP_ALL,
    SERVICE_NAME_UNPAUSE_WATERING,
    SERVICE_NAME_UNRESTRICT_WATERING,
)
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture(name="device_id")
def device_id_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller_mac: str
) -> str:
    """Define a fixture for the RainMachine device registry ID."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, controller_mac)},
    )
    return device_entry.id


async def test_services_registered(
    hass: HomeAssistant, setup_rainmachine: None
) -> None:
    """Test that the services are registered during setup."""
    for service_name in (
        SERVICE_NAME_PAUSE_WATERING,
        SERVICE_NAME_PUSH_FLOW_METER_DATA,
        SERVICE_NAME_PUSH_WEATHER_DATA,
        SERVICE_NAME_RESTRICT_WATERING,
        SERVICE_NAME_STOP_ALL,
        SERVICE_NAME_UNPAUSE_WATERING,
        SERVICE_NAME_UNRESTRICT_WATERING,
    ):
        assert hass.services.has_service(DOMAIN, service_name)


@pytest.mark.parametrize(
    ("service_name", "service_data", "method", "expected_args", "expected_kwargs"),
    [
        (
            SERVICE_NAME_PAUSE_WATERING,
            {"seconds": 90},
            "watering.pause_all",
            (90,),
            {},
        ),
        (
            SERVICE_NAME_PUSH_FLOW_METER_DATA,
            {"value": 100},
            "watering.post_flowmeter",
            (),
            {"value": 100.0},
        ),
        (
            SERVICE_NAME_PUSH_FLOW_METER_DATA,
            {"value": 100, "unit_of_measurement": "gal"},
            "watering.post_flowmeter",
            (),
            {"value": 100.0, "units": "gal"},
        ),
        (
            SERVICE_NAME_PUSH_WEATHER_DATA,
            {"temperature": 18.5},
            "parsers.post_data",
            ({CONF_WEATHER: [{"temperature": 18.5}]},),
            {},
        ),
        (SERVICE_NAME_STOP_ALL, {}, "watering.stop_all", (), {}),
        (SERVICE_NAME_UNPAUSE_WATERING, {}, "watering.unpause_all", (), {}),
    ],
)
async def test_service_calls(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: AsyncMock,
    setup_rainmachine: None,
    device_id: str,
    service_name: str,
    service_data: dict,
    method: str,
    expected_args: tuple,
    expected_kwargs: dict,
) -> None:
    """Test that each service calls the expected controller method with arguments."""
    await hass.services.async_call(
        DOMAIN,
        service_name,
        {CONF_DEVICE_ID: device_id, **service_data},
        blocking=True,
    )

    mock = controller
    for attr in method.split("."):
        mock = getattr(mock, attr)
    mock.assert_awaited_once_with(*expected_args, **expected_kwargs)


async def test_restrict_and_unrestrict_watering(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: AsyncMock,
    setup_rainmachine: None,
    device_id: str,
) -> None:
    """Test restrict/unrestrict watering set the expected rain delay duration.

    Both services call ``restrictions.set_universal``, so the duration is what
    distinguishes them: restrict passes the requested period, unrestrict passes 0.
    """
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAME_RESTRICT_WATERING,
        {CONF_DEVICE_ID: device_id, "duration": {"minutes": 30}},
        blocking=True,
    )
    controller.restrictions.set_universal.assert_awaited_once()
    assert (
        controller.restrictions.set_universal.call_args.args[0]["rainDelayDuration"]
        == 1800.0
    )

    controller.restrictions.set_universal.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAME_UNRESTRICT_WATERING,
        {CONF_DEVICE_ID: device_id},
        blocking=True,
    )
    controller.restrictions.set_universal.assert_awaited_once()
    assert (
        controller.restrictions.set_universal.call_args.args[0]["rainDelayDuration"]
        == 0
    )


async def test_service_call_controller_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: AsyncMock,
    setup_rainmachine: None,
    device_id: str,
) -> None:
    """Test that a controller error is wrapped in a HomeAssistantError."""
    controller.watering.stop_all.side_effect = RainMachineError("error")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAME_STOP_ALL,
            {CONF_DEVICE_ID: device_id},
            blocking=True,
        )


async def test_service_call_invalid_device_id(
    hass: HomeAssistant, setup_rainmachine: None
) -> None:
    """Test that an unknown device ID raises a ServiceValidationError."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAME_STOP_ALL,
            {CONF_DEVICE_ID: "abcd1234"},
            blocking=True,
        )

    assert err.value.translation_key == "invalid_device_id"


async def test_service_call_non_rainmachine_device(
    hass: HomeAssistant, setup_rainmachine: None
) -> None:
    """Test that a non-RainMachine device raises a ServiceValidationError."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "abcd1234")},
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAME_STOP_ALL,
            {CONF_DEVICE_ID: device_entry.id},
            blocking=True,
        )

    assert err.value.translation_key == "no_controller_for_device_id"


async def test_service_call_controller_not_loaded(
    hass: HomeAssistant, setup_rainmachine: None
) -> None:
    """Test that an unloaded controller raises a ServiceValidationError."""
    unloaded_entry = MockConfigEntry(domain=DOMAIN)
    unloaded_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=unloaded_entry.entry_id,
        identifiers={(DOMAIN, "00:11:22:33:44:55")},
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAME_STOP_ALL,
            {CONF_DEVICE_ID: device_entry.id},
            blocking=True,
        )

    assert err.value.translation_key == "controller_not_ready"
