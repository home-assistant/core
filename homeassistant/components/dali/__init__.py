"""The Tridonic DALI integration."""

from dali.driver.serial import DriverLubaRs232
from dali.exceptions import TransmissionError

from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .const import CONF_BUS_POWER, DOMAIN, GEAR_ID_INFIX
from .coordinator import DaliConfigEntry, DaliCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: DaliConfigEntry) -> None:
    """Set up Tridonic DALI from a config entry."""
    driver = DriverLubaRs232(
        uri=f"luba232:{entry.data[CONF_DEVICE]}",
        bus_power=entry.data.get(CONF_BUS_POWER, False),
    )

    def _close_transport() -> None:
        """Close the interface's serial transport if it was opened."""
        if transport := getattr(driver, "_transport", None):
            transport.close()

    # Registered before connecting so a failed or cancelled connect, first
    # refresh, or platform setup still closes the serial transport.
    entry.async_on_unload(_close_transport)
    try:
        # Only control gear is used, so skip the control-device instance scan
        # that would broadcast quiescent mode and interrupt DALI-2 input devices.
        await driver.connect(scan_dev_inst=False)
    except (TransmissionError, OSError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    coordinator = DaliCoordinator(hass, driver, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: DaliConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: DaliConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Allow removing a device only when its address no longer responds."""
    # A failed setup (e.g. the interface unplugged on restart) leaves the entry
    # without runtime data, yet the device-removal API still calls this; allow
    # removal then, since there is no live bus state to check against.
    if not hasattr(entry, "runtime_data"):
        return True
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
