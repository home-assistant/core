"""Representation of a deCONZ gateway."""

from __future__ import annotations

import asyncio
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

import async_timeout
from pydeconz import DeconzSession, errors
from pydeconz.models import ResourceGroup
from pydeconz.models.alarm_system import AlarmSystem as DeconzAlarmSystem
from pydeconz.models.group import Group as DeconzGroup
from pydeconz.models.light import LightBase as DeconzLight
from pydeconz.models.sensor import SensorBase as DeconzSensor

from homeassistant.config_entries import SOURCE_HASSIO, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_ALLOW_NEW_DEVICES,
    CONF_MASTER_GATEWAY,
    DEFAULT_ALLOW_CLIP_SENSOR,
    DEFAULT_ALLOW_DECONZ_GROUPS,
    DEFAULT_ALLOW_NEW_DEVICES,
    DOMAIN as DECONZ_DOMAIN,
    HASSIO_CONFIGURATION_URL,
    LOGGER,
    PLATFORMS,
)
from .errors import AuthenticationRequired, CannotConnect

if TYPE_CHECKING:
    from .deconz_event import DeconzAlarmEvent, DeconzEvent


class DeconzGateway:
    """Manages a single deCONZ gateway."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: DeconzSession
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api

        api.add_device_callback = self.async_add_device_callback
        api.connection_status_callback = self.async_connection_status_callback

        self.available = True
        self.ignore_state_updates = False

        self.signal_reachable = f"deconz-reachable-{config_entry.entry_id}"
        self.signal_reload_groups = f"deconz_reload_group_{config_entry.entry_id}"

        self.signal_new_light = f"deconz_new_light_{config_entry.entry_id}"
        self.signal_new_sensor = f"deconz_new_sensor_{config_entry.entry_id}"

        self.deconz_resource_type_to_signal_new_device = {
            ResourceGroup.LIGHT.value: self.signal_new_light,
            ResourceGroup.SENSOR.value: self.signal_new_sensor,
        }

        self.deconz_ids: dict[str, str] = {}
        self.entities: dict[str, set[str]] = {}
        self.events: list[DeconzAlarmEvent | DeconzEvent] = []

        self._option_allow_deconz_groups = self.config_entry.options.get(
            CONF_ALLOW_DECONZ_GROUPS, DEFAULT_ALLOW_DECONZ_GROUPS
        )

    @property
    def bridgeid(self) -> str:
        """Return the unique identifier of the gateway."""
        return cast(str, self.config_entry.unique_id)

    @property
    def host(self) -> str:
        """Return the host of the gateway."""
        return cast(str, self.config_entry.data[CONF_HOST])

    @property
    def master(self) -> bool:
        """Gateway which is used with deCONZ services without defining id."""
        return cast(bool, self.config_entry.options[CONF_MASTER_GATEWAY])

    # Options

    @property
    def option_allow_clip_sensor(self) -> bool:
        """Allow loading clip sensor from gateway."""
        return self.config_entry.options.get(
            CONF_ALLOW_CLIP_SENSOR, DEFAULT_ALLOW_CLIP_SENSOR
        )

    @property
    def option_allow_deconz_groups(self) -> bool:
        """Allow loading deCONZ groups from gateway."""
        return self.config_entry.options.get(
            CONF_ALLOW_DECONZ_GROUPS, DEFAULT_ALLOW_DECONZ_GROUPS
        )

    @property
    def option_allow_new_devices(self) -> bool:
        """Allow automatic adding of new devices."""
        return self.config_entry.options.get(
            CONF_ALLOW_NEW_DEVICES, DEFAULT_ALLOW_NEW_DEVICES
        )

    # Callbacks

    @callback
    def async_connection_status_callback(self, available: bool) -> None:
        """Handle signals of gateway connection status."""
        self.available = available
        self.ignore_state_updates = False
        async_dispatcher_send(self.hass, self.signal_reachable)

    @callback
    def async_add_device_callback(
        self,
        resource_type: str,
        device: DeconzAlarmSystem
        | DeconzGroup
        | DeconzLight
        | DeconzSensor
        | list[DeconzAlarmSystem | DeconzGroup | DeconzLight | DeconzSensor]
        | None = None,
        force: bool = False,
    ) -> None:
        """Handle event of new device creation in deCONZ."""
        if (
            not force
            and not self.option_allow_new_devices
            or resource_type not in self.deconz_resource_type_to_signal_new_device
        ):
            return

        args = []

        if device is not None and not isinstance(device, list):
            args.append([device])

        async_dispatcher_send(
            self.hass,
            self.deconz_resource_type_to_signal_new_device[resource_type],
            *args,  # Don't send device if None, it would override default value in listeners
        )

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        if self.api.config.mac is None:
            return

        device_registry = dr.async_get(self.hass)

        # Host device
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.api.config.mac)},
        )

        # Gateway service
        configuration_url = f"http://{self.host}:{self.config_entry.data[CONF_PORT]}"
        if self.config_entry.source == SOURCE_HASSIO:
            configuration_url = HASSIO_CONFIGURATION_URL
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            configuration_url=configuration_url,
            entry_type=dr.DeviceEntryType.SERVICE,
            identifiers={(DECONZ_DOMAIN, self.api.config.bridge_id)},
            manufacturer="Dresden Elektronik",
            model=self.api.config.model_id,
            name=self.api.config.name,
            sw_version=self.api.config.software_version,
            via_device=(CONNECTION_NETWORK_MAC, self.api.config.mac),
        )

    @staticmethod
    async def async_config_entry_updated(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle signals of config entry being updated.

        This is a static method because a class method (bound method), can not be used with weak references.
        Causes for this is either discovery updating host address or config entry options changing.
        """
        gateway = get_gateway_from_config_entry(hass, entry)

        if gateway.api.host != gateway.host:
            gateway.api.close()
            gateway.api.host = gateway.host
            gateway.api.start()
            return

        await gateway.options_updated()

    async def options_updated(self) -> None:
        """Manage entities affected by config entry options."""
        deconz_ids = []

        if self.option_allow_clip_sensor:
            self.async_add_device_callback(ResourceGroup.SENSOR.value)

        else:
            deconz_ids += [
                sensor.deconz_id
                for sensor in self.api.sensors.values()
                if sensor.type.startswith("CLIP")
            ]

        if self.option_allow_deconz_groups:
            if not self._option_allow_deconz_groups:
                async_dispatcher_send(self.hass, self.signal_reload_groups)
        else:
            deconz_ids += [group.deconz_id for group in self.api.groups.values()]

        self._option_allow_deconz_groups = self.option_allow_deconz_groups

        entity_registry = er.async_get(self.hass)

        for entity_id, deconz_id in self.deconz_ids.items():
            if deconz_id in deconz_ids and entity_registry.async_is_registered(
                entity_id
            ):
                # Removing an entity from the entity registry will also remove them
                # from Home Assistant
                entity_registry.async_remove(entity_id)

    @callback
    def shutdown(self, event: Event) -> None:
        """Wrap the call to deconz.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.api.close()

    async def async_reset(self) -> bool:
        """Reset this gateway to default state."""
        self.api.connection_status_callback = None
        self.api.close()

        await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )

        self.deconz_ids = {}
        return True


@callback
def get_gateway_from_config_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> DeconzGateway:
    """Return gateway with a matching config entry ID."""
    return cast(DeconzGateway, hass.data[DECONZ_DOMAIN][config_entry.entry_id])


async def get_deconz_session(
    hass: HomeAssistant,
    config: MappingProxyType[str, Any],
) -> DeconzSession:
    """Create a gateway object and verify configuration."""
    session = aiohttp_client.async_get_clientsession(hass)

    deconz_session = DeconzSession(
        session,
        config[CONF_HOST],
        config[CONF_PORT],
        config[CONF_API_KEY],
    )
    try:
        async with async_timeout.timeout(10):
            await deconz_session.refresh_state()
        return deconz_session

    except errors.Unauthorized as err:
        LOGGER.warning("Invalid key for deCONZ at %s", config[CONF_HOST])
        raise AuthenticationRequired from err

    except (asyncio.TimeoutError, errors.RequestError, errors.ResponseError) as err:
        LOGGER.error("Error connecting to deCONZ gateway at %s", config[CONF_HOST])
        raise CannotConnect from err
