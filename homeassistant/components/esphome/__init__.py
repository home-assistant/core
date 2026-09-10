"""Support for esphome devices."""

import logging

from aioesphomeapi import APIConnectionError, SerialProxyPortType
from serialx import SerialPortInfo

from homeassistant.components import zeroconf
from homeassistant.components.bluetooth import async_remove_scanner
from homeassistant.components.usb import (
    SerialDevice,
    USBDevice,
    async_register_serial_port_scanner,
    usb_serial_device_from_port,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import async_delete_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from . import assist_satellite, dashboard, ffmpeg_proxy, serial_proxy
from .const import CONF_BLUETOOTH_MAC_ADDRESS, CONF_NOISE_PSK, DOMAIN
from .domain_data import DomainData
from .encryption_key_storage import async_get_encryption_key_storage
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData
from .manager import (
    DEVICE_CONFLICT_ISSUE_FORMAT,
    ESPHomeManager,
    async_create_api_client,
    async_get_manufacturer_model,
    cleanup_instance,
)
from .websocket_api import async_setup as async_setup_websocket_api

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@callback
def _async_scan_serial_ports(
    hass: HomeAssistant,
) -> list[USBDevice | SerialDevice]:
    """Return serial-proxy ports exposed by connected ESPHome devices."""
    ports: list[USBDevice | SerialDevice] = []

    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        entry_data = entry.runtime_data
        if not entry_data.available:
            continue

        device_info = entry_data.device_info
        if device_info is None:
            continue

        usb_infos = entry_data.serial_proxy_usb_info

        for instance, proxy in enumerate(device_info.serial_proxies):
            if proxy.port_type is not SerialProxyPortType.USB_SERIAL:
                manufacturer, model = async_get_manufacturer_model(device_info)

                # A pin-header UART, where the port itself is the device
                ports.append(
                    SerialDevice(
                        device=str(serial_proxy.build_url(entry.entry_id, proxy.name)),
                        serial_number=(
                            device_info.mac_address.replace(":", "")
                            + "-"
                            + slugify(proxy.name)
                        ),
                        manufacturer=manufacturer,
                        description=f"{model} ({proxy.name})",
                    )
                )
                continue

            if instance not in usb_infos or not usb_infos[instance].connected:
                # An empty socket, or one not yet asked about. Offering it would be like
                # listing a /dev node for an adapter that has been unplugged: nothing can
                # be done with it, and a client that stored a path to the device that
                # used to be here should be told it is gone rather than handed a port
                # that answers nothing.
                continue

            usb = usb_infos[instance]
            url = str(
                serial_proxy.build_url(
                    entry.entry_id,
                    proxy.name,
                    usb.serial_number or None,
                    # Spelled the way USBDevice spells them
                    vid=f"{usb.vendor_id:04X}",
                    pid=f"{usb.product_id:04X}",
                )
            )

            # A USB port is a socket, so the device in it is what callers care about.
            # Reported through the same converter a local port goes through, so an adapter
            # reached this way is described exactly as it would be when plugged into the
            # host: the existing USB matchers recognize it, and its identity does not
            # change when it moves between the two.
            ports.append(
                usb_serial_device_from_port(
                    SerialPortInfo(
                        device=url,
                        resolved_device=url,
                        vid=usb.vendor_id,
                        pid=usb.product_id,
                        serial_number=usb.serial_number or None,
                        manufacturer=usb.manufacturer or None,
                        product=usb.product or None,
                        bcd_device=usb.bcd_device or None,
                        interface_description=usb.interface_description or None,
                        interface_num=usb.interface_number,
                    )
                )
            )

    return ports


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the esphome component."""
    ffmpeg_proxy.async_setup(hass)
    await assist_satellite.async_setup(hass)
    await dashboard.async_setup(hass)
    async_setup_websocket_api(hass)

    if "usb" in hass.config.components:
        async_register_serial_port_scanner(hass, _async_scan_serial_ports)
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP,
            serial_proxy.register_serialx_transport(hass.loop),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ESPHomeConfigEntry) -> bool:
    """Set up the esphome component."""
    host: str = entry.data[CONF_HOST]
    password: str | None = entry.data[CONF_PASSWORD]

    zeroconf_instance = await zeroconf.async_get_instance(hass)

    cli = async_create_api_client(
        hass,
        entry,
        zeroconf_instance,
        noise_psk=entry.data.get(CONF_NOISE_PSK),
        declare_outgoing_target=True,
    )

    domain_data = DomainData.get(hass)
    entry_data = RuntimeEntryData(
        client=cli,
        entry_id=entry.entry_id,
        title=entry.title,
        store=domain_data.get_or_create_store(hass, entry),
        original_options=dict(entry.options),
    )
    entry.runtime_data = entry_data

    manager = ESPHomeManager(
        hass, entry, host, password, cli, zeroconf_instance, domain_data
    )
    await manager.async_start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ESPHomeConfigEntry) -> bool:
    """Unload an esphome config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, entry.runtime_data.loaded_platforms
    )
    if unload_ok:
        await cleanup_instance(entry)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ESPHomeConfigEntry) -> None:
    """Remove an esphome config entry."""
    if bluetooth_mac_address := entry.data.get(CONF_BLUETOOTH_MAC_ADDRESS):
        async_remove_scanner(hass, bluetooth_mac_address.upper())
    async_delete_issue(
        hass, DOMAIN, DEVICE_CONFLICT_ISSUE_FORMAT.format(entry.entry_id)
    )
    await DomainData.get(hass).get_or_create_store(hass, entry).async_remove()

    await _async_clear_dynamic_encryption_key(hass, entry)


async def _async_clear_dynamic_encryption_key(
    hass: HomeAssistant, entry: ESPHomeConfigEntry
) -> None:
    """Clear the dynamic encryption key on the device and from storage."""
    if entry.unique_id is None or entry.data.get(CONF_NOISE_PSK) is None:
        return

    # Only clear the key if it's stored in our storage, meaning it was
    # dynamically generated by us and not user-provided
    storage = await async_get_encryption_key_storage(hass)
    if await storage.async_get_key(entry.unique_id) is None:
        return

    zeroconf_instance = await zeroconf.async_get_instance(hass)

    cli = async_create_api_client(
        hass,
        entry,
        zeroconf_instance,
        noise_psk=entry.data.get(CONF_NOISE_PSK),
    )

    try:
        await cli.connect()
        # Clear the encryption key on the device by passing an empty key
        if not await cli.noise_encryption_set_key(b""):
            _LOGGER.debug(
                "Could not clear dynamic encryption key for"
                " ESPHome device %s: Device rejected key removal",
                entry.unique_id,
            )
            return
    except APIConnectionError as exc:
        _LOGGER.debug(
            "Could not connect to ESPHome device %s to clear"
            " dynamic encryption key: %s",
            entry.unique_id,
            exc,
        )
        return
    finally:
        await cli.disconnect()

    await storage.async_remove_key(entry.unique_id)
