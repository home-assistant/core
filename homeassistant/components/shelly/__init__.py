"""The Shelly integration."""

import asyncio
from functools import partial
from typing import TYPE_CHECKING, Final

from aioshelly.ble.const import BLE_SCRIPT_NAME
from aioshelly.block_device import BlockDevice
from aioshelly.common import ConnectionOptions
from aioshelly.const import DEFAULT_COAP_PORT, RPC_GENERATIONS
from aioshelly.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
    RpcCallError,
)
from aioshelly.rpc_device import RpcDevice, bluetooth_mac_from_primary_mac
import voluptuous as vol

from homeassistant.components.bluetooth import async_remove_scanner
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import ConfigType

from .const import (
    BLOCK_EXPECTED_SLEEP_PERIOD,
    BLOCK_WRONG_SLEEP_PERIOD,
    CONF_BLE_SCANNER_MODE,
    CONF_COAP_PORT,
    CONF_SLEEP_PERIOD,
    DEVICE_CONFLICT_ISSUE_ID,
    DOMAIN,
    FIRMWARE_UNSUPPORTED_ISSUE_ID,
    LOGGER,
    MODELS_WITH_WRONG_SLEEP_PERIOD,
    PUSH_UPDATE_ISSUE_ID,
    BLEScannerMode,
)
from .coordinator import (
    ShellyBlockCoordinator,
    ShellyConfigEntry,
    ShellyEntryData,
    ShellyRestCoordinator,
    ShellyRpcCoordinator,
    ShellyRpcPollingCoordinator,
)
from .repairs import (
    async_manage_ble_scanner_firmware_unsupported_issue,
    async_manage_deprecated_firmware_issue,
    async_manage_open_wifi_ap_issue,
    async_manage_outbound_websocket_incorrectly_enabled_issue,
)
from .services import async_setup_services
from .utils import (
    async_create_issue_unsupported_firmware,
    async_migrate_rpc_sensor_description_unique_ids,
    async_migrate_rpc_virtual_components_unique_ids,
    get_coap_context,
    get_device_entry_gen,
    get_http_port,
    get_rpc_scripts_event_types,
    get_ws_context,
    is_rpc_ble_scanner_supported,
    remove_empty_sub_devices,
    remove_stale_blu_trv_devices,
)

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.UPDATE,
    Platform.VALVE,
]
BLOCK_SLEEPING_PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
RPC_SLEEPING_PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.UPDATE,
]

COAP_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_COAP_PORT, default=DEFAULT_COAP_PORT): cv.port,
    }
)
CONFIG_SCHEMA: Final = vol.Schema({DOMAIN: COAP_SCHEMA}, extra=vol.ALLOW_EXTRA)

# Max time to wait at startup for a BLE proxy to register its scanner.
STARTUP_SCANNER_WAIT: Final = 3.0


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Shelly component."""
    if (conf := config.get(DOMAIN)) is not None:
        # Uses legacy hass.data[DOMAIN] pattern
        # pylint: disable-next=home-assistant-use-runtime-data
        hass.data[DOMAIN] = {CONF_COAP_PORT: conf[CONF_COAP_PORT]}

    async_setup_services(hass)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ShellyConfigEntry) -> bool:
    """Migrate old config entries."""

    if entry.minor_version < 3:
        # One-time flip of explicit Active scanning to Auto so existing
        # installs get the new battery-friendly default; Passive stays
        # Passive because users picked it deliberately.
        options = dict(entry.options)
        if options.get(CONF_BLE_SCANNER_MODE) == BLEScannerMode.ACTIVE:
            options[CONF_BLE_SCANNER_MODE] = BLEScannerMode.AUTO
        hass.config_entries.async_update_entry(entry, options=options, minor_version=3)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ShellyConfigEntry) -> bool:
    """Set up Shelly from a config entry."""
    entry.runtime_data = ShellyEntryData([])

    # The custom component for Shelly devices uses shelly domain as well as core
    # integration. If the user removes the custom component but doesn't remove the
    # config entry, core integration will try to configure that config entry with an
    # error. The config entry data for this custom component doesn't contain host
    # value, so if host isn't present, config entry will not be configured.
    if not entry.data.get(CONF_HOST):
        LOGGER.warning(
            (
                "The config entry %s probably comes from a custom integration, please"
                " remove it if you want to use core Shelly integration"
            ),
            entry.title,
        )
        return False

    if get_device_entry_gen(entry) in RPC_GENERATIONS:
        return await _async_setup_rpc_entry(hass, entry)

    return await _async_setup_block_entry(hass, entry)


async def _async_setup_block_entry(
    hass: HomeAssistant, entry: ShellyConfigEntry
) -> bool:
    """Set up Shelly block based device from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        device_mac=entry.unique_id,
    )

    coap_context = await get_coap_context(hass)

    device = await BlockDevice.create(
        async_get_clientsession(hass),
        coap_context,
        options,
    )

    dev_reg = dr.async_get(hass)
    device_entry = None
    if entry.unique_id is not None:
        device_entry = dev_reg.async_get_device(
            connections={(CONNECTION_NETWORK_MAC, entry.unique_id)},
        )
    # https://github.com/home-assistant/core/pull/48076
    if device_entry and entry.entry_id not in device_entry.config_entries:
        LOGGER.debug("Detected first time setup for device %s", entry.title)
        device_entry = None

    sleep_period = entry.data.get(CONF_SLEEP_PERIOD)
    runtime_data = entry.runtime_data
    runtime_data.platforms = BLOCK_SLEEPING_PLATFORMS

    # Some old firmware have a wrong sleep period hardcoded value.
    # Following code block will force the right value for affected devices
    if (
        sleep_period == BLOCK_WRONG_SLEEP_PERIOD
        and entry.data[CONF_MODEL] in MODELS_WITH_WRONG_SLEEP_PERIOD
    ):
        LOGGER.warning(
            "Updating stored sleep period for %s: from %s to %s",
            entry.title,
            sleep_period,
            BLOCK_EXPECTED_SLEEP_PERIOD,
        )
        data = {**entry.data}
        data[CONF_SLEEP_PERIOD] = sleep_period = BLOCK_EXPECTED_SLEEP_PERIOD
        hass.config_entries.async_update_entry(entry, data=data)

    if sleep_period == 0:
        # Not a sleeping device, finish setup
        LOGGER.debug("Setting up online block device %s", entry.title)
        runtime_data.platforms = PLATFORMS
        try:
            await device.initialize()
            if not device.firmware_supported:
                async_create_issue_unsupported_firmware(hass, entry)
                await device.shutdown()
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="firmware_unsupported",
                    translation_placeholders={"device": entry.title},
                )
        except (DeviceConnectionError, MacAddressMismatchError) as err:
            # Unlike the RPC path, the Block setup cannot offer a device conflict
            # repair: aioshelly raises MacAddressMismatchError from inside
            # get_info() and discards the response, so the observed MAC is not
            # available on the device object. A gen1 hardware swap on a static-IP
            # device thus surfaces as a generic error until rediscovered via
            # zeroconf.
            await device.shutdown()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_communication_error",
                translation_placeholders={"device": entry.title},
            ) from err
        except InvalidAuthError as err:
            await device.shutdown()
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"device": entry.title},
            ) from err

        runtime_data.block = ShellyBlockCoordinator(hass, entry, device)
        runtime_data.block.async_setup()
        runtime_data.rest = ShellyRestCoordinator(hass, device, entry)
        await hass.config_entries.async_forward_entry_setups(
            entry, runtime_data.platforms
        )
        remove_empty_sub_devices(hass, entry)
    elif (
        sleep_period is None
        or device_entry is None
        or not er.async_entries_for_device(er.async_get(hass), device_entry.id)
    ):
        # Need to get sleep info or first time sleeping device setup, wait for device
        # If there are no entities for the device, it means we added the device, but
        # Home Assistant was restarted before the device was online. In this case we
        # cannot restore the entities, so we need to wait for the device to be online.
        LOGGER.debug(
            "Setup for device %s will resume when device is online", entry.title
        )
        runtime_data.block = ShellyBlockCoordinator(hass, entry, device)
        runtime_data.block.async_setup(runtime_data.platforms)
    else:
        # Restore sensors for sleeping device
        LOGGER.debug("Setting up offline block device %s", entry.title)
        runtime_data.block = ShellyBlockCoordinator(hass, entry, device)
        runtime_data.block.async_setup()
        await hass.config_entries.async_forward_entry_setups(
            entry, runtime_data.platforms
        )

    ir.async_delete_issue(
        hass, DOMAIN, FIRMWARE_UNSUPPORTED_ISSUE_ID.format(unique=entry.unique_id)
    )
    # The device connected cleanly with a matching MAC, so any pending device
    # conflict (hardware replacement) repair issue is resolved.
    ir.async_delete_issue(
        hass, DOMAIN, DEVICE_CONFLICT_ISSUE_ID.format(unique=entry.entry_id)
    )
    return True


async def _async_setup_rpc_entry(hass: HomeAssistant, entry: ShellyConfigEntry) -> bool:
    """Set up Shelly RPC based device from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        device_mac=entry.unique_id,
        port=get_http_port(entry.data),
    )

    ws_context = await get_ws_context(hass)

    device = await RpcDevice.create(
        async_get_clientsession(hass),
        ws_context,
        options,
    )

    dev_reg = dr.async_get(hass)
    device_entry = None
    if entry.unique_id is not None:
        device_entry = dev_reg.async_get_device(
            connections={(CONNECTION_NETWORK_MAC, entry.unique_id)},
        )
    # https://github.com/home-assistant/core/pull/48076
    if device_entry and entry.entry_id not in device_entry.config_entries:
        LOGGER.debug("Detected first time setup for device %s", entry.title)
        device_entry = None

    sleep_period = entry.data.get(CONF_SLEEP_PERIOD)
    runtime_data = entry.runtime_data
    runtime_data.platforms = RPC_SLEEPING_PLATFORMS

    await er.async_migrate_entries(
        hass,
        entry.entry_id,
        async_migrate_rpc_sensor_description_unique_ids,
    )

    if sleep_period == 0:
        # Not a sleeping device, finish setup
        LOGGER.debug("Setting up online RPC device %s", entry.title)
        runtime_data.platforms = PLATFORMS
        try:
            await device.initialize()
            if not device.firmware_supported:
                async_create_issue_unsupported_firmware(hass, entry)
                await device.shutdown()
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="firmware_unsupported",
                    translation_placeholders={"device": entry.title},
                )
            runtime_data.rpc_zigbee_firmware = device.zigbee_firmware
            runtime_data.rpc_supports_scripts = await device.supports_scripts()
            if runtime_data.rpc_supports_scripts:
                runtime_data.rpc_script_events = await get_rpc_scripts_event_types(
                    device, ignore_scripts=[BLE_SCRIPT_NAME]
                )
            remove_stale_blu_trv_devices(hass, device, entry)
        except MacAddressMismatchError as err:
            # The device answering at this host reports a different MAC than the
            # one stored on the entry: the hardware was most likely replaced.
            # The device's own primary MAC is available here (Shelly.GetDeviceInfo
            # is fetched before aioshelly raises), so we can offer a repair to
            # migrate the configuration even when zeroconf discovery never fires
            # (static IP, discovery disabled, different subnet).
            _async_create_device_conflict_issue(hass, entry, device.shelly[CONF_MAC])
            await device.shutdown()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_communication_error",
                translation_placeholders={"device": entry.title},
            ) from err
        except (DeviceConnectionError, RpcCallError) as err:
            await device.shutdown()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_communication_error",
                translation_placeholders={"device": entry.title},
            ) from err
        except InvalidAuthError as err:
            await device.shutdown()
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"device": entry.title},
            ) from err

        await er.async_migrate_entries(
            hass,
            entry.entry_id,
            partial(async_migrate_rpc_virtual_components_unique_ids, device.config),
        )

        runtime_data.rpc = ShellyRpcCoordinator(hass, entry, device)
        runtime_data.rpc.async_setup()

        if (
            is_rpc_ble_scanner_supported(entry)
            and entry.options.get(CONF_BLE_SCANNER_MODE, BLEScannerMode.DISABLED)
            != BLEScannerMode.DISABLED
        ):
            # Wait for the proxy to register its scanner before finishing setup.
            try:
                async with asyncio.timeout(STARTUP_SCANNER_WAIT):
                    await runtime_data.rpc.ble_scanner_setup_done.wait()
            except TimeoutError:
                LOGGER.debug(
                    "%s: Timed out waiting for BLE scanner to register", entry.title
                )

        runtime_data.rpc_poll = ShellyRpcPollingCoordinator(hass, entry, device)
        await hass.config_entries.async_forward_entry_setups(
            entry, runtime_data.platforms
        )
        async_manage_deprecated_firmware_issue(hass, entry)
        async_manage_ble_scanner_firmware_unsupported_issue(
            hass,
            entry,
        )
        async_manage_outbound_websocket_incorrectly_enabled_issue(
            hass,
            entry,
        )
        async_manage_open_wifi_ap_issue(hass, entry)
        remove_empty_sub_devices(hass, entry)
    elif (
        sleep_period is None
        or device_entry is None
        or not er.async_entries_for_device(er.async_get(hass), device_entry.id)
    ):
        # Need to get sleep info or first time sleeping device setup, wait for device
        # If there are no entities for the device, it means we added the device, but
        # Home Assistant was restarted before the device was online. In this case we
        # cannot restore the entities, so we need to wait for the device to be online.
        LOGGER.debug(
            "Setup for device %s will resume when device is online", entry.title
        )
        runtime_data.rpc = ShellyRpcCoordinator(hass, entry, device)
        runtime_data.rpc.async_setup(runtime_data.platforms)
        # Try to connect to the device, if we reached here from config flow
        # and user woke up the device when adding it, we can continue setup
        # otherwise we will wait for the device to wake up
        if sleep_period:
            await runtime_data.rpc.async_device_online("setup")
    else:
        # Restore sensors for sleeping device
        LOGGER.debug("Setting up offline RPC device %s", entry.title)
        runtime_data.rpc = ShellyRpcCoordinator(hass, entry, device)
        runtime_data.rpc.async_setup()
        await hass.config_entries.async_forward_entry_setups(
            entry, runtime_data.platforms
        )

    ir.async_delete_issue(
        hass, DOMAIN, FIRMWARE_UNSUPPORTED_ISSUE_ID.format(unique=entry.unique_id)
    )
    # The device connected cleanly with a matching MAC, so any pending device
    # conflict (hardware replacement) repair issue is resolved.
    ir.async_delete_issue(
        hass, DOMAIN, DEVICE_CONFLICT_ISSUE_ID.format(unique=entry.entry_id)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ShellyConfigEntry) -> bool:
    """Unload a config entry."""
    # delete push update issue if it exists
    LOGGER.debug(
        "Deleting issue %s", PUSH_UPDATE_ISSUE_ID.format(unique=entry.unique_id)
    )
    ir.async_delete_issue(
        hass, DOMAIN, PUSH_UPDATE_ISSUE_ID.format(unique=entry.unique_id)
    )

    runtime_data = entry.runtime_data

    if runtime_data.rpc:
        await runtime_data.rpc.shutdown()

    if runtime_data.block:
        await runtime_data.block.shutdown()

    return await hass.config_entries.async_unload_platforms(
        entry, runtime_data.platforms
    )


async def async_remove_entry(hass: HomeAssistant, entry: ShellyConfigEntry) -> None:
    """Remove a config entry."""
    ir.async_delete_issue(
        hass, DOMAIN, DEVICE_CONFLICT_ISSUE_ID.format(unique=entry.entry_id)
    )
    if get_device_entry_gen(entry) in RPC_GENERATIONS and (
        mac_address := entry.unique_id
    ):
        source = dr.format_mac(bluetooth_mac_from_primary_mac(mac_address)).upper()
        async_remove_scanner(hass, source)


@callback
def _async_create_device_conflict_issue(
    hass: HomeAssistant, entry: ShellyConfigEntry, new_mac: str
) -> None:
    """Raise a repair issue for a replacement device detected during setup.

    Used when a device answering at the configured host reports a different
    primary MAC than the one stored on the entry (``MacAddressMismatchError``).
    This is the fallback detection path for devices that are never rediscovered
    via zeroconf (static IP, discovery disabled, different subnet).
    """
    stored_mac = entry.unique_id
    if (
        not stored_mac
        or stored_mac.replace(":", "").upper() == new_mac.replace(":", "").upper()
    ):
        # No stored identity, or the observed MAC matches it: nothing to migrate.
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        DEVICE_CONFLICT_ISSUE_ID.format(unique=entry.entry_id),
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="device_conflict",
        translation_placeholders={
            "device_name": entry.title,
            "host": entry.data[CONF_HOST],
            "old_mac": dr.format_mac(stored_mac).upper(),
            "new_mac": dr.format_mac(new_mac).upper(),
        },
        data={
            "entry_id": entry.entry_id,
            "device_name": entry.title,
            "host": entry.data[CONF_HOST],
            "old_mac": stored_mac,
            "new_mac": new_mac,
        },
    )


async def async_replace_device(
    hass: HomeAssistant,
    entry_id: str,
    old_mac: str,
    new_mac: str,
) -> None:
    """Migrate a Shelly config entry to a replacement device with a new MAC.

    Rewrites the config entry unique_id, the main device's connections and
    identifiers, every Shelly sub-device identifier, and every entity
    unique_id, so the Home Assistant device, entity_ids, history and
    automations are preserved on the new hardware.

    Bluetooth/BLU sub-devices (keyed by their own BLE address, not the
    gateway MAC) are deliberately left untouched.
    """
    entry = hass.config_entries.async_get_entry(entry_id)
    if TYPE_CHECKING:
        assert entry is not None

    # MAC casing: identifiers and entity unique_ids use UPPERCASE bare;
    # the connection tuple is format_mac'd to lowercase colon-separated.
    old_mac_upper = old_mac.replace(":", "").upper()
    new_mac_upper = new_mac.replace(":", "").upper()

    # 1. Config entry unique_id. Shelly stores the bare MAC UPPERCASE (it is
    #    set from the device's reported MAC, which aioshelly returns upper),
    #    and coordinator.mac == entry.unique_id feeds every device identifier
    #    and entity unique_id. Storing the upper form keeps the reload from
    #    re-deriving a mismatching MAC. The next device.initialize() then sees
    #    a matching MAC and the conflict does not re-fire (Shelly re-derives
    #    identity live; there is no Store cache to update).
    hass.config_entries.async_update_entry(entry, unique_id=new_mac_upper)

    # 2. Main device: rewrite both the MAC connection and the (DOMAIN, MAC)
    #    identifier. Sub-devices: rewrite the MAC-prefixed identifier.
    dev_reg = dr.async_get(hass)
    new_connection = (CONNECTION_NETWORK_MAC, dr.format_mac(new_mac))
    old_main_identifier = (DOMAIN, old_mac_upper)
    new_main_identifier = (DOMAIN, new_mac_upper)
    sub_prefix = f"{old_mac_upper}-"
    for device in dr.async_entries_for_config_entry(dev_reg, entry_id):
        new_identifiers: set[tuple[str, str]] | None = None
        if old_main_identifier in device.identifiers:
            # Main device.
            new_identifiers = {
                new_main_identifier if ident == old_main_identifier else ident
                for ident in device.identifiers
            }
            dev_reg.async_update_device(
                device.id,
                new_connections={new_connection},
                new_identifiers=new_identifiers,
            )
            continue

        # Sub-device. Rewrite only DOMAIN identifiers prefixed with the old
        # MAC; this naturally skips BLU/bthome sub-devices (BLE-addr keyed).
        if any(
            domain == DOMAIN and ident.startswith(sub_prefix)
            for domain, ident in device.identifiers
        ):
            new_identifiers = {
                (domain, f"{new_mac_upper}-{ident[len(sub_prefix) :]}")
                if domain == DOMAIN and ident.startswith(sub_prefix)
                else (domain, ident)
                for domain, ident in device.identifiers
            }
            dev_reg.async_update_device(device.id, new_identifiers=new_identifiers)

    # 3. Entity unique_ids: rewrite the MAC prefix. BLU entities are
    #    BLE-addr prefixed and skipped by the startswith guard.
    @callback
    def _migrate_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, str] | None:
        """Rewrite the old MAC prefix of an entity unique_id to the new MAC."""
        if entity_entry.unique_id.startswith(sub_prefix):
            return {
                "new_unique_id": new_mac_upper
                + entity_entry.unique_id[len(old_mac_upper) :]
            }
        return None

    await er.async_migrate_entries(hass, entry_id, _migrate_unique_id)
