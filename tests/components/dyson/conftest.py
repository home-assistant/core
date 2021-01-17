"""Configure pytest for Dyson tests."""
from unittest.mock import patch

from libpurecool.dyson_device import DysonDevice
import pytest

from homeassistant.components.dyson import CONF_LANGUAGE, DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .common import SERIAL

from tests.common import async_setup_component

BASE_PATH = "homeassistant.components.dyson"


@pytest.fixture
async def device(hass: HomeAssistant, request) -> DysonDevice:
    """Fixture to provide Dyson 360 Eye device."""
    device = request.module.get_device()
    with patch(f"{BASE_PATH}.DysonAccount.login", return_value=True), patch(
        f"{BASE_PATH}.DysonAccount.devices", return_value=[device]
    ):
        await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_USERNAME: "user@example.com",
                    CONF_PASSWORD: "password",
                    CONF_LANGUAGE: "US",
                    CONF_DEVICES: [
                        {
                            "device_id": SERIAL,
                            "device_ip": "0.0.0.0",
                        }
                    ],
                }
            },
        )
        await hass.async_block_till_done()

    return device
