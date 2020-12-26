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


def terncy_event_handler(t, ev):
    """Handle event from terncy system."""
    hass = t.hass_platform_data.hass
    parsed_devices = t.hass_platform_data.parsed_devices
    if isinstance(ev, terncy.event.Connected):
        _LOGGER.info("got connected event %s", t.dev_id)
        asyncio.ensure_future(async_refresh_devices(hass, t))
    if isinstance(ev, terncy.event.Disconnected):
        _LOGGER.info("got disconnected event %s", t.dev_id)
        for dev in parsed_devices.values():
            dev._available = False
            dev.schedule_update_ha_state()
    if isinstance(ev, terncy.event.EventMessage):
        _LOGGER.info("got event message %s %s", t.dev_id, ev.msg)
        evt_type = ""
        if "type" in ev.msg:
            evt_type = ev.msg["type"]
        if "entities" not in ev.msg:
            return
        ents = ev.msg["entities"]
        if evt_type == "report":
            for e in ents:
                if "attributes" not in e:
                    continue
                devid = e["id"]

                if devid in parsed_devices:
                    dev = parsed_devices[devid]
                    attrs = e["attributes"]
                    dev.update_state(attrs)
        elif evt_type == "entityAvailable":
            for e in ents:
                devid = e["id"]
                _LOGGER.info("[%s] %s is available", t.dev_id, devid)
                hass.async_create_task(update_or_create_entity(e, t))
        elif evt_type == "offline":
            for e in ents:
                devid = e["id"]
                _LOGGER.info("[%s] %s is offline", t.dev_id, devid)
                if devid in parsed_devices:
                    dev = parsed_devices[devid]
                    dev._available = False
                    dev.schedule_update_ha_state()
                elif devid.rfind("-") > 0:
                    prefix = devid[0 : devid.rfind("-")]
                    _LOGGER.info("[%s] %s not found, try find prefix", t.dev_id, prefix)
                    devs = find_dev_by_prefix(parsed_devices, prefix)
                    for d in devs:
                        _LOGGER.info("[%s] %s is offline", t.dev_id, d.unique_id)
                        d._available = False
                        d.schedule_update_ha_state()
        elif evt_type == "entityDeleted":
            platform = None
            for p in async_get_platforms(hass, DOMAIN):
                if p.config_entry.unique_id == t.dev_id:
                    if p.domain == "light":
                        platform = p
                        break
            if platform is None:
                return
            for e in ents:
                devid = e["id"]
                _LOGGER.info("[%s] %s is deleted", t.dev_id, devid)
                if devid in parsed_devices:
                    dev = parsed_devices[devid]
                    dev._available = False
                    dev.schedule_update_ha_state()
                elif devid.rfind("-") > 0:
                    prefix = devid[0 : devid.rfind("-")]
                    _LOGGER.info("[%s] %s not found, try find prefix", t.dev_id, prefix)
                    devs = find_dev_by_prefix(parsed_devices, prefix)
                    for d in devs:
                        _LOGGER.info("[%s] %s is delete", t.dev_id, d.unique_id)
                        hass.async_create_task(
                            platform.async_remove_entity(d.entity_id)
                        )
                        parsed_devices.pop(d.unique_id)
        else:
            _LOGGER.info("unsupported event type %s", evt_type)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Terncy component."""
    return True


def get_attr_value(attrs, key):
    """Read attr value from terncy attributes."""
    for a in attrs:
        if a["attr"] == key:
            return a["value"]
    return None


async def update_or_create_entity(dev, t):
    """Update or crate hass entity for given terncy device."""
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
        if devid in t.hass_platform_data.parsed_devices:
            light = t.hass_platform_data.parsed_devices[devid]
        else:
            light = TerncyLight(t, devid, name, model, version, features)
        on = get_attr_value(svc["attributes"], "on")
        if on is not None:
            light._onoff = on == 1
        bri = get_attr_value(svc["attributes"], "brightness")
        if bri:
            light._bri = int(bri / 100 * 255)
        ct = get_attr_value(svc["attributes"], "colorTemperature")
        if ct:
            light._ct = ct
        hue = get_attr_value(svc["attributes"], "hue")
        sat = get_attr_value(svc["attributes"], "saturation")
        if hue is not None and sat is not None:
            hue = hue / 255 * 360.0
            sat = sat / 255 * 100
            light._hs = (hue, sat)
        light._available = available
        if devid in t.hass_platform_data.parsed_devices:
            light.schedule_update_ha_state()
        else:
            platform = None
            for platform in async_get_platforms(t.hass_platform_data.hass, DOMAIN):
                if platform.config_entry.unique_id == t.dev_id:
                    if platform.domain == "light":
                        await platform.async_add_entities([light])
            t.hass_platform_data.parsed_devices[devid] = light


async def async_refresh_devices(hass: HomeAssistant, t):
    """Get devices from terncy."""
    _LOGGER.debug("refresh devices now")
    response = await t.get_entities("device", True)
    devices = response["rsp"]["entities"]
    pd = t.hass_platform_data

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=pd.hub_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, pd.mac)},
        identifiers={(DOMAIN, pd.hub_entry.entry_id)},
        manufacturer=TERNCY_MANU_NAME,
        name=pd.hub_entry.title,
        model="TERNCY-GW01",
        sw_version=1,
    )

    for dev in devices:
        await update_or_create_entity(dev, t)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Terncy from a config entry."""
    _LOGGER.debug("terncy domain async_setup_entry")
    _LOGGER.debug(entry.unique_id)
    _LOGGER.debug(entry.title)
    _LOGGER.debug(entry.data)
    dev_id = entry.data["identifier"]
    hass.data[DOMAIN] = {}
    mgr = TerncyHubManager.instance(hass)
    await mgr.start_discovery()

    t = terncy.Terncy(
        HA_CLIENT_ID,
        dev_id,
        entry.data["host"],
        entry.data["port"],
        entry.data["username"],
        entry.data["token"],
    )

    pd = TerncyHassPlatformData()

    pd.hass = hass
    pd.hub_entry = entry
    pd.mac = dr.format_mac(entry.unique_id.replace(TERNCY_HUB_ID_PREFIX, ""))
    t.hass_platform_data = pd
    hass.data[DOMAIN][entry.entry_id] = t

    async def setup_terncy_loop():
        asyncio.create_task(t.start())

    async def on_hass_stop(event):
        """Stop push updates when hass stops."""
        _LOGGER.info("terncy domain stop")
        await t.stop()

    async def on_terncy_svc_add(event):
        """Stop push updates when hass stops."""
        dev_id = event.data["dev_id"]
        _LOGGER.debug("found terncy service: %s %s", dev_id, event.data)
        host = event.data["ip"]
        if dev_id == t.dev_id and t._connection is None:
            t.host = host
            _LOGGER.info("start connection to %s %s", dev_id, t.host)

            hass.async_create_task(setup_terncy_loop())

    async def on_terncy_svc_remove(event):
        """Stop push updates when hass stops."""
        dev_id = event.data["dev_id"]
        _LOGGER.info("terncy svc remove %s", dev_id)
        if t._connection is not None:
            await t.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    hass.bus.async_listen(TERNCY_EVENT_SVC_ADD, on_terncy_svc_add)

    manager = TerncyHubManager.instance(hass)
    if dev_id in manager.hubs:
        if t._connection is None:
            t.host = manager.hubs[dev_id]["ip"]
            _LOGGER.info("start connection to %s %s", dev_id, t.host)
            hass.async_create_task(setup_terncy_loop())

    t.register_event_handler(terncy_event_handler)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(pd.hub_entry, component)
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
