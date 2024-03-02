"""Tracks devices by sending a ICMP echo request (ping)."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
    SourceType,
)
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    remove_device_from_config,
)
from homeassistant.config import load_yaml_config_file
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import PingDomainData
from .const import CONF_IMPORTED_BY, CONF_PING_COUNT, DOMAIN
from .coordinator import PingUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTS): {cv.slug: cv.string},
        vol.Optional(CONF_PING_COUNT, default=1): cv.positive_int,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Legacy init: import via config flow."""

    async def _run_import(_: Event) -> None:
        """Delete devices from known_device.yaml and import them via config flow."""
        _LOGGER.debug(
            "Home Assistant successfully started, importing ping device tracker config entries now"
        )

        devices: dict[str, dict[str, Any]] = {}
        try:
            devices = await hass.async_add_executor_job(
                load_yaml_config_file, hass.config.path(YAML_DEVICES)
            )
        except (FileNotFoundError, HomeAssistantError):
            _LOGGER.debug(
                "No valid known_devices.yaml found, "
                "skip removal of devices from known_devices.yaml"
            )

        for dev_name, dev_host in config[CONF_HOSTS].items():
            if dev_name in devices:
                await hass.async_add_executor_job(
                    remove_device_from_config, hass, dev_name
                )
                _LOGGER.debug("Removed device %s from known_devices.yaml", dev_name)

            if not hass.states.async_available(f"device_tracker.{dev_name}"):
                hass.states.async_remove(f"device_tracker.{dev_name}")

            # run import after everything has been cleaned up
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_IMPORTED_BY: "device_tracker",
                        CONF_NAME: dev_name,
                        CONF_HOST: dev_host,
                        CONF_PING_COUNT: config[CONF_PING_COUNT],
                        CONF_CONSIDER_HOME: config[CONF_CONSIDER_HOME],
                    },
                )
            )

            async_create_issue(
                hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                breaks_in_ha_version="2024.6.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Ping",
                },
            )

    # delay the import until after Home Assistant has started and everything has been initialized,
    # as the legacy device tracker entities will be restored after the legacy device tracker platforms
    # have been set up, so we can only remove the entities from the state machine then
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _run_import)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Ping config entry."""

    data: PingDomainData = hass.data[DOMAIN]

    async_add_entities([PingDeviceTracker(entry, data.coordinators[entry.entry_id])])


class PingDeviceTracker(CoordinatorEntity[PingUpdateCoordinator], ScannerEntity):
    """Representation of a Ping device tracker."""

    _last_seen: datetime | None = None

    def __init__(
        self, config_entry: ConfigEntry, coordinator: PingUpdateCoordinator
    ) -> None:
        """Initialize the Ping device tracker."""
        super().__init__(coordinator)

        self._attr_name = config_entry.title
        self.config_entry = config_entry
        self._consider_home_interval = timedelta(
            seconds=config_entry.options.get(
                CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.seconds
            )
        )

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self.coordinator.data.ip_address

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.config_entry.entry_id

    @property
    def source_type(self) -> SourceType:
        """Return the source type which is router."""
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        """Return true if ping returns is_alive or considered home."""
        if self.coordinator.data.is_alive:
            self._last_seen = dt_util.utcnow()

        return (
            self._last_seen is not None
            and (dt_util.utcnow() - self._last_seen) < self._consider_home_interval
        )

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        if CONF_IMPORTED_BY in self.config_entry.data:
            return bool(self.config_entry.data[CONF_IMPORTED_BY] == "device_tracker")
        return False
