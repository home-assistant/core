"""Tests for Fritz!Tools services."""

from unittest.mock import patch

from fritzconnection.core.exceptions import FritzConnectionException, FritzServiceError
import pytest

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.fritz.services import SERVICE_SET_GUEST_WIFI_PW
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_setup_services(hass: HomeAssistant) -> None:
    """Test setup of Fritz!Tools services."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    services = hass.services.async_services_for_domain(DOMAIN)
    assert services
    assert SERVICE_SET_GUEST_WIFI_PW in services


async def test_service_set_guest_wifi_password(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test service set_guest_wifi_password."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "1C:ED:6F:12:34:11")}
    )
    assert device
    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password"
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": device.id}
        )
        assert mock_async_trigger_set_guest_password.called


async def test_service_set_guest_wifi_password_unknown_parameter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test service set_guest_wifi_password with unknown parameter."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "1C:ED:6F:12:34:11")}
    )
    assert device

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password",
        side_effect=FritzServiceError("boom"),
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": device.id}
        )
        assert mock_async_trigger_set_guest_password.called
        assert "HomeAssistantError: Action or parameter unknown" in caplog.text


async def test_service_set_guest_wifi_password_service_not_supported(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test service set_guest_wifi_password with connection error."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "1C:ED:6F:12:34:11")}
    )
    assert device

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password",
        side_effect=FritzConnectionException("boom"),
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": device.id}
        )
        assert mock_async_trigger_set_guest_password.called
        assert "HomeAssistantError: Action not supported" in caplog.text


async def test_service_set_guest_wifi_password_unloaded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test service set_guest_wifi_password."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password"
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": "12345678"}
        )
        assert not mock_async_trigger_set_guest_password.called
        assert (
            'ServiceValidationError: Failed to perform action "set_guest_wifi_password". Config entry for target not found'
            in caplog.text
        )
