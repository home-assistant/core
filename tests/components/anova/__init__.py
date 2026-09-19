"""Tests for the Anova integration."""

from unittest.mock import patch

from anova_wifi import APCUpdate, APCUpdateBinary, APCUpdateSensor, APCWifiDevice

from homeassistant.components.anova.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_UNIQUE_ID = "abc123def"

CONF_INPUT = {CONF_USERNAME: "sample@gmail.com", CONF_PASSWORD: "sample"}

ONLINE_UPDATE = APCUpdate(
    sensor=APCUpdateSensor(
        0, "Low water", "No state", 23.33, 0, "2.2.0", 20.87, 21.79, 21.33
    ),
    binary_sensor=APCUpdateBinary(False, False, False, True, False, True, False, False),
)


def create_entry(hass: HomeAssistant, device_id: str = DEVICE_UNIQUE_ID) -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Anova",
        data={
            CONF_USERNAME: "sample@gmail.com",
            CONF_PASSWORD: "sample",
        },
        unique_id="sample@gmail.com",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    return entry


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
) -> ConfigEntry:
    """Set up the Anova integration in Home Assistant."""

    with patch("homeassistant.components.anova.AnovaApi.authenticate"):
        entry = create_entry(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        return entry


def get_device(entry: ConfigEntry) -> APCWifiDevice:
    """Get the real APCWifiDevice backing the first coordinator on a set-up entry.

    The anova_api/anova_api_cooking fixtures yield a throwaway AnovaApi
    instance - the device actually used by the integration is only reachable
    through the config entry's runtime_data after setup.
    """
    return entry.runtime_data.coordinators[0].anova_device
