"""Support for UV data from openuv.io."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, cast

from pyopenuv import Client
from pyopenuv.errors import OpenUvError
import voluptuous as vol

from homeassistant.components.repairs import IssueSeverity, async_create_issue
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_DEVICE_ID,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSORS,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.debounce import Debouncer
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
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

DEFAULT_DEBOUNCER_COOLDOWN_SECONDS = 15 * 60

NOTIFICATION_ID = "openuv_notification"
NOTIFICATION_TITLE = "OpenUV Component Setup"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

SERVICE_NAME_UPDATE_DATA = "update_data"
SERVICE_NAME_UPDATE_PROTECTION_DATA = "update_protection_data"
SERVICE_NAME_UPDATE_UV_INDEX_DATA = "update_uv_index_data"

SERVICES = (
    SERVICE_NAME_UPDATE_DATA,
    SERVICE_NAME_UPDATE_PROTECTION_DATA,
    SERVICE_NAME_UPDATE_UV_INDEX_DATA,
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
    }
)


@callback
def async_get_openuv_for_service_call(hass: HomeAssistant, call: ServiceCall) -> OpenUV:
    """Get the OpenUV object related to a service call (by device ID)."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)

    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ValueError(f"Invalid OpenUV service ID: {device_id}")

    for entry_id in device_entry.config_entries:
        if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN:
            return cast(OpenUV, hass.data[DOMAIN][entry_id])

    raise ValueError(f"No OpenUV object for service ID: {device_id}")


@callback
def async_log_deprecated_service_call(
    hass: HomeAssistant,
    call: ServiceCall,
    alternate_service: str,
    alternate_target: str,
    breaks_in_ha_version: str,
) -> None:
    """Log a warning about a deprecated service call."""
    deprecated_service = f"{call.domain}.{call.service}"

    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_service_{deprecated_service}",
        breaks_in_ha_version=breaks_in_ha_version,
        is_fixable=False,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_service",
        translation_placeholders={
            "alternate_service": alternate_service,
            "alternate_target": alternate_target,
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
            openuv = async_get_openuv_for_service_call(hass, call)

            try:
                await func(call, openuv)
            except OpenUvError as err:
                raise HomeAssistantError(
                    f'Error while executing "{call.service}": {err}'
                ) from err

        return wrapper

    @_verify_domain_control
    @extract_openuv
    async def update_data(call: ServiceCall, openuv: OpenUV) -> None:
        """Refresh all OpenUV data."""
        async_log_deprecated_service_call(
            hass,
            call,
            "homeassistant.update_entity",
            "binary_sensor.protection_window, sensor.current_uv_index",
            "2022.11.0",
        )
        await openuv.async_update()

    @_verify_domain_control
    @extract_openuv
    async def update_uv_index_data(call: ServiceCall, openuv: OpenUV) -> None:
        """Refresh OpenUV UV index data."""
        async_log_deprecated_service_call(
            hass,
            call,
            "homeassistant.update_entity",
            "sensor.current_uv_index",
            "2022.11.0",
        )
        await openuv.async_update_uv_index_data()

    @_verify_domain_control
    @extract_openuv
    async def update_protection_data(call: ServiceCall, openuv: OpenUV) -> None:
        """Refresh OpenUV protection window data."""
        async_log_deprecated_service_call(
            hass,
            call,
            "homeassistant.update_entity",
            "binary_sensor.protection_window",
            "2022.11.0",
        )
        await openuv.async_update_protection_data()

    for service, method in (
        (SERVICE_NAME_UPDATE_DATA, update_data),
        (SERVICE_NAME_UPDATE_UV_INDEX_DATA, update_uv_index_data),
        (SERVICE_NAME_UPDATE_PROTECTION_DATA, update_protection_data),
    ):
        if hass.services.has_service(DOMAIN, service):
            continue
        hass.services.async_register(DOMAIN, service, method, schema=SERVICE_SCHEMA)

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
        coordinates = f"{openuv.client.latitude}, {openuv.client.longitude}"
        self._attr_device_info = DeviceInfo(
            entry_type=dr.DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinates)},
            manufacturer="OpenUV Team",
            name=coordinates,
        )
        self._attr_extra_state_attributes = {}
        self._attr_should_poll = False
        self._attr_unique_id = f"{coordinates}_{description.key}"
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

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service. Should be implemented by each
        OpenUV platform.
        """
        raise NotImplementedError

    def update_from_latest_data(self) -> None:
        """Update the sensor using the latest data."""
        raise NotImplementedError
