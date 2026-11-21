"""Tests for SimpliSafe services."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.simplisafe.const import DOMAIN
from homeassistant.components.simplisafe.services import (
    _async_get_system_for_service_call,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError


def _mock_service_call(hass: HomeAssistant) -> ServiceCall:
    """Create a service call with a selected system device."""
    call = Mock(spec=ServiceCall)
    call.configure_mock(hass=hass, data={ATTR_DEVICE_ID: "device_id"})
    return call


def test_service_call_rejects_excluded_system(hass: HomeAssistant) -> None:
    """Test service calls for excluded systems raise a validation error."""
    device_entry = Mock(via_device_id="base_station_id")
    device_registry = Mock()
    device_registry.async_get.return_value = device_entry
    base_station = Mock(identifiers={(DOMAIN, "12345")})
    config_entry = Mock(runtime_data=Mock(systems={}))

    with (
        patch(
            "homeassistant.components.simplisafe.services.dr.async_get",
            return_value=device_registry,
        ),
        patch(
            "homeassistant.components.simplisafe.services.async_get_device_and_config_entry",
            return_value=(base_station, config_entry),
        ),
        pytest.raises(ServiceValidationError) as err,
    ):
        _async_get_system_for_service_call(_mock_service_call(hass))

    assert err.value.translation_key == "system_not_selected"


def test_service_call_returns_included_system(hass: HomeAssistant) -> None:
    """Test service calls for included systems return the system."""
    device_entry = Mock(via_device_id="base_station_id")
    device_registry = Mock()
    device_registry.async_get.return_value = device_entry
    base_station = Mock(identifiers={(DOMAIN, "12345")})
    system = Mock()
    config_entry = Mock(runtime_data=Mock(systems={12345: system}))

    with (
        patch(
            "homeassistant.components.simplisafe.services.dr.async_get",
            return_value=device_registry,
        ),
        patch(
            "homeassistant.components.simplisafe.services.async_get_device_and_config_entry",
            return_value=(base_station, config_entry),
        ),
    ):
        assert _async_get_system_for_service_call(_mock_service_call(hass)) is system
