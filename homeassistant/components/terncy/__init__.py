"""The Terncy integration."""
import asyncio
import logging

import terncy
import terncy.event
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import async_get_platforms

from .const import (
    DOMAIN,
    HA_CLIENT_ID,
    PROFILE_COLOR_DIMMABLE_LIGHT,
    PROFILE_COLOR_LIGHT,
    PROFILE_COLOR_TEMPERATURE_LIGHT,
    PROFILE_DIMMABLE_COLOR_TEMPERATURE_LIGHT,
    PROFILE_DIMMABLE_LIGHT,
    PROFILE_DIMMABLE_LIGHT2,
    PROFILE_EXTENDED_COLOR_LIGHT,
    PROFILE_EXTENDED_COLOR_LIGHT2,
    PROFILE_ONOFF_LIGHT,
    TERNCY_EVENT_SVC_ADD,
    TERNCY_EVENT_SVC_REMOVE,
    TERNCY_HUB_ID_PREFIX,
    TERNCY_MANU_NAME,
    TerncyHassPlatformData,
)
from .hub_monitor import TerncyHubManager
from .light import (
    SUPPORT_TERNCY_COLOR,
    SUPPORT_TERNCY_CT,
    SUPPORT_TERNCY_DIMMABLE,
    SUPPORT_TERNCY_EXTENDED,
    SUPPORT_TERNCY_ON_OFF,
    TerncyLight,
)

PLATFORM_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["light"]

_LOGGER = logging.getLogger(__name__)


def find_dev_by_prefix(devices, prefix):
    """Find device with given prefix."""
    result = []
    for dev in devices.values():
        if dev.unique_id.startswith(prefix):
            result.append(dev)
    return result


def terncy_event_handler(tern, ev):
    """Handle event from terncy system."""
    hass = tern.hass_platform_data.hass
    parsed_devices = tern.hass_platform_data.parsed_devices
    if isinstance(ev, terncy.event.Connected):
        _LOGGER.info("got connected event %s", tern.dev_id)
        asyncio.ensure_future(async_refresh_devices(hass, tern))
    if isinstance(ev, terncy.event.Disconnected):
        _LOGGER.info("got disconnected event %s", tern.dev_id)
        for dev in parsed_devices.values():
            dev.is_available = False
            dev.schedule_update_ha_state()
    if isinstance(ev, terncy.event.EventMessage):
        _LOGGER.info("got event message %s %s", tern.dev_id, ev.msg)
        evt_type = ""
        if "type" in ev.msg:
            evt_type = ev.msg["type"]
        if "entities" not in ev.msg:
            return
        ents = ev.msg["entities"]
        if evt_type == "report":
            for ent in ents:
                if "attributes" not in ent:
                    continue
                devid = ent["id"]

                if devid in parsed_devices:
                    dev = parsed_devices[devid]
                    attrs = ent["attributes"]
                    dev.update_state(attrs)
                    dev.schedule_update_ha_state()
        elif evt_type == "entityAvailable":
            for ent in ents:
                devid = ent["id"]
                _LOGGER.info("[%s] %s is available", tern.dev_id, devid)
                hass.async_create_task(update_or_create_entity(ent, tern))
        elif evt_type == "offline":
            for ent in ents:
                devid = ent["id"]
                _LOGGER.info("[%s] %s is offline", tern.dev_id, devid)
                if devid in parsed_devices:
                    dev = parsed_devices[devid]
                    dev.is_available = False
                    dev.schedule_update_ha_state()
                elif devid.rfind("-") > 0:
                    prefix = devid[0 : devid.rfind("-")]
                    _LOGGER.info(
                        "[%s] %s not found, try find prefix", tern.dev_id, prefix
                    )
                    devs = find_dev_by_prefix(parsed_devices, prefix)
                    for dev in devs:
                        _LOGGER.info("[%s] %s is offline", tern.dev_id, dev.unique_id)
                        dev.is_available = False
                        dev.schedule_update_ha_state()
        elif evt_type == "entityDeleted":
            platform = None
            for plat in async_get_platforms(hass, DOMAIN):
                if plat.config_entry.unique_id == tern.dev_id:
                    if plat.domain == "light":
                        platform = plat
                        break
            if platform is None:
                return
            for ent in ents:
                devid = ent["id"]
                _LOGGER.info("[%s] %s is deleted", tern.dev_id, devid)
                if devid in parsed_devices:
                    dev = parsed_devices[devid]
                    dev.is_available = False
                    dev.schedule_update_ha_state()
                elif devid.rfind("-") > 0:
                    prefix = devid[0 : devid.rfind("-")]
                    _LOGGER.info(
                        "[%s] %s not found, try find prefix", tern.dev_id, prefix
                    )
                    devs = find_dev_by_prefix(parsed_devices, prefix)
                    for dev in devs:
                        _LOGGER.info("[%s] %s is delete", tern.dev_id, dev.unique_id)
                        hass.async_create_task(
                            platform.async_remove_entity(dev.entity_id)
                        )
                        parsed_devices.pop(dev.unique_id)
        else:
            _LOGGER.info("unsupported event type %s", evt_type)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Terncy component."""
    return True


async def update_or_create_entity(dev, tern):
    """Update or create hass entity for given terncy device."""
    model = dev["model"] if "model" in dev else ""
    version = dev["version"] if "version" in dev else ""
    available = dev["online"] if "online" in dev else False
    if "services" not in dev:
        return []
    for svc in dev["services"]:
        profile = svc["profile"]
        features = -1
        if profile == PROFILE_ONOFF_LIGHT:
            features = SUPPORT_TERNCY_ON_OFF
        elif profile == PROFILE_COLOR_LIGHT:
            features = SUPPORT_TERNCY_COLOR
        elif profile == PROFILE_EXTENDED_COLOR_LIGHT:
            features = SUPPORT_TERNCY_EXTENDED
        elif profile == PROFILE_COLOR_TEMPERATURE_LIGHT:
            features = SUPPORT_TERNCY_CT
        elif profile == PROFILE_DIMMABLE_COLOR_TEMPERATURE_LIGHT:
            features = SUPPORT_TERNCY_CT
        elif profile == PROFILE_DIMMABLE_LIGHT:
            features = SUPPORT_TERNCY_DIMMABLE
        elif profile == PROFILE_DIMMABLE_LIGHT2:
            features = SUPPORT_TERNCY_DIMMABLE
        elif profile == PROFILE_COLOR_DIMMABLE_LIGHT:
            features = SUPPORT_TERNCY_EXTENDED
        elif profile == PROFILE_EXTENDED_COLOR_LIGHT2:
            features = SUPPORT_TERNCY_EXTENDED
        else:
            _LOGGER.info("unsupported profile %d", profile)
            return []

        devid = svc["id"]
        name = svc["name"]
        if name == "":
            name = devid
        light = None
        if devid in tern.hass_platform_data.parsed_devices:
            light = tern.hass_platform_data.parsed_devices[devid]
        else:
            light = TerncyLight(tern, devid, name, model, version, features)
        light.update_state(svc["attributes"])
        light.is_available = available
        if devid in tern.hass_platform_data.parsed_devices:
            light.schedule_update_ha_state()
        else:
            platform = None
            for platform in async_get_platforms(tern.hass_platform_data.hass, DOMAIN):
                if platform.config_entry.unique_id == tern.dev_id:
                    if platform.domain == "light":
                        await platform.async_add_entities([light])
            tern.hass_platform_data.parsed_devices[devid] = light


async def async_refresh_devices(hass: HomeAssistant, tern):
    """Get devices from terncy."""
    _LOGGER.info("refresh devices now")
    response = await tern.get_entities("device", True)
    devices = response["rsp"]["entities"]
    pdata = tern.hass_platform_data

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=pdata.hub_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, pdata.mac)},
        identifiers={(DOMAIN, pdata.hub_entry.entry_id)},
        manufacturer=TERNCY_MANU_NAME,
        name=pdata.hub_entry.title,
        model="TERNCY-GW01",
        sw_version=1,
    )

    for dev in devices:
        await update_or_create_entity(dev, tern)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Terncy from a config entry."""
    _LOGGER.info("terncy domain async_setup_entry %s", entry.unique_id)
    dev_id = entry.data["identifier"]
    hass.data[DOMAIN] = {}
    mgr = TerncyHubManager.instance(hass)
    await mgr.start_discovery()

    tern = terncy.Terncy(
        HA_CLIENT_ID,
        dev_id,
        entry.data["host"],
        entry.data["port"],
        entry.data["username"],
        entry.data["token"],
    )

    pdata = TerncyHassPlatformData()

    pdata.hass = hass
    pdata.hub_entry = entry
    pdata.mac = dr.format_mac(entry.unique_id.replace(TERNCY_HUB_ID_PREFIX, ""))
    tern.hass_platform_data = pdata
    hass.data[DOMAIN][entry.entry_id] = tern

    async def setup_terncy_loop():
        asyncio.create_task(tern.start())

    async def on_hass_stop(event):
        """Stop push updates when hass stops."""
        _LOGGER.info("terncy domain stop")
        await tern.stop()

    async def on_terncy_svc_add(event):
        """Stop push updates when hass stops."""
        dev_id = event.data["dev_id"]
        _LOGGER.info("found terncy service: %s %s", dev_id, event.data)
        host = event.data["ip"]
        if dev_id == tern.dev_id and not tern.is_connected():
            tern.host = host
            _LOGGER.info("start connection to %s %s", dev_id, tern.host)

            hass.async_create_task(setup_terncy_loop())

    async def on_terncy_svc_remove(event):
        """Stop push updates when hass stops."""
        dev_id = event.data["dev_id"]
        _LOGGER.info("terncy svc remove %s", dev_id)
        if not tern.is_connected():
            await tern.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    hass.bus.async_listen(TERNCY_EVENT_SVC_ADD, on_terncy_svc_add)
    hass.bus.async_listen(TERNCY_EVENT_SVC_REMOVE, on_terncy_svc_remove)

    manager = TerncyHubManager.instance(hass)
    if dev_id in manager.hubs:
        if not tern.is_connected():
            tern.host = manager.hubs[dev_id]["ip"]
            _LOGGER.info("start connection to %s %s", dev_id, tern.host)
            hass.async_create_task(setup_terncy_loop())

    tern.register_event_handler(terncy_event_handler)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(pdata.hub_entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
