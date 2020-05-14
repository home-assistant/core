"""The tests for the AsusWrt sensor platform."""
from datetime import datetime, timedelta

from aioasuswrt.asuswrt import Device
from asynctest import CoroutineMock, patch

from homeassistant.components import sensor
from homeassistant.components.asuswrt import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_MODE,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SENSORS,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

VALID_CONFIG_ROUTER_SSH = {
    DOMAIN: {
        CONF_DNSMASQ: "/",
        CONF_HOST: "fake_host",
        CONF_INTERFACE: "eth0",
        CONF_MODE: "router",
        CONF_PORT: "22",
        CONF_PROTOCOL: "ssh",
        CONF_USERNAME: "fake_user",
        CONF_PASSWORD: "fake_pass",
        CONF_SENSORS: [
            "devices",
            "download_speed",
            "download",
            "upload_speed",
            "upload",
        ],
    }
}

MOCK_DEVICES = {
    "a1:b1:c1:d1:e1:f1": Device("a1:b1:c1:d1:e1:f1", "192.168.1.2", "Test"),
    "a2:b2:c2:d2:e2:f2": Device("a2:b2:c2:d2:e2:f2", "192.168.1.3", "TestTwo"),
    "a3:b3:c3:d3:e3:f3": Device("a3:b3:c3:d3:e3:f3", "192.168.1.4", "TestThree"),
}
MOCK_BYTES_TOTAL = [60000000000, 50000000000]
MOCK_CURRENT_TRANSFER_RATES = [20000000, 10000000]


async def test_sensors(hass: HomeAssistant):
    """Test creating an AsusWRT sensor."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = CoroutineMock()
        AsusWrt().async_get_connected_devices = CoroutineMock(return_value=MOCK_DEVICES)
        AsusWrt().async_get_bytes_total = CoroutineMock(return_value=MOCK_BYTES_TOTAL)
        AsusWrt().async_get_current_transfer_rates = CoroutineMock(
            return_value=MOCK_CURRENT_TRANSFER_RATES
        )

        now = datetime(2020, 1, 1, 1, tzinfo=dt_util.UTC)
        with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
            assert await async_setup_component(hass, DOMAIN, VALID_CONFIG_ROUTER_SSH)
            await hass.async_block_till_done()
            async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
            await hass.async_block_till_done()

            assert (
                hass.states.get(f"{sensor.DOMAIN}.asuswrt_devices_connected").state
                == "3"
            )
            assert (
                hass.states.get(f"{sensor.DOMAIN}.asuswrt_download_speed").state
                == "160.0"
            )
            assert hass.states.get(f"{sensor.DOMAIN}.asuswrt_download").state == "60.0"
            assert (
                hass.states.get(f"{sensor.DOMAIN}.asuswrt_upload_speed").state == "80.0"
            )
            assert hass.states.get(f"{sensor.DOMAIN}.asuswrt_upload").state == "50.0"
