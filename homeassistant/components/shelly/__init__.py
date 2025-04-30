"""The Shelly integration."""

from __future__ import annotations

from typing import Final

from aioshelly.ble.const import BLE_SCRIPT_NAME
from aioshelly.block_device import BlockDevice
from aioshelly.common import ConnectionOptions
from aioshelly.const import (
    DEFAULT_COAP_PORT,
    MODEL_OUT_PLUG_S_G3,
    MODEL_PLUG_S_G3,
    RPC_GENERATIONS,
)
from aioshelly.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
    RpcCallError,
)
from aioshelly.rpc_device import RpcDevice, bluetooth_mac_from_primary_mac
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.components.bluetooth import async_remove_scanner
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
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
    BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID,
    BLE_SCANNER_MIN_FIRMWARE,
    BLOCK_EXPECTED_SLEEP_PERIOD,
    BLOCK_WRONG_SLEEP_PERIOD,
    CONF_BLE_SCANNER_MODE,
    CONF_COAP_PORT,
    CONF_SLEEP_PERIOD,
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
from .utils import (
    async_create_issue_unsupported_firmware,
    get_coap_context,
    get_device_entry_gen,
    get_http_port,
    get_rpc_scripts_event_types,
    get_ws_context,
)

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
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
    Platform.SENSOR,
    Platform.UPDATE,
]

COAP_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_COAP_PORT, default=DEFAULT_COAP_PORT): cv.port,
    }
)
CONFIG_SCHEMA: Final = vol.Schema({DOMAIN: COAP_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Shelly component."""
    if (conf := config.get(DOMAIN)) is not None:
        hass.data[DOMAIN] = {CONF_COAP_PORT: conf[CONF_COAP_PORT]}

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
            connections={(CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
        )
    # https://github.com/home-assistant/core/pull/48076
    if device_entry and entry.entry_id not in device_entry.config_entries:
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
            connections={(CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
        )
    # https://github.com/home-assistant/core/pull/48076
    if device_entry and entry.entry_id not in device_entry.config_entries:
        device_entry = None

    sleep_period = entry.data.get(CONF_SLEEP_PERIOD)
    runtime_data = entry.runtime_data
    runtime_data.platforms = RPC_SLEEPING_PLATFORMS

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
            runtime_data.rpc_zigbee_enabled = device.zigbee_enabled
            runtime_data.rpc_supports_scripts = await device.supports_scripts()
            if runtime_data.rpc_supports_scripts:
                runtime_data.rpc_script_events = await get_rpc_scripts_event_types(
                    device, ignore_scripts=[BLE_SCRIPT_NAME]
                )
        except (DeviceConnectionError, MacAddressMismatchError, RpcCallError) as err:
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

        runtime_data.rpc = ShellyRpcCoordinator(hass, entry, device)
        runtime_data.rpc.async_setup()
        runtime_data.rpc_poll = ShellyRpcPollingCoordinator(hass, entry, device)
        await hass.config_entries.async_forward_entry_setups(
            entry, runtime_data.platforms
        )

        # Latest available firmware for Plug S Gen3 and Outdoor Plug S Gen3 is 1.2.3.
        if runtime_data.rpc_supports_scripts and runtime_data.rpc.model not in (
            MODEL_PLUG_S_G3,
            MODEL_OUT_PLUG_S_G3,
        ):
            firmware = AwesomeVersion(device.shelly["ver"])
            issue_id = BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID.format(
                unique=entry.unique_id
            )
            if (
                firmware < BLE_SCANNER_MIN_FIRMWARE
                and entry.options.get(CONF_BLE_SCANNER_MODE) == BLEScannerMode.ACTIVE
            ):
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=True,
                    is_persistent=True,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="ble_scanner_firmware_unsupported",
                    translation_placeholders={
                        "device_name": device.name,
                        "ip_address": device.ip_address,
                        "firmware": firmware,
                    },
                    data={"entry_id": entry.entry_id},
                )
            else:
                ir.async_delete_issue(
                    hass,
                    DOMAIN,
                    issue_id,
                )
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
    if get_device_entry_gen(entry) in RPC_GENERATIONS and (
        mac_address := entry.unique_id
    ):
        source = dr.format_mac(bluetooth_mac_from_primary_mac(mac_address)).upper()
        async_remove_scanner(hass, source)
