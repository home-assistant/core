"""The WATERCryst integration."""

from dataclasses import dataclass

from httpx import HTTPStatusError
from pyocat import AsyncApiClient, AsyncAuth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_BSN, DOMAIN
from .coordinator import MeasurementsUpdateCoordinator, StateUpdateCoordinator

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


@dataclass
class RuntimeData:
    """Strongly typed runtime data container."""

    bsn: str
    device_info: DeviceInfo
    client: AsyncApiClient
    measurements: MeasurementsUpdateCoordinator
    state: StateUpdateCoordinator


type WatercrystConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: WatercrystConfigEntry) -> bool:
    """Set up a WATERCryst BIOCAT device from a config entry."""

    bsn: str = entry.data[CONF_BSN]
    key: str = entry.data[CONF_API_KEY]

    auth = AsyncAuth(client=get_async_client(hass), api_key=key)
    client = AsyncApiClient(auth=auth)

    try:
        # Fetch device related information like the model ID,
        # firmware version and user specified device name.
        info = await client.get_device_info()

        # BIOCAT serial entered by the user must match the
        # serial associated with the given API key.
        if info.biocat_serial != bsn:
            raise ConfigEntryAuthFailed("BIOCAT serial number mismatch")

        # Fetch the current device state to check if the
        # device is online.
        state = await client.get_state()

        if not state.online:
            raise ConfigEntryNotReady("Device is offline")

    except HTTPStatusError as err:
        match err.response.status_code:
            case 401:
                raise ConfigEntryAuthFailed("Invalid authentication") from err
            case 403:
                raise ConfigEntryError("API disabled") from err
            case _:
                raise ConfigEntryError("Unexpected error") from err

    connections: set[tuple[str, str]] = set()

    if info.system_mac_address:
        connections.add((CONNECTION_NETWORK_MAC, info.system_mac_address))

    if info.ble_mac_address:
        connections.add((CONNECTION_BLUETOOTH, info.ble_mac_address))

    device_info = DeviceInfo(
        identifiers={(DOMAIN, bsn)},
        connections=connections,
        manufacturer="WATERCryst",
        model=f"{info.line} {info.series}",
        model_id=info.device_type_number,
        name=info.name,
        serial_number=bsn,
        sw_version=info.fw_version,
        hw_version=info.hw_version,
        configuration_url=f"https://app.watercryst.com/devices/{bsn}",
    )

    measurements = MeasurementsUpdateCoordinator(hass=hass, entry=entry, client=client)
    state = StateUpdateCoordinator(hass=hass, entry=entry, client=client)

    await measurements.async_config_entry_first_refresh()
    await state.async_config_entry_first_refresh()

    entry.runtime_data = RuntimeData(
        bsn=bsn,
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
