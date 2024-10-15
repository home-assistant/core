"""The La Marzocco integration."""

import logging

from lmcloud.client_bluetooth import LaMarzoccoBluetoothClient
from lmcloud.client_cloud import LaMarzoccoCloudClient
from lmcloud.client_local import LaMarzoccoLocalClient
from lmcloud.const import BT_MODEL_PREFIXES, FirmwareType
from lmcloud.exceptions import AuthFail, RequestNotSuccessful
from packaging import version

from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_USE_BLUETOOTH, DOMAIN
from .coordinator import LaMarzoccoUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

_LOGGER = logging.getLogger(__name__)

type LaMarzoccoConfigEntry = ConfigEntry[LaMarzoccoUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LaMarzoccoConfigEntry) -> bool:
    """Set up La Marzocco as config entry."""

    assert entry.unique_id
    serial = entry.unique_id

    cloud_client = LaMarzoccoCloudClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        client=get_async_client(hass),
    )

    # initialize local API
    local_client: LaMarzoccoLocalClient | None = None
    if (host := entry.data.get(CONF_HOST)) is not None:
        _LOGGER.debug("Initializing local API")
        local_client = LaMarzoccoLocalClient(
            host=host,
            local_bearer=entry.data[CONF_TOKEN],
            client=get_async_client(hass),
        )

    # initialize Bluetooth
    bluetooth_client: LaMarzoccoBluetoothClient | None = None
    if entry.options.get(CONF_USE_BLUETOOTH, True):

        def bluetooth_configured() -> bool:
            return entry.data.get(CONF_MAC, "") and entry.data.get(CONF_NAME, "")

        if not bluetooth_configured():
            for discovery_info in async_discovered_service_info(hass):
                if (
                    (name := discovery_info.name)
                    and name.startswith(BT_MODEL_PREFIXES)
                    and name.split("_")[1] == serial
                ):
                    _LOGGER.debug("Found Bluetooth device, configuring with Bluetooth")
                    # found a device, add MAC address to config entry
                    hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_MAC: discovery_info.address,
                            CONF_NAME: discovery_info.name,
                        },
                    )
                    break

        if bluetooth_configured():
            _LOGGER.debug("Initializing Bluetooth device")
            bluetooth_client = LaMarzoccoBluetoothClient(
                username=entry.data[CONF_USERNAME],
                serial_number=serial,
                token=entry.data[CONF_TOKEN],
                address_or_ble_device=entry.data[CONF_MAC],
            )

    coordinator = LaMarzoccoUpdateCoordinator(
        hass=hass,
        local_client=local_client,
        cloud_client=cloud_client,
        bluetooth_client=bluetooth_client,
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    gateway_version = coordinator.device.firmware[FirmwareType.GATEWAY].current_version
    if version.parse(gateway_version) < version.parse("v3.4-rc5"):
        # incompatible gateway firmware, create an issue
        ir.async_create_issue(
            hass,
            DOMAIN,
            "unsupported_gateway_firmware",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="unsupported_gateway_firmware",
            translation_placeholders={"gateway_version": gateway_version},
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry."""
    if entry.version > 2:
        # guard against downgrade from a future version
        return False

    if entry.version == 1:
        cloud_client = LaMarzoccoCloudClient(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
        try:
            fleet = await cloud_client.get_customer_fleet()
        except (AuthFail, RequestNotSuccessful) as exc:
            _LOGGER.error("Migration failed with error %s", exc)
            return False

        assert entry.unique_id is not None
        device = fleet[entry.unique_id]
        v2_data = {
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
            CONF_MODEL: device.model,
            CONF_NAME: device.name,
            CONF_TOKEN: device.communication_key,
        }

        if CONF_HOST in entry.data:
            v2_data[CONF_HOST] = entry.data[CONF_HOST]

        if CONF_MAC in entry.data:
            v2_data[CONF_MAC] = entry.data[CONF_MAC]

        hass.config_entries.async_update_entry(
            entry,
            data=v2_data,
            version=2,
        )
        _LOGGER.debug("Migrated La Marzocco config entry to version 2")
    return True
