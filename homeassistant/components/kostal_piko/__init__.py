"""The Kostal Piko Solar Inverter integration."""
from __future__ import annotations

from pykostalpiko.Inverter import Piko
from pykostalpiko.dxs import Entries

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kostal Piko Solar Inverter from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    piko = Piko(
        async_get_clientsession(hass),
        entry.data.get(CONF_HOST),
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )

    hass.data[DOMAIN][entry.entry_id] = piko

    device_registry = dr.async_get(hass)

    data = await piko.async_fetch(
        Entries.InverterName,
        Entries.InverterType,
        Entries.VersionUI,
        Entries.VersionFW,
        Entries.VersionHW,
        Entries.VersionPAR,
        Entries.SerialNumber,
        Entries.ArticleNumber,
        Entries.CountrySettingsName,
        Entries.CountrySettingsVersion,
    )

    # pylint: disable=no-member
    name: str = data[Entries.InverterName.name]
    # pylint: disable=no-member
    model: str = data[Entries.InverterType.name]
    # pylint: disable=no-member
    version_ui: str = data[Entries.VersionUI.name]
    # pylint: disable=no-member
    version_fw: str = data[Entries.VersionFW.name]
    # pylint: disable=no-member
    version_hw: str = data[Entries.VersionHW.name]
    # pylint: disable=no-member
    version_par: str = data[Entries.VersionPAR.name]
    # pylint: disable=no-member
    serial_number: str = data[Entries.SerialNumber.name]

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        default_manufacturer="Kostal",
        name=name,
        model=model,
        identifiers={(DOMAIN, serial_number)},
        sw_version=f"UI: {version_ui} FW: {version_fw} PAR: {version_par}",
        hw_version=version_hw,
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
