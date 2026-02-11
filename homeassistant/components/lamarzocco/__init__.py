"""The La Marzocco integration."""

import asyncio
import logging
import uuid

from aiohttp import ClientSession
from packaging import version
from pylamarzocco import (
    LaMarzoccoBluetoothClient,
    LaMarzoccoCloudClient,
    LaMarzoccoMachine,
)
from pylamarzocco.const import FirmwareType
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
from pylamarzocco.util import InstallationKey, generate_installation_key

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.const import (
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
    __version__,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_INSTALLATION_KEY, CONF_OFFLINE_MODE, CONF_USE_BLUETOOTH, DOMAIN
from .coordinator import (
    LaMarzoccoBluetoothUpdateCoordinator,
    LaMarzoccoConfigEntry,
    LaMarzoccoConfigUpdateCoordinator,
    LaMarzoccoRuntimeData,
    LaMarzoccoScheduleUpdateCoordinator,
    LaMarzoccoSettingsUpdateCoordinator,
    LaMarzoccoStatisticsUpdateCoordinator,
)

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

BT_MODEL_PREFIXES = ("MICRA", "MINI", "GS3")

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: LaMarzoccoConfigEntry) -> bool:
    """Set up La Marzocco as config entry."""

    assert entry.unique_id
    serial = entry.unique_id

    cloud_client = LaMarzoccoCloudClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        installation_key=InstallationKey.from_json(entry.data[CONF_INSTALLATION_KEY]),
        client=create_client_session(hass),
    )

    # initialize Bluetooth
    bluetooth_client: LaMarzoccoBluetoothClient | None = None
    if entry.options.get(CONF_USE_BLUETOOTH, True) and (
        token := entry.data.get(CONF_TOKEN)
    ):
        if CONF_MAC not in entry.data:
            for discovery_info in async_discovered_service_info(hass):
                if (
                    (name := discovery_info.name)
                    and name.startswith(BT_MODEL_PREFIXES)
                    and name.split("_")[1] == serial
                ):
                    _LOGGER.info("Found lamarzocco Bluetooth device, adding to entry")
                    # found a device, add MAC address to config entry
                    hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_MAC: discovery_info.address,
                        },
                    )

        if CONF_MAC in entry.data:
            ble_device = async_ble_device_from_address(hass, entry.data[CONF_MAC])
            if ble_device:
                _LOGGER.info("Setting up lamarzocco with Bluetooth")
                bluetooth_client = LaMarzoccoBluetoothClient(
                    ble_device=ble_device,
                    ble_token=token,
                )

                async def disconnect_bluetooth(_: Event) -> None:
                    """Stop push updates when hass stops."""
                    await bluetooth_client.disconnect()

                entry.async_on_unload(
                    hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_STOP, disconnect_bluetooth
                    )
                )
                entry.async_on_unload(bluetooth_client.disconnect)
            else:
                _LOGGER.info(
                    "Bluetooth device not found during lamarzocco setup, continuing with cloud only"
                )

    async def _get_thing_settings() -> None:
        """Get thing settings from cloud to verify details and get BLE token."""
        try:
            settings = await cloud_client.get_thing_settings(serial)
        except AuthFail as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from ex
        except (RequestNotSuccessful, TimeoutError) as ex:
            _LOGGER.debug(ex, exc_info=True)
            if not bluetooth_client:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN, translation_key="api_error"
                ) from ex
            _LOGGER.debug("Cloud failed, continuing with Bluetooth only", exc_info=True)
        else:
            gateway_version = version.parse(
                settings.firmwares[FirmwareType.GATEWAY].build_version
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
            # Update BLE Token if exists
            if settings.ble_auth_token:
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_TOKEN: settings.ble_auth_token,
                    },
                )

    if not (local_mode := entry.options.get(CONF_OFFLINE_MODE, False)):
        await _get_thing_settings()

    device = LaMarzoccoMachine(
        serial_number=entry.unique_id,
        cloud_client=cloud_client,
        bluetooth_client=bluetooth_client,
    )

    coordinators = LaMarzoccoRuntimeData(
        LaMarzoccoConfigUpdateCoordinator(hass, entry, device),
        LaMarzoccoSettingsUpdateCoordinator(hass, entry, device),
        LaMarzoccoScheduleUpdateCoordinator(hass, entry, device),
        LaMarzoccoStatisticsUpdateCoordinator(hass, entry, device),
    )

    if not local_mode:
        await asyncio.gather(
            coordinators.config_coordinator.async_config_entry_first_refresh(),
            coordinators.settings_coordinator.async_config_entry_first_refresh(),
            coordinators.schedule_coordinator.async_config_entry_first_refresh(),
            coordinators.statistics_coordinator.async_config_entry_first_refresh(),
        )

    if local_mode and not bluetooth_client:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="bluetooth_required_offline"
        )

    # bt coordinator only if bluetooth client is available
    # and after the initial refresh of the config coordinator
    # to fetch only if the others failed
    if bluetooth_client:
        bluetooth_coordinator = LaMarzoccoBluetoothUpdateCoordinator(
            hass, entry, device
        )
        await bluetooth_coordinator.async_config_entry_first_refresh()
        coordinators.bluetooth_coordinator = bluetooth_coordinator

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LaMarzoccoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: LaMarzoccoConfigEntry
) -> bool:
    """Migrate config entry."""
    if entry.version > 4:
        # guard against downgrade from a future version
        return False

    if entry.version in (1, 2):
        _LOGGER.error(
            "Migration from version 1 or 2 is no longer supported, please remove and re-add the integration"
        )
        return False

    if entry.version == 3:
        installation_key = generate_installation_key(str(uuid.uuid4()).lower())
        cloud_client = LaMarzoccoCloudClient(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            installation_key=installation_key,
            client=create_client_session(hass),
        )
        try:
            await cloud_client.async_register_client()
        except (AuthFail, RequestNotSuccessful) as exc:
            _LOGGER.error("Migration failed with error %s", exc)
            return False

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_INSTALLATION_KEY: installation_key.to_json(),
            },
            version=4,
        )
        _LOGGER.debug("Migrated La Marzocco config entry to version 4")

    return True


def create_client_session(hass: HomeAssistant) -> ClientSession:
    """Create a ClientSession with La Marzocco specific headers."""

    return async_create_clientsession(
        hass,
        headers={
            "X-Client": "HOME_ASSISTANT",
            "X-Client-Build": __version__,
        },
    )
