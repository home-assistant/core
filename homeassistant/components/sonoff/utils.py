import logging
import re
import uuid
from datetime import datetime
from typing import List

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.typing import HomeAssistantType

try:  # support old Home Assistant version
    from homeassistant.components.binary_sensor import BinarySensorEntity
except:
    from homeassistant.components.binary_sensor import \
        BinarySensorDevice as BinarySensorEntity

try:  # support old Home Assistant version
    from homeassistant.components.cover import CoverEntity
except:
    from homeassistant.components.cover import CoverDevice as CoverEntity

_LOGGER = logging.getLogger(__name__)


def init_zeroconf_singleton(hass):
    """Generate only one Zeroconf. Component must be loaded before Zeroconf."""
    from homeassistant.components import zeroconf
    if isinstance(zeroconf.Zeroconf, type):
        def zeroconf_singleton():
            if 'zeroconf' not in hass.data:
                from zeroconf import Zeroconf
                _LOGGER.debug("Generate zeroconf singleton")
                hass.data['zeroconf'] = Zeroconf()
            else:
                _LOGGER.debug("Use zeroconf singleton")
            return hass.data['zeroconf']

        _LOGGER.debug("Init zeroconf singleton")
        zeroconf.Zeroconf = zeroconf_singleton


UIIDS = {}


def init_device_class(default_class: str = 'switch'):
    switch1 = default_class
    switch2 = [default_class, default_class]
    switch3 = [default_class, default_class, default_class]
    switch4 = [default_class, default_class, default_class, default_class]
    switchx = [default_class]

    UIIDS.update({
        # list cloud uiids
        1: switch1,
        2: switch2,
        3: switch3,
        4: switch4,
        5: switch1,  # Sonoff Pow
        6: switch1,
        7: switch2,  # Sonoff T1 2C
        8: switch3,  # Sonoff T1 3C
        9: switch4,
        11: 'cover',  # King Art - King Q4 Cover (only cloud)
        # 14 Sonoff Basic
        # 15 Sonoff TH16
        18: 'sensor',  # Sonoff SC
        22: 'light',  # Sonoff B1 (only cloud)
        25: ['fan', 'light'],  # Diffuser
        28: 'remote',  # Sonoff RF Brigde 433
        29: switch2,
        30: switch3,
        31: switch4,
        34: ['light', {'fan': [2, 3, 4]}],  # Sonoff iFan02 and iFan03
        36: 'light',  # KING-M4 (dimmer, only cloud)
        44: 'light',  # Sonoff D1
        59: 'light',  # Sonoff LED (only cloud)
        77: switchx,  # Sonoff Micro
        78: switchx,
        81: switch1,
        82: switch2,
        83: switch3,
        84: switch4,
        102: 'binary_sensor',  # Sonoff DW2 Door/Window sensor
        107: switchx,
        # list local types
        'plug': switch1,  # Basic, Mini
        'diy_plug': switch1,  # Mini in DIY mode
        'enhanced_plug': switch1,  # Sonoff Pow R2?
        'th_plug': switch1,  # Sonoff TH?
        'strip': switch4,  # 4CH Pro R2, Micro!, iFan02!
        'light': 'light',  # D1
        'rf': 'remote',  # RF Bridge 433
        'fan_light': ['light', {'fan': [2, 3, 4]}],  # iFan03
    })


def guess_device_class(config: dict):
    """Get device_class from uiid (from eWeLink Servers) or from zeroconf type.

    Sonoff iFan02 and iFan03 both have uiid 34. But different types (strip and
    fan_light) and different local API for each type. Without uiid iFan02 will
    be displayed as 4 switches.
    """
    uiid = config.get('uiid')
    return UIIDS.get(uiid)


def get_device_info(config: dict):
    try:
        # https://developers.home-assistant.io/docs/device_registry_index/
        return {
            'manufacturer': config['brandName'],
            'model': config['productModel'],
            'sw_version': f"{config['extra']['extra']['model']} "
                          f"v{config['params'].get('fwVersion', '???')}"
        }
    except:
        return None


def parse_multichannel_class(device_class: list) -> List[dict]:
    """Supported device_class formats:

        device_class: [light, fan]  # version 1
        device_class:  # version 2
        - light  # zone 1 (channel 1)
        - light  # zone 2 (channel 2)
        - light: [3, 4]  # zone 3 (channels 3 and 4)
        device_class:  # version 3 (legacy)
        - light # zone 1 (channel 1)
        - light # zone 2 (channel 2)
        - device_class: light # zone 3 (channels 3 и 4)
          channels: [3, 4]
    """
    entities = []

    # read multichannel device_class
    for i, component in enumerate(device_class, 1):
        # read device with several channels
        if isinstance(component, dict):
            if 'device_class' in component:
                # backward compatibility
                channels = component['channels']
                component = component['device_class']
            else:
                component, channels = list(component.items())[0]

            if isinstance(channels, int):
                channels = [channels]
        else:
            channels = [i]

        entities.append({'component': component, 'channels': channels})

    return entities


def handle_cloud_error(hass: HomeAssistantType):
    """Show persistent notification if cloud error occurs."""
    from .sonoff_cloud import _LOGGER, CLOUD_ERROR

    class CloudError(logging.Handler):
        def handle(self, rec: logging.LogRecord) -> None:
            if rec.msg == CLOUD_ERROR:
                hass.components.persistent_notification.async_create(
                    rec.msg, title="Sonoff Warning")

    _LOGGER.addHandler(CloudError())


RE_DEVICEID = re.compile(r"^[a-z0-9]{10}\b")
# remove uiid, MAC, IP
RE_PRIVATE = re.compile(
    r"\b([a-zA-Z0-9_-]{36,}|[A-F0-9:]{17}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"EWLK-\d{6}-[A-Z]{5})\b")
NOTIFY_TEXT = (
    '<a href="%s" target="_blank">Open Log<a> | '
    '[New Issue on GitHub](https://github.com/AlexxIT/SonoffLAN/issues/new) | '
    '[sonofflan@gmail.com](mailto:sonofflan@gmail.com)')

HTML = ('<!DOCTYPE html><html><head><title>Sonoff Debug</title>'
        '<meta http-equiv="refresh" content="%s"></head>'
        '<body><pre>%s</pre></body></html>')


class SonoffDebug(logging.Handler, HomeAssistantView):
    name = "sonoff_debug"
    requires_auth = False

    text = ''

    def __init__(self, hass: HomeAssistantType):
        super().__init__()

        # random url because without authorization!!!
        self.url = f"/{uuid.uuid4()}"

        hass.http.register_view(self)
        hass.components.persistent_notification.async_create(
            NOTIFY_TEXT % self.url, title="Sonoff Debug")

    def handle(self, rec: logging.LogRecord) -> None:
        dt = datetime.fromtimestamp(rec.created).strftime("%Y-%m-%d %H:%M:%S")
        module = 'main' if rec.module == '__init__' else rec.module
        # remove private data
        # TODO: fix single IP address
        msg = RE_PRIVATE.sub("...", str(rec.msg))
        self.text += f"{dt}  {rec.levelname:7}  {module:12}  {msg}\n"

    async def get(self, request: web.Request):
        reload = request.query.get('r', '')

        if 'q' in request.query:
            try:
                reg = re.compile(fr"({request.query['q']})", re.IGNORECASE)
                body = '\n'.join([p for p in self.text.split('\n')
                                  if reg.search(p)])
            except:
                return web.Response(status=500)
        else:
            body = None

        return web.Response(text=HTML % (reload, body or self.text),
                            content_type="text/html")
