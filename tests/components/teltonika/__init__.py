"""Tests for Teltonika."""

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_json_object_fixture


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Teltonika integration in Home Assistant."""
    # Load real device data to create more realistic config entry
    device_data = await async_load_json_object_fixture(hass, "device_data.json", DOMAIN)  # type: ignore[misc]
    real_serial = device_data["system_info"]["mnf_info"]["serial"]  # type: ignore[index]
    real_device_name = device_data["system_info"]["static"]["device_name"]  # type: ignore[index]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=real_device_name,
        data={
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "test_password",
        },
        unique_id=real_serial,  # Use real device serial
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
