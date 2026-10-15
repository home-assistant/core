"""The WATERCryst integration."""

from dataclasses import dataclass

from httpx2 import HTTPStatusError, RequestError
from pyocat import (
    AsyncApiClient,
    AsyncAuth,
    WTCApiDisabledError,
    WTCApiTemporaryError,
    WTCApiUnauthorizedError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN
from .coordinator import (
    WatercrystMeasurementsUpdateCoordinator,
    WatercrystStateUpdateCoordinator,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class RuntimeData:
    """Strongly typed runtime data container."""

    biocat_serial_number: str
    has_flow_rate_sensor: bool
    has_leakage_protection_system: bool
    has_pressure_sensor: bool
    has_temperature_sensor: bool
    device_info: DeviceInfo
    client: AsyncApiClient
    measurements: WatercrystMeasurementsUpdateCoordinator
    state: WatercrystStateUpdateCoordinator


type WatercrystConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: WatercrystConfigEntry) -> bool:
    """Set up a WATERCryst BIOCAT device from a config entry."""

    client = AsyncApiClient(
        auth=AsyncAuth(client=get_async_client(hass), api_key=entry.data[CONF_API_KEY])
    )

    try:
        info = await client.get_device_info()
    except WTCApiUnauthorizedError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except WTCApiDisabledError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="api_disabled"
        ) from err
    except (WTCApiTemporaryError, RequestError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="temporary_api_error"
        ) from err
    except HTTPStatusError as err:
        if err.response.is_server_error:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="temporary_api_error"
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="unknown_error"
        ) from err

    connections: set[tuple[str, str]] = set()

    if info.system_mac_address:
        connections.add((CONNECTION_NETWORK_MAC, format_mac(info.system_mac_address)))

    device_info = DeviceInfo(
        identifiers={(DOMAIN, info.biocat_serial)},
        connections=connections,
        manufacturer="WATERCryst",
        model=" ".join(part for part in (info.line, info.series) if part) or None,
        model_id=info.device_type_number,
        name=info.name or entry.title,
        serial_number=info.biocat_serial,
        sw_version=info.current_firmware_version,
        hw_version=info.current_hardware_version,
        configuration_url=f"https://app.watercryst.com/devices/{info.biocat_serial}",
    )

    state = WatercrystStateUpdateCoordinator(
        hass=hass, config_entry=entry, client=client
    )
    await state.async_config_entry_first_refresh()

    measurements = WatercrystMeasurementsUpdateCoordinator(
        hass=hass, config_entry=entry, client=client, state=state
    )
    if state.data.online:
        await measurements.async_config_entry_first_refresh()

    entry.runtime_data = RuntimeData(
        biocat_serial_number=info.biocat_serial,
        has_flow_rate_sensor=info.has_flow_rate_sensor,
        has_leakage_protection_system=info.has_leakage_protection_system,
        has_pressure_sensor=info.has_pressure_sensor,
        has_temperature_sensor=info.has_temperature_sensor,
        device_info=device_info,
        client=client,
        measurements=measurements,
        state=state,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WatercrystConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
