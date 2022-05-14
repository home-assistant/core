"""Representation of Z-Wave updates."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.driver import CheckConfigUpdates

from homeassistant.components.update import UpdateEntity
from homeassistant.components.update.const import UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(days=1)

UNKNOWN = "unknown"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave update from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_device_configs_update_entity() -> None:
        """Add device configs update entity."""
        async_add_entities([ZWaveDeviceConfigsUpdate(client)], update_before_add=True)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_device_configs_update_entity",
            async_add_device_configs_update_entity,
        )
    )


class ZWaveDeviceConfigsUpdate(UpdateEntity):
    """Representation of a Z-Wave device configs update."""

    def __init__(self, client: ZwaveClient) -> None:
        """Initialize a ping Z-Wave device button entity."""
        # Entity class attributes
        self.client = client
        self._home_id = client.driver.controller.home_id

        self._attr_title = "Z-Wave JS"
        self._attr_unique_id = f"{self._home_id}.device_configs_update"
        self._attr_supported_features = UpdateEntityFeature.INSTALL

        self._config_updates: CheckConfigUpdates | None = None

    async def async_update(self) -> None:
        """Update the state."""
        self._config_updates = await self.client.driver.async_check_for_config_updates()

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return f"{self._attr_title} Device Configs: Update"

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        assert self._config_updates
        if self._config_updates.update_available:
            return self._config_updates.new_version  # type: ignore[no-any-return]
        return self.installed_version

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed version."""
        return UNKNOWN

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.unique_id}_poll_value",
                self.async_poll_value,
            )
        )
        # Override title to include Home ID if there are multiple Z-Wave JS config
        # entries
        if len(self.hass.config_entries.async_entries(DOMAIN)) > 1:
            self._attr_title = f"{self._attr_title} ({self._home_id})"

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        LOGGER.error(
            "There is no value to refresh for this entity so the zwave_js.refresh_value "
            "service won't work for it"
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.client.driver.async_install_config_update()
