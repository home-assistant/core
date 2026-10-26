"""The rest component."""

from types import MappingProxyType
from typing import Any

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_PARAMS,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import template
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_PAYLOAD_TEMPLATE,
    CONF_SSL_SECTION,
    COORDINATOR,
    DOMAIN,
    PLATFORM_IDX,
    REST_IDX,
)
from .coordinator import RestConfigEntry, RestCoordinator
from .data import RestData
from .schema import CONFIG_SCHEMA, RESOURCE_SCHEMA
from .services import async_setup_services
from .util import (
    async_process_config,
    async_setup_shared_data,
    create_rest_data_from_config,
)

ENTRY_PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

__all__ = [
    "CONFIG_SCHEMA",
    "CONF_PAYLOAD_TEMPLATE",
    "DOMAIN",
    "RESOURCE_SCHEMA",
    "RestData",
    "create_rest_data_from_config",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the rest platforms."""
    async_setup_shared_data(hass)
    async_setup_services(hass)

    return await async_process_config(hass, config)


async def async_setup_entry(hass: HomeAssistant, config_entry: RestConfigEntry) -> None:
    """Setup config entry."""

    try:
        rest: RestData = create_rest_data_from_config_entry(hass, config_entry.data)
    except HomeAssistantError as exc:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="template_error",
            translation_placeholders={"template_error_message": str(exc)},
        ) from exc

    resource_template: template.Template = template.Template(
        config_entry.data[CONF_RESOURCE], hass
    )
    payload_template: template.Template | None = (
        template.Template(config_entry.data[CONF_PAYLOAD], hass)
        if config_entry.data.get(CONF_PAYLOAD)
        else None
    )
    coordinator = RestCoordinator(
        hass,
        rest,
        config_entry,
        resource_template,
        payload_template,
        DEFAULT_SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, ENTRY_PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(_async_entry_updated))


async def _async_entry_updated(
    hass: HomeAssistant, config_entry: ConfigEntry[Any]
) -> None:
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RestConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, ENTRY_PLATFORMS)


def convert_config_to_legacy_format(
    config: dict[str, Any] | MappingProxyType[str, Any],
) -> ConfigType:
    """Convert config entry data to legacy .yaml structure."""
    mutable_config: dict[str, Any] = {**config}
    mutable_config[CONF_RESOURCE_TEMPLATE] = mutable_config.pop(CONF_RESOURCE)
    if mutable_config.get(CONF_PAYLOAD):
        mutable_config[CONF_PAYLOAD_TEMPLATE] = mutable_config.pop(CONF_PAYLOAD)
    for key in (CONF_PARAMS, CONF_HEADERS):
        if key in mutable_config:
            mutable_config[key] = {
                param["key"]: param["value"] for param in mutable_config[key]
            }
    ssl: dict[str, Any] = mutable_config.pop(CONF_SSL_SECTION)
    auth: dict[str, Any] = mutable_config.pop(CONF_AUTHENTICATION)
    return mutable_config | ssl | auth


def create_rest_data_from_config_entry(
    hass: HomeAssistant, config: dict[str, Any] | MappingProxyType[str, Any]
) -> RestData:
    """Create RestData from user input or config entry data."""
    return create_rest_data_from_config(
        hass,
        probatio.Schema(RESOURCE_SCHEMA, extra=probatio.REMOVE_EXTRA)(
            convert_config_to_legacy_format(config)
        ),  # To convert templates
    )


async def async_get_config_and_coordinator(
    hass: HomeAssistant, platform_domain: str, discovery_info: DiscoveryInfoType
) -> tuple[ConfigType, RestCoordinator, RestData]:
    """Get the config and coordinator for the platform from discovery."""
    # pylint: disable=home-assistant-use-runtime-data
    coordinator: RestCoordinator = hass.data[DOMAIN][COORDINATOR][
        discovery_info[REST_IDX]
    ]
    # pylint: disable=home-assistant-use-runtime-data
    conf: ConfigType = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]
    if coordinator.rest.data is None:
        await coordinator.async_request_refresh()
    return conf, coordinator, coordinator.rest
