"""The Tridonic DALI integration."""

from dali.driver.serial import DriverLubaRs232
from dali.exceptions import TransmissionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .const import CONF_BUS_POWER, DOMAIN, GEAR_ID_INFIX
from .coordinator import DaliCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


type DaliConfigEntry = ConfigEntry[DaliCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DaliConfigEntry) -> bool:
    """Set up Tridonic DALI from a config entry."""
    driver = DriverLubaRs232(
        uri=f"luba232:{entry.data[CONF_DEVICE]}",
        bus_power=entry.data.get(CONF_BUS_POWER, False),
    )
    try:
        await driver.connect(scan_dev_inst=True)
    except (TransmissionError, OSError, TimeoutError) as err:
        if transport := getattr(driver, "_transport", None):
            transport.close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    coordinator = DaliCoordinator(hass, driver, entry)
    entry.async_on_unload(coordinator.close)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DaliConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: DaliConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Allow removing a device only when its address no longer responds."""
    coordinator = entry.runtime_data
    gear_addresses = set(coordinator.data)
    gear_prefix = f"{entry.entry_id}_{GEAR_ID_INFIX}_"
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        address = identifier.removeprefix(gear_prefix)
        if address.isdigit() and int(address) in gear_addresses:
            return False
    return True
