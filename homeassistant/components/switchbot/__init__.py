"""Support for Switchbot devices."""

import logging

import switchbot

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    CONF_RETRY_COUNT,
    CONNECTABLE_SUPPORTED_MODEL_TYPES,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
    HASS_SENSOR_TYPE_TO_SWITCHBOT_MODEL,
    SupportedModels,
)
from .coordinator import SwitchbotDataUpdateCoordinator

PLATFORMS_BY_TYPE = {
    SupportedModels.BULB.value: [Platform.SENSOR, Platform.LIGHT],
    SupportedModels.LIGHT_STRIP.value: [Platform.SENSOR, Platform.LIGHT],
    SupportedModels.CEILING_LIGHT.value: [Platform.SENSOR, Platform.LIGHT],
    SupportedModels.BOT.value: [Platform.SWITCH, Platform.SENSOR],
    SupportedModels.PLUG.value: [Platform.SWITCH, Platform.SENSOR],
    SupportedModels.CURTAIN.value: [
        Platform.COVER,
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    SupportedModels.HYGROMETER.value: [Platform.SENSOR],
    SupportedModels.CONTACT.value: [Platform.BINARY_SENSOR, Platform.SENSOR],
    SupportedModels.MOTION.value: [Platform.BINARY_SENSOR, Platform.SENSOR],
    SupportedModels.HUMIDIFIER.value: [Platform.HUMIDIFIER, Platform.SENSOR],
    SupportedModels.LOCK.value: [
        Platform.BINARY_SENSOR,
        Platform.LOCK,
        Platform.SENSOR,
    ],
    SupportedModels.BLIND_TILT.value: [
        Platform.COVER,
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
}
CLASS_BY_DEVICE = {
    SupportedModels.CEILING_LIGHT.value: switchbot.SwitchbotCeilingLight,
    SupportedModels.CURTAIN.value: switchbot.SwitchbotCurtain,
    SupportedModels.BOT.value: switchbot.Switchbot,
    SupportedModels.PLUG.value: switchbot.SwitchbotPlugMini,
    SupportedModels.BULB.value: switchbot.SwitchbotBulb,
    SupportedModels.LIGHT_STRIP.value: switchbot.SwitchbotLightStrip,
    SupportedModels.HUMIDIFIER.value: switchbot.SwitchbotHumidifier,
    SupportedModels.LOCK.value: switchbot.SwitchbotLock,
    SupportedModels.BLIND_TILT.value: switchbot.SwitchbotBlindTilt,
}


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Switchbot from a config entry."""
    assert entry.unique_id is not None
    hass.data.setdefault(DOMAIN, {})
    if CONF_ADDRESS not in entry.data and CONF_MAC in entry.data:
        # Bleak uses addresses not mac addresses which are actually
        # UUIDs on some platforms (MacOS).
        mac = entry.data[CONF_MAC]
        if "-" not in mac:
            mac = dr.format_mac(mac)
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ADDRESS: mac},
        )

    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
        )

    sensor_type: str = entry.data[CONF_SENSOR_TYPE]
    switchbot_model = HASS_SENSOR_TYPE_TO_SWITCHBOT_MODEL[sensor_type]
    # connectable means we can make connections to the device
    connectable = switchbot_model in CONNECTABLE_SUPPORTED_MODEL_TYPES
    address: str = entry.data[CONF_ADDRESS]

    await switchbot.close_stale_connections_by_address(address)

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Switchbot {sensor_type} with address {address}"
        )

    cls = CLASS_BY_DEVICE.get(sensor_type, switchbot.SwitchbotDevice)
    if cls is switchbot.SwitchbotLock:
        try:
            device = switchbot.SwitchbotLock(
                device=ble_device,
                key_id=entry.data.get(CONF_KEY_ID),
                encryption_key=entry.data.get(CONF_ENCRYPTION_KEY),
                retry_count=entry.options[CONF_RETRY_COUNT],
            )
        except ValueError as error:
            raise ConfigEntryNotReady(
                "Invalid encryption configuration provided"
            ) from error
    else:
        device = cls(
            device=ble_device,
            password=entry.data.get(CONF_PASSWORD),
            retry_count=entry.options[CONF_RETRY_COUNT],
        )

    coordinator = hass.data[DOMAIN][entry.entry_id] = SwitchbotDataUpdateCoordinator(
        hass,
        _LOGGER,
        ble_device,
        device,
        entry.unique_id,
        entry.data.get(CONF_NAME, entry.title),
        connectable,
        switchbot_model,
    )
    entry.async_on_unload(coordinator.async_start())
    if not await coordinator.async_wait_ready():
        raise ConfigEntryNotReady(f"{address} is not advertising state")

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    sensor_type = entry.data[CONF_SENSOR_TYPE]
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.config_entries.async_entries(DOMAIN):
            hass.data.pop(DOMAIN)

    return unload_ok
