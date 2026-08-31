"""The Ubiquiti airOS integration."""

import logging

from aiohttp import ClientSession, TCPConnector
from airos.airos6 import AirOS6
from airos.airos8 import AirOS8
from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSConnectionSetupError,
    AirOSDataMissingError,
    AirOSDeviceConnectionError,
    AirOSKeyDataMissingError,
    AirOSTLSCompatibilityError,
)
from airos.helpers import DetectDeviceData, async_get_firmware_data

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_LEGACY_SSL,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SECTION_ADDITIONAL_SETTINGS,
)
from .coordinator import (
    AirOSConfigEntry,
    AirOSDataUpdateCoordinator,
    AirOSFirmwareUpdateCoordinator,
    AirOSRuntimeData,
)
from .helpers import build_legacy_context

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.UPDATE,
]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Set up Ubiquiti airOS from a config entry."""
    owns_session = False
    verify_ssl = entry.data[SECTION_ADDITIONAL_SETTINGS][CONF_VERIFY_SSL]

    # By default airOS 8 comes with self-signed SSL certificates,
    # with no option in the web UI to change or upload a custom certificate.
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)

    if entry.data.get(CONF_LEGACY_SSL, False):
        session = ClientSession(
            connector=TCPConnector(ssl=build_legacy_context(verify_ssl=verify_ssl))
        )
        owns_session = True

    conn_data = {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_USERNAME: entry.data[CONF_USERNAME],
        CONF_PASSWORD: entry.data[CONF_PASSWORD],
        "session": session,
        "use_ssl": entry.data[SECTION_ADDITIONAL_SETTINGS][CONF_SSL],
    }

    async def close_session() -> None:
        """Close legacy session before raising if needed."""
        if owns_session:
            await session.close()

    # Determine firmware version before creating the device instance
    try:
        device_data: DetectDeviceData = await async_get_firmware_data(**conn_data)

    except (
        AirOSConnectionSetupError,
        AirOSDeviceConnectionError,
        AirOSTLSCompatibilityError,
        TimeoutError,
    ) as err:
        await close_session()
        raise ConfigEntryNotReady from err
    except (
        AirOSConnectionAuthenticationError,
        AirOSDataMissingError,
    ) as err:
        await close_session()
        raise ConfigEntryAuthFailed from err
    except AirOSKeyDataMissingError as err:
        await close_session()
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="key_data_missing"
        ) from err
    except Exception as err:
        await close_session()
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="unknown"
        ) from err

    airos_class: type[AirOS8 | AirOS6] = (
        AirOS8 if device_data["fw_major"] == 8 else AirOS6
    )

    airos_device = airos_class(**conn_data)

    data_coordinator = AirOSDataUpdateCoordinator(
        hass, entry, device_data, airos_device
    )

    try:
        await data_coordinator.async_config_entry_first_refresh()

        firmware_coordinator: AirOSFirmwareUpdateCoordinator | None = None
        if device_data["fw_major"] >= 8:
            firmware_coordinator = AirOSFirmwareUpdateCoordinator(
                hass, entry, airos_device
            )
            await firmware_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady, ConfigEntryAuthFailed:
        await close_session()
        raise
    except Exception as err:
        await close_session()
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="unknown"
        ) from err

    entry.runtime_data = AirOSRuntimeData(
        status=data_coordinator,
        firmware=firmware_coordinator,
        owns_session=owns_session,
        session=session,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Migrate old config entry."""

    # 1.1 Migrate config_entry to add additional ssl settings
    if entry.version == 1 and entry.minor_version == 1:
        new_minor_version = 2
        new_data = {**entry.data}
        additional_data = {
            CONF_SSL: DEFAULT_SSL,
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
        }
        new_data[SECTION_ADDITIONAL_SETTINGS] = additional_data

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=new_minor_version,
        )

    # 2.1 Migrate binary_sensor entity unique_id from device_id to mac_address
    #     Step 1 - migrate binary_sensor entity unique_id
    #     Step 2 - migrate device entity identifier
    if entry.version == 1:
        new_version = 2
        new_minor_version = 1

        mac_adress = dr.format_mac(entry.unique_id)

        device_registry = dr.async_get(hass)
        if device_entry := device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac_adress), entry.entry_id
        ):
            old_device_id = next(
                (
                    device_id
                    for domain, device_id in device_entry.identifiers
                    if domain == DOMAIN
                ),
            )

            @callback
            def update_unique_id(
                entity_entry: er.RegistryEntry,
            ) -> dict[str, str] | None:
                """Update unique id from device_id to mac address."""
                if old_device_id and entity_entry.unique_id.startswith(old_device_id):
                    suffix = entity_entry.unique_id.removeprefix(old_device_id)
                    new_unique_id = f"{mac_adress}{suffix}"
                    return {"new_unique_id": new_unique_id}
                return None

            await er.async_migrate_entries(hass, entry.entry_id, update_unique_id)

            new_identifiers = device_entry.identifiers.copy()
            new_identifiers.discard((DOMAIN, old_device_id))
            new_identifiers.add((DOMAIN, mac_adress))
            device_registry.async_update_device(
                device_entry.id, new_identifiers=new_identifiers
            )

        hass.config_entries.async_update_entry(
            entry, version=new_version, minor_version=new_minor_version
        )

    if entry.version == 2:
        new_version = 3
        new_minor_version = 1
        new_data = {**entry.data}

        if "advanced_settings" in new_data:
            new_data[SECTION_ADDITIONAL_SETTINGS] = new_data.pop("advanced_settings")

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            version=new_version,
            minor_version=new_minor_version,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Unload a config entry."""
    unload_state = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    # Clean up legacy session if needed
    if unload_state and entry.runtime_data.owns_session:
        await entry.runtime_data.session.close()

    return unload_state
