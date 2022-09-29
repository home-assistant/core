"""Support for UV data from openuv.io."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pyopenuv import Client
from pyopenuv.errors import OpenUvError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSORS,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    entity_registry,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service import verify_domain_control

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DATA_PROTECTION_WINDOW,
    DATA_UV,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    DOMAIN,
    LOGGER,
)

CONF_ENTRY_ID = "entry_id"

DEFAULT_DEBOUNCER_COOLDOWN_SECONDS = 15 * 60

TOPIC_UPDATE = f"{DOMAIN}_data_update"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

SERVICE_NAME_UPDATE_DATA = "update_data"
SERVICE_NAME_UPDATE_PROTECTION_DATA = "update_protection_data"
SERVICE_NAME_UPDATE_UV_INDEX_DATA = "update_uv_index_data"

SERVICES = (
    SERVICE_NAME_UPDATE_DATA,
    SERVICE_NAME_UPDATE_PROTECTION_DATA,
    SERVICE_NAME_UPDATE_UV_INDEX_DATA,
)


@callback
def async_get_entity_id_from_unique_id_suffix(
    hass: HomeAssistant, entry: ConfigEntry, unique_id_suffix: str
) -> str:
    """Get the entity ID for a config entry based on unique ID suffix."""
    ent_reg = entity_registry.async_get(hass)
    [registry_entry] = [
        registry_entry
        for registry_entry in ent_reg.entities.values()
        if registry_entry.config_entry_id == entry.entry_id
        and registry_entry.unique_id.endswith(unique_id_suffix)
    ]
    return registry_entry.entity_id


@callback
def async_log_deprecated_service_call(
    hass: HomeAssistant,
    call: ServiceCall,
    alternate_service: str,
    alternate_targets: list[str],
    breaks_in_ha_version: str,
) -> None:
    """Log a warning about a deprecated service call."""
    deprecated_service = f"{call.domain}.{call.service}"

    if len(alternate_targets) > 1:
        translation_key = "deprecated_service_multiple_alternate_targets"
    else:
        translation_key = "deprecated_service_single_alternate_target"

    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_service_{deprecated_service}",
        breaks_in_ha_version=breaks_in_ha_version,
        is_fixable=False,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={
            "alternate_service": alternate_service,
            "alternate_targets": ", ".join(alternate_targets),
            "deprecated_service": deprecated_service,
        },
    )

    LOGGER.warning(
        (
            'The "%s" service is deprecated and will be removed in %s; review the '
            "Repairs item in the UI for more information"
        ),
        deprecated_service,
        breaks_in_ha_version,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenUV as config entry."""
    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    websession = aiohttp_client.async_get_clientsession(hass)
    openuv = OpenUV(
        hass,
        entry,
        Client(
            entry.data[CONF_API_KEY],
            entry.data.get(CONF_LATITUDE, hass.config.latitude),
            entry.data.get(CONF_LONGITUDE, hass.config.longitude),
            altitude=entry.data.get(CONF_ELEVATION, hass.config.elevation),
            session=websession,
        ),
    )

    # We disable the client's request retry abilities here to avoid a lengthy (and
    # blocking) startup:
    openuv.client.disable_request_retries()

    try:
        await openuv.async_update()
    except HomeAssistantError as err:
        LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    # Once we've successfully authenticated, we re-enable client request retries:
    openuv.client.enable_request_retries()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = openuv

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def extract_openuv(func: Callable) -> Callable:
        """Define a decorator to get the correct OpenUV object for a service call."""

        async def wrapper(call: ServiceCall) -> None:
            """Wrap the service function."""
            openuv: OpenUV = hass.data[DOMAIN][call.data[CONF_ENTRY_ID]]

            try:
                await func(call, openuv)
            except OpenUvError as err:
                raise HomeAssistantError(
                    f'Error while executing "{call.service}": {err}'
                ) from err

        return wrapper

    # We determine entity IDs needed to help the user migrate from deprecated services:
    current_uv_index_entity_id = async_get_entity_id_from_unique_id_suffix(
        hass, entry, "current_uv_index"
    )
    protection_window_entity_id = async_get_entity_id_from_unique_id_suffix(
        hass, entry, "protection_window"
    )

    @_verify_domain_control
    @extract_openuv
    async def update_data(call: ServiceCall, openuv: OpenUV) -> None:
        """Refresh all OpenUV data."""
        LOGGER.debug("Refreshing all OpenUV data")
        async_log_deprecated_service_call(
            hass,
            call,
            "homeassistant.update_entity",
            [protection_window_entity_id, current_uv_index_entity_id],
            "2022.12.0",
        )
        await openuv.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    @_verify_domain_control
    @extract_openuv
    async def update_uv_index_data(call: ServiceCall, openuv: OpenUV) -> None:
        """Refresh OpenUV UV index data."""
        LOGGER.debug("Refreshing OpenUV UV index data")
        async_log_deprecated_service_call(
            hass,
            call,
            "homeassistant.update_entity",
            [current_uv_index_entity_id],
            "2022.12.0",
        )
        await openuv.async_update_uv_index_data()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    @_verify_domain_control
    @extract_openuv
    async def update_protection_data(call: ServiceCall, openuv: OpenUV) -> None:
        """Refresh OpenUV protection window data."""
        LOGGER.debug("Refreshing OpenUV protection window data")
        async_log_deprecated_service_call(
            hass,
            call,
            "homeassistant.update_entity",
            [protection_window_entity_id],
            "2022.12.0",
        )
        await openuv.async_update_protection_data()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    service_schema = vol.Schema(
        {
            vol.Optional(CONF_ENTRY_ID, default=entry.entry_id): cv.string,
        }
    )

    for service, method in (
        (SERVICE_NAME_UPDATE_DATA, update_data),
        (SERVICE_NAME_UPDATE_UV_INDEX_DATA, update_uv_index_data),
        (SERVICE_NAME_UPDATE_PROTECTION_DATA, update_protection_data),
    ):
        if hass.services.has_service(DOMAIN, service):
            continue
        hass.services.async_register(DOMAIN, service, method, schema=service_schema)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OpenUV config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        # If this is the last loaded instance of OpenUV, deregister any services
        # defined during integration setup:
        for service_name in SERVICES:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the config entry upon new versions."""
    version = entry.version
    data = {**entry.data}

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Remove unused condition data:
    if version == 1:
        data.pop(CONF_BINARY_SENSORS, None)
        data.pop(CONF_SENSORS, None)
        version = entry.version = 2
        hass.config_entries.async_update_entry(entry, data=data)
        LOGGER.debug("Migration to version %s successful", version)

    return True


class OpenUV:
    """Define a generic OpenUV object."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: Client) -> None:
        """Initialize."""
        self._update_protection_data_debouncer = Debouncer(
            hass,
            LOGGER,
            cooldown=DEFAULT_DEBOUNCER_COOLDOWN_SECONDS,
            immediate=True,
            function=self._async_update_protection_data,
        )

        self._update_uv_index_data_debouncer = Debouncer(
            hass,
            LOGGER,
            cooldown=DEFAULT_DEBOUNCER_COOLDOWN_SECONDS,
            immediate=True,
            function=self._async_update_uv_index_data,
        )

        self._entry = entry
        self.client = client
        self.data: dict[str, Any] = {DATA_PROTECTION_WINDOW: {}, DATA_UV: {}}

    async def _async_update_protection_data(self) -> None:
        """Update binary sensor (protection window) data."""
        low = self._entry.options.get(CONF_FROM_WINDOW, DEFAULT_FROM_WINDOW)
        high = self._entry.options.get(CONF_TO_WINDOW, DEFAULT_TO_WINDOW)

        try:
            data = await self.client.uv_protection_window(low=low, high=high)
        except OpenUvError as err:
            raise HomeAssistantError(
                f"Error during protection data update: {err}"
            ) from err

        self.data[DATA_PROTECTION_WINDOW] = data.get("result")

    async def _async_update_uv_index_data(self) -> None:
        """Update sensor (uv index, etc) data."""
        try:
            data = await self.client.uv_index()
        except OpenUvError as err:
            raise HomeAssistantError(
                f"Error during UV index data update: {err}"
            ) from err

        self.data[DATA_UV] = data.get("result")

    async def async_update_protection_data(self) -> None:
        """Update binary sensor (protection window) data with a debouncer."""
        await self._update_protection_data_debouncer.async_call()

    async def async_update_uv_index_data(self) -> None:
        """Update sensor (uv index, etc) data with a debouncer."""
        await self._update_uv_index_data_debouncer.async_call()

    async def async_update(self) -> None:
        """Update sensor/binary sensor data."""
        tasks = [self.async_update_protection_data(), self.async_update_uv_index_data()]
        await asyncio.gather(*tasks)


class OpenUvEntity(Entity):
    """Define a generic OpenUV entity."""

    _attr_has_entity_name = True

    def __init__(self, openuv: OpenUV, description: EntityDescription) -> None:
        """Initialize."""
        self._attr_extra_state_attributes = {}
        self._attr_should_poll = False
        self._attr_unique_id = (
            f"{openuv.client.latitude}_{openuv.client.longitude}_{description.key}"
        )
        self.entity_description = description
        self.openuv = openuv

    @callback
    def async_update_state(self) -> None:
        """Update the state."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.update_from_latest_data()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self.async_update_state)
        )

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service. Should be implemented by each
        OpenUV platform.
        """
        raise NotImplementedError

    def update_from_latest_data(self) -> None:
        """Update the sensor using the latest data."""
        raise NotImplementedError
