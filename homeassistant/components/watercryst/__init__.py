"""The WATERCryst integration."""

from dataclasses import dataclass

from httpx import HTTPStatusError, RequestError
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

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


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

    key: str = entry.data[CONF_API_KEY]
    auth = AsyncAuth(client=get_async_client(hass), api_key=key)
    client = AsyncApiClient(auth=auth)

    try:
        info = await client.get_device_info()
        initial_state = await client.get_state()
    except WTCApiUnauthorizedError as err:
        raise ConfigEntryAuthFailed("Invalid authentication") from err
    except WTCApiDisabledError as err:
        raise ConfigEntryError("API disabled") from err
    except WTCApiTemporaryError as err:
        raise ConfigEntryNotReady("Temporary API error") from err
    except RequestError as err:
        raise ConfigEntryNotReady("Temporary API error") from err
    except HTTPStatusError as err:
        raise ConfigEntryNotReady("Unexpected error") from err

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
    state.async_set_updated_data(initial_state)

    measurements = WatercrystMeasurementsUpdateCoordinator(
        hass=hass, config_entry=entry, client=client, state=state
    )
    await measurements.async_refresh()

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


async def async_unload_entry(hass: HomeAssistant, entry: WatercrystConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
