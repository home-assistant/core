"""The BSB-LAN integration."""

import dataclasses

from awesomeversion import AwesomeVersion
from bsblan import (
    BSBLAN,
    BSBLANAuthError,
    BSBLANConfig,
    BSBLANConnectionError,
    BSBLANError,
    BSBLANVersionError,
    Device,
    Info,
    StaticState,
)
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_HEATING_CIRCUITS,
    CONF_PASSKEY,
    DEFAULT_HEATING_CIRCUITS,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)
from .coordinator import BSBLanFastCoordinator, BSBLanSlowCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.BUTTON, Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]
ISSUE_OUTDATED_FIRMWARE = "outdated_firmware"

# JSON-API version (reported by /JV) at or above which the device exposes the
# full feature set. Below this, the library operates in a reduced
# single-circuit mode and we surface a repair issue recommending an upgrade.
MINIMUM_FULL_API_VERSION = AwesomeVersion("2.0")

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type BSBLanConfigEntry = ConfigEntry[BSBLanData]


@dataclasses.dataclass
class BSBLanData:
    """BSBLan data stored in the Home Assistant data object."""

    fast_coordinator: BSBLanFastCoordinator
    slow_coordinator: BSBLanSlowCoordinator
    client: BSBLAN
    device: Device
    info: Info
    static: dict[int, StaticState | None]
    available_circuits: list[int]


def get_bsblan_device_info(
    device: Device, info: Info, host: str, port: int
) -> DeviceInfo:
    """Build DeviceInfo for the main BSB-LAN controller device."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.MAC)},
        connections={(CONNECTION_NETWORK_MAC, device.MAC)},
        name=device.name,
        manufacturer="BSBLAN Inc.",
        model=(
            info.device_identification.value
            if info.device_identification and info.device_identification.value
            else None
        ),
        model_id=(
            f"{info.controller_family.value}_{info.controller_variant.value}"
            if info.controller_family
            and info.controller_variant
            and info.controller_family.value
            and info.controller_variant.value
            else None
        ),
        sw_version=device.version,
        configuration_url=str(URL.build(scheme="http", host=host, port=port)),
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the BSB-LAN integration."""
    async_setup_services(hass)
    return True


def _issue_id_for_entry(entry_id: str) -> str:
    """Build issue id for a config entry."""
    return f"{ISSUE_OUTDATED_FIRMWARE}_{entry_id}"


def _is_reduced_api_mode(json_api_version: str | None) -> bool:
    """Return whether the device runs in reduced (single-circuit) JSON-API mode.

    Devices reporting a JSON-API version below v2 expose only a reduced feature
    set limited to a single heating circuit.
    """
    return (
        json_api_version is not None
        and AwesomeVersion(json_api_version) < MINIMUM_FULL_API_VERSION
    )


def _async_manage_outdated_firmware_issue(
    hass: HomeAssistant,
    entry: BSBLanConfigEntry,
    firmware_version: str,
    json_api_version: str | None,
) -> None:
    """Create or remove the outdated firmware repair issue for an entry.

    Devices reporting a JSON-API version below v2 run with a reduced feature
    set, so we recommend the user upgrades the firmware for full support.
    """
    issue_id = _issue_id_for_entry(entry.entry_id)
    if _is_reduced_api_mode(json_api_version):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_OUTDATED_FIRMWARE,
            translation_placeholders={"firmware_version": firmware_version},
            learn_more_url="https://github.com/fredlcore/BSB-LAN/releases",
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_setup_entry(hass: HomeAssistant, entry: BSBLanConfigEntry) -> bool:
    """Set up BSB-LAN from a config entry."""

    # create config using BSBLANConfig
    config = BSBLANConfig(
        host=entry.data[CONF_HOST],
        passkey=entry.data[CONF_PASSKEY],
        port=entry.data[CONF_PORT],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    # create BSBLAN client
    session = async_get_clientsession(hass)
    bsblan = BSBLAN(config=config, session=session)

    try:
        # Initialize the client. This validates the connection and fetches the
        # firmware and JSON-API versions. The library selects the full or the
        # reduced (single-circuit) feature set from the JSON-API version, and
        # raises BSBLANVersionError when no supported version is available.
        await bsblan.initialize()

        # Read available heating circuits from config entry data
        # (populated by config flow or migration)
        circuits: list[int] = entry.data[CONF_HEATING_CIRCUITS] or list(
            DEFAULT_HEATING_CIRCUITS
        )

        # Devices reporting a JSON-API version below v2 operate in a reduced
        # single-circuit mode. A previously configured entry may still list
        # additional circuits from when the device ran newer firmware, which
        # would make setup fail when fetching those now-unsupported circuits.
        # Restrict to the default single circuit so the integration still loads.
        if _is_reduced_api_mode(bsblan.json_api_version):
            circuits = list(DEFAULT_HEATING_CIRCUITS)

        # Fetch device metadata
        device = await bsblan.device()
        info = await bsblan.info()
    except BSBLANConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    except BSBLANAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_auth_error",
        ) from err
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    except BSBLANVersionError as err:
        # The device does not report a supported JSON-API version, so the
        # integration cannot operate. Surface a clear, actionable error.
        firmware_version = bsblan.device_info.version if bsblan.device_info else None
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_outdated_firmware",
            translation_placeholders={
                "firmware_version": firmware_version or "unknown"
            },
        ) from err
    except BSBLANError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_general_error",
        ) from err

    # Devices below JSON-API v2 operate with a reduced single-circuit feature
    # set. Surface (or clear) the repair issue recommending a firmware upgrade.
    _async_manage_outdated_firmware_issue(
        hass, entry, device.version, bsblan.json_api_version
    )

    # Fetch static values per configured circuit.
    # BSB-LAN is a serial bus — it processes one parameter at a time,
    # so concurrent requests offer no speed benefit over sequential.
    # Static values are optional — some devices may not support them.
    static_per_circuit: dict[int, StaticState | None] = {}
    for circuit in circuits:
        try:
            static_per_circuit[circuit] = await bsblan.static_values(circuit=circuit)
        except (BSBLANError, TimeoutError) as err:
            LOGGER.debug(
                "Static values not available for %s circuit %d: %s",
                entry.data[CONF_HOST],
                circuit,
                err,
            )
            static_per_circuit[circuit] = None

    # Create coordinators with the already-initialized client
    fast_coordinator = BSBLanFastCoordinator(hass, entry, bsblan, circuits)
    slow_coordinator = BSBLanSlowCoordinator(hass, entry, bsblan)

    # Perform first refresh of fast coordinator (required for entities)
    await fast_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = BSBLanData(
        client=bsblan,
        fast_coordinator=fast_coordinator,
        slow_coordinator=slow_coordinator,
        device=device,
        info=info,
        static=static_per_circuit,
        available_circuits=circuits,
    )

    # Fetch slow data in the background so it does not block startup.
    entry.async_create_background_task(
        hass,
        slow_coordinator.async_refresh(),
        name=f"{DOMAIN}_slow_data_fetch_{entry.entry_id}",
    )

    # Register main device before forwarding platforms, so sub-devices
    # (heating circuits, water heater) can reference it via via_device
    device_registry = dr.async_get(hass)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    main_device_info = get_bsblan_device_info(device, info, entry.data[CONF_HOST], port)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=main_device_info["identifiers"],
        connections=main_device_info["connections"],
        name=main_device_info["name"],
        manufacturer=main_device_info["manufacturer"],
        model=main_device_info.get("model"),
        model_id=main_device_info.get("model_id"),
        sw_version=main_device_info.get("sw_version"),
        configuration_url=main_device_info.get("configuration_url"),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BSBLanConfigEntry) -> bool:
    """Unload BSBLAN config entry."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id_for_entry(entry.entry_id))
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: BSBLanConfigEntry) -> bool:
    """Migrate old config entries to the latest schema."""
    LOGGER.debug(
        "Migrating BSB-LAN entry from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    # 1.1 -> 1.2: Add CONF_HEATING_CIRCUITS. Attempt to discover available
    # heating circuits from the device; fall back to [1] (pre-multi-circuit
    # default) if the device is unreachable or the endpoint is unsupported.
    if entry.version == 1 and entry.minor_version < 2:
        circuits: list[int] = list(DEFAULT_HEATING_CIRCUITS)
        config = BSBLANConfig(
            host=entry.data[CONF_HOST],
            passkey=entry.data[CONF_PASSKEY],
            port=entry.data[CONF_PORT],
            username=entry.data.get(CONF_USERNAME),
            password=entry.data.get(CONF_PASSWORD),
        )
        session = async_get_clientsession(hass)
        bsblan = BSBLAN(config=config, session=session)
        try:
            await bsblan.initialize()
            circuits = await bsblan.get_available_circuits()
        except (BSBLANError, TimeoutError) as err:
            LOGGER.warning(
                "Circuit discovery during migration failed for %s (%s); "
                "defaulting to a single circuit. Use Reconfigure to "
                "rediscover additional circuits later",
                entry.data[CONF_HOST],
                err,
            )
        if not circuits:
            LOGGER.warning(
                "Circuit discovery during migration returned no heating circuits "
                "for %s; defaulting to a single circuit",
                entry.data[CONF_HOST],
            )
            circuits = list(DEFAULT_HEATING_CIRCUITS)

        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_HEATING_CIRCUITS: circuits},
            minor_version=2,
        )
        LOGGER.debug(
            "Migrated BSB-LAN entry to version %s.%s with circuits %s",
            entry.version,
            entry.minor_version,
            circuits,
        )

    # 1.2 -> 1.3: Repair entries that stored an empty circuit list during
    # discovery. Every BSB-LAN setup has at least one heating circuit.
    if entry.version == 1 and entry.minor_version < 3:
        if not entry.data[CONF_HEATING_CIRCUITS]:
            LOGGER.warning(
                "Stored heating circuits for %s are empty; defaulting to a "
                "single circuit",
                entry.data[CONF_HOST],
            )
            data = {
                **entry.data,
                CONF_HEATING_CIRCUITS: list(DEFAULT_HEATING_CIRCUITS),
            }
        else:
            data = {**entry.data}

        hass.config_entries.async_update_entry(entry, data=data, minor_version=3)

    return True
