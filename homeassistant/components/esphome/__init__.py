"""Support for esphome devices."""

import dataclasses
import logging

from aioesphomeapi import (
    APIConnectionError,
    SerialProxyIdentity,
    SerialProxyIdentityFlag,
    SerialProxyIdentitySource,
)
from serialx import SerialPortInfo, udev_serial_by_id_stem

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


def _identity_port_info(identity: SerialProxyIdentity) -> SerialPortInfo:
    """Describe the device behind a serial proxy port."""
    is_usb = identity.source is SerialProxyIdentitySource.USB

    return SerialPortInfo(
        device="",
        resolved_device="",
        vid=identity.usb.vendor_id if is_usb else None,
        pid=identity.usb.product_id if is_usb else None,
        serial_number=identity.serial_number or None,
        manufacturer=identity.manufacturer or None,
        product=identity.product or None,
        bcd_device=identity.usb.bcd_device if is_usb else None,
        interface_description=None,
        interface_num=identity.usb.interface_number if is_usb else None,
    )


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

        identities = entry_data.serial_proxy_identities

        for instance, proxy in enumerate(device_info.serial_proxies):
            # Older ESPHome devices send no identity, and a port without a configured
            # identity carries none. Both fall back to less granular port info.
            if (
                instance not in identities
                or identities[instance].source is SerialProxyIdentitySource.NONE
            ):
                manufacturer, model = async_get_manufacturer_model(device_info)

                ports.append(
                    SerialDevice(
                        device=str(
                            serial_proxy.build_url(entry.entry_id, port_name=proxy.name)
                        ),
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

            identity = identities[instance]

            # An empty USB socket, or a USB device whose descriptors cannot be read
            if (
                not identity.flags & SerialProxyIdentityFlag.CONNECTED
                or identity.flags & SerialProxyIdentityFlag.ERROR
            ):
                continue

            port_info = _identity_port_info(identity)

            if (port_udev_id := udev_serial_by_id_stem(port_info)) is None:
                # If a port has incomplete metadata, it cannot be given a `udev_id`. We
                # try to match based on everything else, including the name of the
                # serial proxy. This is like `/dev/serial/by-path/`.
                filters = serial_proxy.SerialProxyFilters(
                    port_name=proxy.name,
                    port_manufacturer=port_info.manufacturer,
                    port_product=port_info.product,
                    port_serial_number=port_info.serial_number,
                    port_usb_vid=port_info.vid,
                    port_usb_pid=port_info.pid,
                    port_usb_bcd_device=port_info.bcd_device,
                    port_usb_interface_num=port_info.interface_num,
                )
            else:
                # Otherwise, we match on just the `udev_id`, which is like
                # `/dev/serial/by-id/`.
                filters = serial_proxy.SerialProxyFilters(port_udev_id=port_udev_id)

            url = str(serial_proxy.build_url(entry_id=entry.entry_id, **filters))
            device = usb_serial_device_from_port(
                dataclasses.replace(port_info, device=url, resolved_device=url)
            )

            ports.append(device)

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
