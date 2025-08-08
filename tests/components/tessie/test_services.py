"""Test the Tessie services."""

from unittest.mock import patch

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.tessie.const import CONF_VALUE, DOMAIN, SERVICE_SHARE
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .common import setup_platform


async def test_share_success(hass: HomeAssistant) -> None:
    """Test the share service."""

    entry = await setup_platform(hass)

    device_registry = dr.async_get(hass)

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    test_device = devices[0]

    with patch(
        "homeassistant.components.tessie.services.share",
        return_value={
            "result": True,
        },
    ) as service_share:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHARE,
            {
                CONF_DEVICE_ID: test_device.id,
                CONF_VALUE: "48.858364,2.2946128",
            },
            blocking=True,
        )
        service_share.assert_called_once()


async def test_share_bad_content(hass: HomeAssistant) -> None:
    """Test the share service."""

    entry = await setup_platform(hass)

    device_registry = dr.async_get(hass)

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    test_device = devices[0]

    with patch(
        "homeassistant.components.tessie.services.share",
        return_value={
            "result": False,
            "reason": "unknown",
        },
    ) as service_share:
        with pytest.raises(HomeAssistantError) as e:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SHARE,
                {
                    CONF_DEVICE_ID: test_device.id,
                    CONF_VALUE: "Test content",
                },
                blocking=True,
            )
        assert e.value.translation_key == "unknown"
        service_share.assert_called_once()


async def test_share_client_error(hass: HomeAssistant) -> None:
    """Test the share service."""

    entry = await setup_platform(hass)

    device_registry = dr.async_get(hass)

    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    test_device = devices[0]

    with patch(
        "homeassistant.components.tessie.services.share",
        side_effect=ClientResponseError(None, None, status=500, message="Client error"),
    ) as service_share:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SHARE,
                {
                    CONF_DEVICE_ID: test_device.id,
                    CONF_VALUE: "Test content",
                },
                blocking=True,
            )
        service_share.assert_called_once()


async def test_share_bad_device(hass: HomeAssistant) -> None:
    """Test the share service."""

    await setup_platform(hass)

    with patch(
        "homeassistant.components.tessie.services.share",
    ) as service_share:
        with pytest.raises(HomeAssistantError) as e:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SHARE,
                {
                    CONF_DEVICE_ID: "abcdef123456",
                    CONF_VALUE: "Test content",
                },
                blocking=True,
            )
        assert e.value.translation_key == "invalid_device"
        service_share.assert_not_called()
