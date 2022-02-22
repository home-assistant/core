"""Support for IKEA Tradfri."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from pytradfri import Gateway, PytradfriError, RequestError
from pytradfri.api.aiocoap_api import APIFactory
from pytradfri.command import Command
from pytradfri.device import Device
from pytradfri.group import Group
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_TRADFRI_GATEWAY,
    ATTR_TRADFRI_GATEWAY_MODEL,
    ATTR_TRADFRI_MANUFACTURER,
    CONF_ALLOW_TRADFRI_GROUPS,
    CONF_GATEWAY_ID,
    CONF_IDENTITY,
    CONF_IMPORT_GROUPS,
    CONF_KEY,
    COORDINATOR,
    COORDINATOR_LIST,
    DEFAULT_ALLOW_TRADFRI_GROUPS,
    DOMAIN,
    GROUPS_LIST,
    KEY_API,
    PLATFORMS,
    SIGNAL_GW,
    TIMEOUT_API,
)
from .coordinator import (
    TradfriDeviceDataUpdateCoordinator,
    TradfriGroupDataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

FACTORY = "tradfri_factory"
LISTENERS = "tradfri_listeners"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                cv.deprecated(CONF_HOST),
                cv.deprecated(
                    CONF_ALLOW_TRADFRI_GROUPS,
                ),
                {
                    vol.Optional(CONF_HOST): cv.string,
                    vol.Optional(
                        CONF_ALLOW_TRADFRI_GROUPS, default=DEFAULT_ALLOW_TRADFRI_GROUPS
                    ): cv.boolean,
                },
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tradfri component."""
    if (conf := config.get(DOMAIN)) is None:
        return True

    configured_hosts = [
        entry.data.get("host") for entry in hass.config_entries.async_entries(DOMAIN)
    ]

    host = conf.get(CONF_HOST)
    import_groups = conf[CONF_ALLOW_TRADFRI_GROUPS]

    if host is None or host in configured_hosts:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: host, CONF_IMPORT_GROUPS: import_groups},
        )
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Create a gateway."""
    tradfri_data: dict[str, Any] = {}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = tradfri_data
    listeners = tradfri_data[LISTENERS] = []

    factory = await APIFactory.init(
        entry.data[CONF_HOST],
        psk_id=entry.data[CONF_IDENTITY],
        psk=entry.data[CONF_KEY],
    )
    tradfri_data[FACTORY] = factory  # Used for async_unload_entry

    async def on_hass_stop(event: Event) -> None:
        """Close connection when hass stops."""
        await factory.shutdown()

    # Setup listeners
    listeners.append(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop))

    api = factory.request
    gateway = Gateway()
    groups: list[Group] = []

    try:
        gateway_info = await api(gateway.get_gateway_info(), timeout=TIMEOUT_API)
        devices_commands: Command = await api(
            gateway.get_devices(), timeout=TIMEOUT_API
        )
        devices: list[Device] = await api(devices_commands, timeout=TIMEOUT_API)

        if entry.data[CONF_IMPORT_GROUPS]:
            # Note: we should update this page when deprecating:
            # https://www.home-assistant.io/integrations/tradfri/
            _LOGGER.warning(
                "Importing of Tradfri groups has been deprecated due to stability issues "
                "and will be removed in Home Assistant core 2022.4"
            )
            # No need to load groups if the user hasn't requested it
            groups_commands: Command = await api(
                gateway.get_groups(), timeout=TIMEOUT_API
            )
            groups = await api(groups_commands, timeout=TIMEOUT_API)

    except PytradfriError as exc:
        await factory.shutdown()
        raise ConfigEntryNotReady from exc

    dev_reg = await hass.helpers.device_registry.async_get_registry()
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={(DOMAIN, entry.data[CONF_GATEWAY_ID])},
        manufacturer=ATTR_TRADFRI_MANUFACTURER,
        name=ATTR_TRADFRI_GATEWAY,
        # They just have 1 gateway model. Type is not exposed yet.
        model=ATTR_TRADFRI_GATEWAY_MODEL,
        sw_version=gateway_info.firmware_version,
    )

    # Setup the device coordinators
    coordinator_data = {
        CONF_GATEWAY_ID: gateway,
        KEY_API: api,
        COORDINATOR_LIST: [],
        GROUPS_LIST: [],
    }

    for device in devices:
        coordinator = TradfriDeviceDataUpdateCoordinator(
            hass=hass, api=api, device=device
        )
        await coordinator.async_config_entry_first_refresh()

        entry.async_on_unload(
            async_dispatcher_connect(hass, SIGNAL_GW, coordinator.set_hub_available)
        )
        coordinator_data[COORDINATOR_LIST].append(coordinator)

    for group in groups:
        group_coordinator = TradfriGroupDataUpdateCoordinator(
            hass=hass, api=api, group=group
        )
        await group_coordinator.async_config_entry_first_refresh()
        entry.async_on_unload(
            async_dispatcher_connect(
                hass, SIGNAL_GW, group_coordinator.set_hub_available
            )
        )
        coordinator_data[GROUPS_LIST].append(group_coordinator)

    tradfri_data[COORDINATOR] = coordinator_data

    async def async_keep_alive(now: datetime) -> None:
        if hass.is_stopping:
            return

        gw_status = True
        try:
            await api(gateway.get_gateway_info())
        except RequestError:
            _LOGGER.error("Keep-alive failed")
            gw_status = False

        async_dispatcher_send(hass, SIGNAL_GW, gw_status)

    listeners.append(
        async_track_time_interval(hass, async_keep_alive, timedelta(seconds=60))
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        tradfri_data = hass.data[DOMAIN].pop(entry.entry_id)
        factory = tradfri_data[FACTORY]
        await factory.shutdown()
        # unsubscribe listeners
        for listener in tradfri_data[LISTENERS]:
            listener()

    return unload_ok
