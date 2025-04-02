"""The La Marzocco integration."""

import logging

from packaging import version
from pylamarzocco import (
    LaMarzoccoBluetoothClient,
    LaMarzoccoCloudClient,
    LaMarzoccoMachine,
)
from pylamarzocco.const import FirmwareType
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful

from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.const import (
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_USE_BLUETOOTH, DOMAIN
from .coordinator import (
    LaMarzoccoConfigEntry,
    LaMarzoccoConfigUpdateCoordinator,
    LaMarzoccoRuntimeData,
    LaMarzoccoSettingsUpdateCoordinator,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.UPDATE,
]

BT_MODEL_PREFIXES = ("MICRA", "MINI", "GS3")

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: LaMarzoccoConfigEntry) -> bool:
    """Set up La Marzocco as config entry."""

    assert entry.unique_id
    serial = entry.unique_id

    client = async_create_clientsession(hass)
    cloud_client = LaMarzoccoCloudClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        client=client,
    )

    # initialize the firmware update coordinator early to check the firmware version
    firmware_device = LaMarzoccoMachine(
        serial_number=entry.unique_id,
        cloud_client=cloud_client,
    )

    firmware_coordinator = LaMarzoccoSettingsUpdateCoordinator(
        hass, entry, firmware_device
    )
    await firmware_coordinator.async_config_entry_first_refresh()
    gateway_version = version.parse(
        firmware_device.settings.firmwares[FirmwareType.GATEWAY].build_version
    )

    if gateway_version < version.parse("v5.0.9"):
        # incompatible gateway firmware, create an issue
        ir.async_create_issue(
            hass,
            DOMAIN,
            "unsupported_gateway_firmware",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="unsupported_gateway_firmware",
            translation_placeholders={"gateway_version": str(gateway_version)},
        )

    # initialize Bluetooth
    bluetooth_client: LaMarzoccoBluetoothClient | None = None
    if (
        entry.options.get(CONF_USE_BLUETOOTH, True)
        and firmware_device.settings.ble_auth_token
    ):
        if CONF_MAC not in entry.data:
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
                        },
                    )

        if CONF_MAC in entry.data:
            _LOGGER.debug("Initializing Bluetooth device")
            bluetooth_client = LaMarzoccoBluetoothClient(
                address_or_ble_device=entry.data[CONF_MAC],
                ble_token=entry.data[CONF_TOKEN],
            )

    device = LaMarzoccoMachine(
        serial_number=entry.unique_id,
        cloud_client=cloud_client,
        bluetooth_client=bluetooth_client,
    )

    coordinators = LaMarzoccoRuntimeData(
        LaMarzoccoConfigUpdateCoordinator(hass, entry, device),
        firmware_coordinator,
    )

    await coordinators.config_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def update_listener(
        hass: HomeAssistant, entry: LaMarzoccoConfigEntry
    ) -> None:
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LaMarzoccoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: LaMarzoccoConfigEntry
) -> bool:
    """Migrate config entry."""
    if entry.version > 3:
        # guard against downgrade from a future version
        return False

    if entry.version == 1:
        _LOGGER.error(
            "Migration from version 1 is no longer supported, please remove and re-add the integration"
        )
        return False

    if entry.version == 2:
        cloud_client = LaMarzoccoCloudClient(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
        try:
            things = await cloud_client.list_things()
        except (AuthFail, RequestNotSuccessful) as exc:
            _LOGGER.error("Migration failed with error %s", exc)
            return False
        v3_data = {
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
            CONF_TOKEN: next(
                (
                    thing.ble_auth_token or ""
                    for thing in things
                    if thing.serial_number == entry.unique_id
                ),
                "",
            ),
        }
        if CONF_MAC in entry.data:
            v3_data[CONF_MAC] = entry.data[CONF_MAC]
        hass.config_entries.async_update_entry(
            entry,
            data=v3_data,
            version=3,
        )
        _LOGGER.debug("Migrated La Marzocco config entry to version 2")

    return True
