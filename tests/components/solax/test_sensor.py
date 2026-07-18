"""Tests for the solax sensor platform."""

from unittest.mock import patch

from solax.inverter import InverterResponse
from solax.inverters import X1MiniV34

from homeassistant.components.solax.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


def __mock_get_data() -> InverterResponse:
    return InverterResponse(
        data=dict.fromkeys(X1MiniV34.sensor_map(), 0),
        dongle_serial_number="ABCDEFGHIJ",
        version="2.034.06",
        type=4,
        inverter_serial_number="XXXXXXX",
    )


async def test_device_info_model(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the device registry entry has the discovered inverter model set."""
    entry_data = {
        CONF_IP_ADDRESS: "192.168.1.87",
        CONF_PORT: 80,
        CONF_PASSWORD: "password",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id="ABCDEFGHIJ")
    entry.add_to_hass(hass)

    inverter = next(
        iter(
            X1MiniV34.build_all_variants(
                entry_data[CONF_IP_ADDRESS],
                entry_data[CONF_PORT],
                entry_data[CONF_PASSWORD],
            )
        )
    )

    with (
        patch("homeassistant.components.solax.discover", return_value=inverter),
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCDEFGHIJ")})
    assert device is not None
    assert device.model == "x1_mini_v34"
