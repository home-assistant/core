"""Tests for Fritz!Tools services."""

from unittest.mock import patch

from homeassistant.components.fritz.const import DOMAIN, SERVICE_SET_GUEST_WIFI_PW
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_services(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test setup of Fritz!Tools services."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    services = hass.services.async_services_for_domain(DOMAIN)
    assert services
    assert SERVICE_SET_GUEST_WIFI_PW in services

    # without loaded config entry
    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password"
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": "12345678"}
        )
        assert not mock_async_trigger_set_guest_password.called

    # with loaded config entry
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
