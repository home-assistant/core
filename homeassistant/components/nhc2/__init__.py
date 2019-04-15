"""Support for Niko Home Control II - CoCo."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, \
    CONF_PASSWORD
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from .config_flow import Nhc2FlowHandler  # noqa  pylint_disable=unused-import
from .const import DOMAIN, KEY_GATEWAY
from .helpers import extract_versions

_LOGGER = logging.getLogger(__name__)

DOMAIN = DOMAIN
KEY_GATEWAY = KEY_GATEWAY

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the NHC2 CoCo component."""
    conf = config.get(DOMAIN)

    if conf is None:
        return True

    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
        data={CONF_HOST: host, CONF_PORT: port,
              CONF_USERNAME: username,
              CONF_PASSWORD: password}
    ))

    return True


async def async_setup_entry(hass, entry):
    """Create a NHC2 gateway."""
    from nhc2_coco import CoCo

    coco = CoCo(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_PORT]
    )

    async def on_hass_stop(event):
        """Close connection when hass stops."""
        coco.disconnect()

    def get_process_sysinfo(dev_reg):
        def process_sysinfo(nhc2_sysinfo):
            coco_image, nhc_version = extract_versions(nhc2_sysinfo)
            _LOGGER.debug('Sysinfo: NhcVersion %s - CocoImage %s',
                          nhc_version,
                          coco_image)
            dev_reg.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections=set(),
                identifiers={
                    (DOMAIN, entry.data[CONF_USERNAME])
                },
                manufacturer='Niko',
                name='Home Control II',
                model='Connected controller',
                sw_version=nhc_version + ' - CoCo Image: ' + coco_image,
            )

            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    entry, 'light')
            )

            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    entry, 'switch')
            )
        return process_sysinfo

    hass.data.setdefault(KEY_GATEWAY, {})[entry.entry_id] = coco
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)

    _LOGGER.debug('Connecting to %s:%s',
                  entry.data[CONF_HOST],
                  str(entry.data[CONF_PORT])
                  )
    coco.connect()
    dev_reg = await hass.helpers.device_registry.async_get_registry()
    coco.get_systeminfo(get_process_sysinfo(dev_reg))

    return True
