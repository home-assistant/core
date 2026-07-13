"""The WATERCryst integration."""

from dataclasses import dataclass

from pyocat import AsyncApiClient, AsyncAuth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_BSN,
    CONF_ESN,
    CONF_FW_VERSION,
    CONF_LATEST_FW_VERSION,
    CONF_LINE,
    CONF_SERIES,
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
    line: str | None
    series: str | None
    name: str | None
    fw_version: str | None
    latest_fw_version: str | None
    device_info: DeviceInfo
    client: AsyncApiClient
    measurements: MeasurementsUpdateCoordinator
    state: StateUpdateCoordinator


type WatercrystConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: WatercrystConfigEntry) -> bool:
    """Set up a WATERCryst Biocat device from a config entry."""

    bsn: str = entry.data[CONF_BSN]
    key: str = entry.data[CONF_API_KEY]
    esn: str | None = entry.data[CONF_ESN]
    line: str | None = entry.data[CONF_LINE]
    series: str | None = entry.data[CONF_SERIES]
    name: str | None = entry.data[CONF_NAME]
    fw_version: str | None = entry.data[CONF_FW_VERSION]
    latest_fw_version: str | None = entry.data[CONF_LATEST_FW_VERSION]

    auth = AsyncAuth(client=get_async_client(hass), api_key=key)
    client = AsyncApiClient(auth=auth)

    device_info = DeviceInfo(
        identifiers={(DOMAIN, bsn)},
        manufacturer="WATERCryst",
        model=f"{line} {series}",
        model_id="TODO",
        name=name,
        serial_number=bsn,
        sw_version=fw_version,
        hw_version="TODO",
    )

    measurements = MeasurementsUpdateCoordinator(hass=hass, entry=entry, client=client)
    state = StateUpdateCoordinator(hass=hass, entry=entry, client=client)

    await measurements.async_config_entry_first_refresh()
    await state.async_config_entry_first_refresh()

    entry.runtime_data = RuntimeData(
        bsn=bsn,
        esn=esn,
        line=line,
        series=series,
        name=name,
        fw_version=fw_version,
        latest_fw_version=latest_fw_version,
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
