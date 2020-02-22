"""The pvpc_hourly_pricing integration to collect Spain official electric prices."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import ATTR_TARIFF, DEFAULT_NAME, DOMAIN, PLATFORM, TARIFFS

UI_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(ATTR_TARIFF, default=TARIFFS[1]): vol.In(TARIFFS),
    }
)
SENSOR_SCHEMA = UI_CONFIG_SCHEMA.extend(
    {vol.Optional(CONF_TIMEOUT, default=10): cv.positive_int}
)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(SENSOR_SCHEMA.schema)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.ensure_list(SENSOR_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: dict):
    """
    Set up the electricity price sensor from configuration.yaml.

    ```yaml
    pvpc_hourly_pricing:
      - name: PVPC manual ve
        tariff: coche_electrico
      - name: PVPC manual nocturna
        tariff: discriminacion
        timeout: 3
    ```
    """
    for conf in config.get(DOMAIN, []):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, data=conf, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up pvpc hourly pricing from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, PLATFORM)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, PLATFORM)
