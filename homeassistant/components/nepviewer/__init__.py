"""The NEPViewer integration."""

from aionepviewer import NepViewer

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import NepViewerConfigEntry, NepViewerCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NepViewerConfigEntry) -> None:
    """Set up NEPViewer from a config entry."""
    client = NepViewer(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = NepViewerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Parent devices must exist before via_device_id can refer to them
    device_registry = dr.async_get(hass)
    site_device_ids: dict[str, str] = {}
    for site in coordinator.data.sites:
        site_detail = coordinator.data.site_details.get(site.sid)
        site_device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, site.sid)},
            name=site.site_name,
            entry_type=dr.DeviceEntryType.SERVICE,
            manufacturer=(site_detail and site_detail.company_name) or "NEP",
            serial_number=(site_detail and site_detail.project_reference_id) or None,
        )
        site_device_ids[site.sid] = site_device.id
    for device in coordinator.data.devices:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.sn)},
            name=device.alias or device.sn,
            manufacturer="NEP",
            model=device.model_name or None,
            serial_number=device.sn,
            sw_version=" / ".join(
                filter(None, [device.cpu_version, device.wifi_version])
            )
            or None,
            via_device_id=site_device_ids.get(device.sid),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: NepViewerConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
