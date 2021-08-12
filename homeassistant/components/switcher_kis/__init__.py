"""The Switcher integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioswitcher.device import SwitcherBase
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry,
    update_coordinator,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_DEVICE_PASSWORD,
    CONF_PHONE_ID,
    DATA_DEVICE,
    DATA_DISCOVERY,
    DOMAIN,
    MAX_UPDATE_INTERVAL_SEC,
    SIGNAL_DEVICE_ADD,
)
from .utils import async_start_bridge, async_stop_bridge

PLATFORMS = ["switch", "sensor"]

_LOGGER = logging.getLogger(__name__)

CCONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_PHONE_ID): cv.string,
                    vol.Required(CONF_DEVICE_ID): cv.string,
                    vol.Required(CONF_DEVICE_PASSWORD): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the switcher component."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Switcher from a config entry."""
    hass.data[DOMAIN][DATA_DEVICE] = {}

    @callback
    def on_device_data_callback(device: SwitcherBase) -> None:
        """Use as a callback for device data."""

        # Existing device update device data
        if device.device_id in hass.data[DOMAIN][DATA_DEVICE]:
            wrapper: SwitcherDeviceWrapper = hass.data[DOMAIN][DATA_DEVICE][
                device.device_id
            ]
            wrapper.async_set_updated_data(device)
            return

        # New device - create device
        _LOGGER.info(
            "Discovered Switcher device - id: %s, name: %s, type: %s (%s)",
            device.device_id,
            device.name,
            device.device_type.value,
            device.device_type.hex_rep,
        )

        wrapper = hass.data[DOMAIN][DATA_DEVICE][
            device.device_id
        ] = SwitcherDeviceWrapper(hass, entry, device)
        hass.async_create_task(wrapper.async_setup())

    async def platforms_setup_task() -> None:
        # Must be ready before dispatcher is called
        for platform in PLATFORMS:
            await hass.config_entries.async_forward_entry_setup(entry, platform)

        discovery_task = hass.data[DOMAIN].pop(DATA_DISCOVERY, None)
        if discovery_task is not None:
            discovered_devices = await discovery_task
            for device in discovered_devices.values():
                on_device_data_callback(device)

        await async_start_bridge(hass, on_device_data_callback)

    hass.async_create_task(platforms_setup_task())

    @callback
    async def stop_bridge(event: Event) -> None:
        await async_stop_bridge(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_bridge)

    return True


class SwitcherDeviceWrapper(update_coordinator.DataUpdateCoordinator):
    """Wrapper for a Switcher device with Home Assistant specific functions."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, device: SwitcherBase
    ) -> None:
        """Initialize the Switcher device wrapper."""
        super().__init__(
            hass,
            _LOGGER,
            name=device.name,
            update_interval=timedelta(seconds=MAX_UPDATE_INTERVAL_SEC),
        )
        self.hass = hass
        self.entry = entry
        self.data = device

    async def _async_update_data(self) -> None:
        """Mark device offline if no data."""
        raise update_coordinator.UpdateFailed(
            f"Device {self.name} did not send update for {MAX_UPDATE_INTERVAL_SEC} seconds"
        )

    @property
    def model(self) -> str:
        """Switcher device model."""
        return self.data.device_type.value  # type: ignore[no-any-return]

    @property
    def device_id(self) -> str:
        """Switcher device id."""
        return self.data.device_id  # type: ignore[no-any-return]

    @property
    def mac_address(self) -> str:
        """Switcher device mac address."""
        return self.data.mac_address  # type: ignore[no-any-return]

    async def async_setup(self) -> None:
        """Set up the wrapper."""
        dev_reg = await device_registry.async_get_registry(self.hass)
        dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            connections={(device_registry.CONNECTION_NETWORK_MAC, self.mac_address)},
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Switcher",
            name=self.name,
            model=self.model,
        )
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_ADD, self)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await async_stop_bridge(hass)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(DATA_DEVICE)

    return unload_ok
