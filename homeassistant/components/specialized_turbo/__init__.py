"""Specialized Turbo BLE integration for Home Assistant."""

import logging

from specialized_turbo import BikeAdvertisement, BLEProfile, ProtocolEncryptionMethod

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_HMI_HARDWARE, CONF_HMI_SERIAL, CONF_WRAPPED_KEY
from .coordinator import SpecializedTurboCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type SpecializedTurboConfigEntry = ConfigEntry[SpecializedTurboCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SpecializedTurboConfigEntry
) -> bool:
    """Set up Specialized Turbo from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    wrapped_key: str | None = entry.data.get(CONF_WRAPPED_KEY)
    hmi_hardware: str | None = entry.data.get(CONF_HMI_HARDWARE)
    hmi_serial: str | None = entry.data.get(CONF_HMI_SERIAL)
    advertisement = (
        BikeAdvertisement(
            generation=BLEProfile.TCX,
            encryption=ProtocolEncryptionMethod.AES_CTR,
            hmi_hardware=hmi_hardware,
            hmi_serial=hmi_serial,
        )
        if hmi_hardware is not None and hmi_serial is not None
        else None
    )

    def request_reauth(current_advertisement: BikeAdvertisement) -> None:
        """Update encryption metadata and start reauthentication."""
        data = dict(entry.data)
        if current_advertisement.hmi_hardware is not None:
            data[CONF_HMI_HARDWARE] = current_advertisement.hmi_hardware
        if current_advertisement.hmi_serial is not None:
            data[CONF_HMI_SERIAL] = current_advertisement.hmi_serial
        hass.config_entries.async_update_entry(entry, data=data)
        entry.async_start_reauth(hass)

    coordinator = SpecializedTurboCoordinator(
        hass,
        _LOGGER,
        address=address,
        wrapped_key=wrapped_key,
        advertisement=advertisement,
        reauth_callback=request_reauth,
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The coordinator connects and subscribes when the first advertisement arrives.
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SpecializedTurboConfigEntry
) -> bool:
    """Unload a Specialized Turbo config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.async_shutdown()

    return unload_ok
