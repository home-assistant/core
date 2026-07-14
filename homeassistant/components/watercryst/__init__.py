"""The WATERCryst integration."""

from dataclasses import dataclass

from pyocat import AsyncApiClient, AsyncAuth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_MODEL_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_BLE_MAC,
    CONF_BSN,
    CONF_ESN,
    CONF_FW_VERSION,
    CONF_HW_VERSION,
    CONF_LATEST_FW_VERSION,
    CONF_LINE,
    CONF_SERIES,
    CONF_SYSTEM_MAC,
    DOMAIN,
)
from .coordinator import MeasurementsUpdateCoordinator, StateUpdateCoordinator

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


@dataclass
class RuntimeData:
    """Strongly typed runtime data container."""

    bsn: str
    esn: str | None
    device_type_number: str | None
    line: str | None
    series: str | None
    name: str | None
    fw_version: str | None
    hw_version: str | None
    latest_fw_version: str | None
    system_mac: str | None
    ble_mac: str | None
    device_info: DeviceInfo
    client: AsyncApiClient
    measurements: MeasurementsUpdateCoordinator
    state: StateUpdateCoordinator


type WatercrystConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: WatercrystConfigEntry) -> bool:
    """Set up a WATERCryst BIOCAT device from a config entry."""

    bsn: str = entry.data[CONF_BSN]
    key: str = entry.data[CONF_API_KEY]
    esn: str | None = entry.data[CONF_ESN]
    device_type_number: str | None = entry.data[CONF_MODEL_ID]
    line: str | None = entry.data[CONF_LINE]
    series: str | None = entry.data[CONF_SERIES]
    name: str | None = entry.data[CONF_NAME]
    fw_version: str | None = entry.data[CONF_FW_VERSION]
    hw_version: str | None = entry.data[CONF_HW_VERSION]
    latest_fw_version: str | None = entry.data[CONF_LATEST_FW_VERSION]
    system_mac: str | None = entry.data[CONF_SYSTEM_MAC]
    ble_mac: str | None = entry.data[CONF_BLE_MAC]

    auth = AsyncAuth(client=get_async_client(hass), api_key=key)
    client = AsyncApiClient(auth=auth)

    connections: set[tuple[str, str]] = set()

    if system_mac:
        connections.add((CONNECTION_NETWORK_MAC, system_mac))

    if ble_mac:
        connections.add((CONNECTION_BLUETOOTH, ble_mac))

    device_info = DeviceInfo(
        identifiers={(DOMAIN, bsn)},
        connections=connections,
        manufacturer="WATERCryst",
        model=f"{line} {series}",
        model_id=device_type_number,
        name=name,
        serial_number=bsn,
        sw_version=fw_version,
        hw_version=hw_version,
        configuration_url=f"https://app.watercryst.com/devices/{bsn}",
    )

    measurements = MeasurementsUpdateCoordinator(hass=hass, entry=entry, client=client)
    state = StateUpdateCoordinator(hass=hass, entry=entry, client=client)

    await measurements.async_config_entry_first_refresh()
    await state.async_config_entry_first_refresh()

    entry.runtime_data = RuntimeData(
        bsn=bsn,
        esn=esn,
        device_type_number=device_type_number,
        line=line,
        series=series,
        name=name,
        fw_version=fw_version,
        hw_version=hw_version,
        latest_fw_version=latest_fw_version,
        system_mac=system_mac,
        ble_mac=ble_mac,
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
