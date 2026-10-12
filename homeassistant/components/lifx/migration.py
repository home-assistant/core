"""Migrate the stored form of a LIFX serial."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import LIFXConfigEntry
from .util import normalize_serial


def _raw_serial(value: str) -> str:
    """Return a serial in raw form, leaving an unrecognized value alone."""
    try:
        return normalize_serial(value)
    except ValueError:
        return value


@callback
def _raw_identifiers(identifiers: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Return the identifiers of a device with its serial in raw form."""
    return {
        (domain, _raw_serial(value) if domain == DOMAIN else value)
        for domain, value in identifiers
    }


@callback
def _raw_unique_id(reg_entity: er.RegistryEntry) -> dict[str, str] | None:
    """Return the update that puts the serial of a unique ID in raw form."""
    serial, separator, key = reg_entity.unique_id.partition("_")
    if (raw_serial := _raw_serial(serial)) == serial:
        return None
    return {"new_unique_id": f"{raw_serial}{separator}{key}"}


async def async_migrate_serials(hass: HomeAssistant, entry: LIFXConfigEntry) -> None:
    """Replace the MAC-formatted serials an entry registered with the actual serial.

    A LIFX serial is not a MAC address and earlier releases stored it colon
    separated, which the device registry then treated as a second identity.
    """
    device_registry = dr.async_get(hass)
    for dev_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if (
            identifiers := _raw_identifiers(dev_entry.identifiers)
        ) != dev_entry.identifiers:
            device_registry.async_update_device(
                dev_entry.id, new_identifiers=identifiers
            )
    await er.async_migrate_entries(hass, entry.entry_id, _raw_unique_id)
