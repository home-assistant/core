"""Adaptive Lighting integration in Home-Assistant.

This integration calculates color temperature and brightness to synchronize
your color-changing lights with the perceived color temperature of the sky
throughout the day. This gives your environment a more natural feel, with
cooler whites during the midday and warmer tints near twilight and dawn.

Additionally, the integration sets your lights to a nice warm white at 1% in
"Sleep mode", which is far brighter than starlight but won't reset your
circadian rhythm or break down too much rhodopsin in your eyes.

Human circadian rhythms are heavily influenced by ambient light levels and
hues. Hormone production, brainwave activity, mood, and wakefulness are
just some of the cognitive functions tied to cyclical natural light.

Resources:
- http://en.wikipedia.org/wiki/Zeitgeber
- http://www.cambridgeincolour.com/tutorials/sunrise-sunset-calculator.htm
- http://en.wikipedia.org/wiki/Color_temperature

## Notes
* Only your location is taken into account to calculate the the sun's position.
* Weather is not considered.
* The integration does not calculate a true "Blue Hour" -- it just sets the
  lights to 2700K (warm white) until your hub goes into "Sleep mode".
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
import homeassistant.helpers.config_validation as cv

from .const import _DOMAIN_SCHEMA, CONF_NAME, DOMAIN, UNDO_UPDATE_LISTENER

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]


def _all_unique_names(value):
    """Validate that all enties have a unique profile name."""
    hosts = [device[CONF_NAME] for device in value]
    schema = vol.Schema(vol.Unique())
    schema(hosts)
    return value


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_DOMAIN_SCHEMA], _all_unique_names)},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Import integration from config."""

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )
    return True


async def async_setup_entry(hass, config_entry: ConfigEntry):
    """Set up the component."""
    data = hass.data.setdefault(DOMAIN, {})

    undo_listener = config_entry.add_update_listener(async_update_options)
    data[config_entry.entry_id] = {UNDO_UPDATE_LISTENER: undo_listener}
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_update_options(hass, config_entry: ConfigEntry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, "switch"
    )
    data = hass.data[DOMAIN]
    data[config_entry.entry_id][UNDO_UPDATE_LISTENER]()
    switch = data[config_entry.entry_id][SWITCH_DOMAIN]
    switch._unsub_trackers()  # pylint: disable=protected-access

    if unload_ok:
        data.pop(config_entry.entry_id)

    return unload_ok
