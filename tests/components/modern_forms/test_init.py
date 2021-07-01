"""Tests for the Modern Forms integration."""
from unittest.mock import MagicMock, Mock, patch

from aiomodernforms import ModernFormsConnectionError
import pytest

from homeassistant.components.modern_forms import (
    DOMAIN,
    async_unload_modern_forms_services,
)
from homeassistant.components.modern_forms.const import SERVICE_REBOOT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.components.modern_forms import (
    init_integration,
    modern_forms_no_light_call_mock,
)
from tests.test_util.aiohttp import AiohttpClientMocker


@patch(
    "homeassistant.components.modern_forms.ModernFormsDevice.update",
    side_effect=ModernFormsConnectionError,
)
async def test_config_entry_not_ready(
    mock_update: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Modern Forms configuration entry not ready."""
    entry = await init_integration(hass, aioclient_mock)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Modern Forms configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)


async def test_fan_only_device(hass, aioclient_mock):
    """Test we set unique ID if not set yet."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_no_light_call_mock
    )
    entity_registry = er.async_get(hass)

    fan_entry = entity_registry.async_get("fan.modernformsfan_fan")
    assert fan_entry
    light_entry = entity_registry.async_get("light.modernformsfan_light")
    assert light_entry is None


async def test_reboot_service(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test the reboot service of the Modern Forms fan."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.reboot") as reboot_mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REBOOT,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )
        await hass.async_block_till_done()
        reboot_mock.assert_called_once()


async def test_reboot_service_with_bad_entity(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test the reboot service against incorrect device."""
    await init_integration(hass, aioclient_mock)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REBOOT,
            {ATTR_ENTITY_ID: "light.modernformsfan_nope"},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_service_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Verify service unload works."""
    hass.data[DOMAIN] = False
    with patch(
        "homeassistant.core.ServiceRegistry.has_service", return_value=Mock(True)
    ), patch(
        "homeassistant.core.ServiceRegistry.async_remove",
        return_value=Mock(True),
    ) as async_remove:
        await async_unload_modern_forms_services(hass)
        assert hass.data[DOMAIN] is False
        assert async_remove.call_count == 1


async def test_service_unload_multiple_configs(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Verify service unload works."""
    hass.data[DOMAIN] = True
    await async_unload_modern_forms_services(hass)
    assert hass.data[DOMAIN] is True


async def test_service_unload_but_no_service(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Verify service unload works."""
    hass.data[DOMAIN] = False
    with patch(
        "homeassistant.core.ServiceRegistry.has_service", return_value=False
    ), patch(
        "homeassistant.core.ServiceRegistry.async_remove",
        return_value=Mock(True),
    ) as async_remove:
        await async_unload_modern_forms_services(hass)
        assert hass.data[DOMAIN] is False
        assert async_remove.call_count == 0
