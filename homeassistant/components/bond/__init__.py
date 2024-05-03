"""The Bond integration."""

from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientTimeout
from bond_async import Bond, BPUPSubscriptions, start_bpup

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import SLOW_UPDATE_WARNING

from .const import BRIDGE_MAKE, DOMAIN
from .models import BondData
from .utils import BondHub

PLATFORMS = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SWITCH,
]
_API_TIMEOUT = SLOW_UPDATE_WARNING - 1

_LOGGER = logging.getLogger(__name__)

BondConfigEntry = ConfigEntry[BondData]


async def async_setup_entry(hass: HomeAssistant, entry: BondConfigEntry) -> bool:
    """Set up Bond from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_ACCESS_TOKEN]
    config_entry_id = entry.entry_id

    bond = Bond(
        host=host,
        token=token,
        timeout=ClientTimeout(total=_API_TIMEOUT),
        session=async_get_clientsession(hass),
    )
    hub = BondHub(bond, host)
    try:
        await hub.setup()
    except ClientResponseError as ex:
        if ex.status == HTTPStatus.UNAUTHORIZED:
            _LOGGER.error("Bond token no longer valid: %s", ex)
            return False
        raise ConfigEntryNotReady from ex
    except (ClientError, TimeoutError, OSError) as error:
        raise ConfigEntryNotReady from error

    bpup_subs = BPUPSubscriptions()
    stop_bpup = await start_bpup(host, bpup_subs)

    @callback
    def _async_stop_event(*_: Any) -> None:
        stop_bpup()

    entry.async_on_unload(_async_stop_event)
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_stop_event)
    )
    entry.runtime_data = BondData(hub, bpup_subs)

    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=hub.bond_id)

    assert hub.bond_id is not None
    hub_name = hub.name or hub.bond_id
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, hub.bond_id)},
        manufacturer=BRIDGE_MAKE,
        name=hub_name,
        model=hub.target,
        sw_version=hub.fw_ver,
        hw_version=hub.mcu_ver,
        suggested_area=hub.location,
        configuration_url=f"http://{host}",
    )

    _async_remove_old_device_identifiers(config_entry_id, device_registry, hub)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BondConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def _async_remove_old_device_identifiers(
    config_entry_id: str, device_registry: dr.DeviceRegistry, hub: BondHub
) -> None:
    """Remove the non-unique device registry entries."""
    for device in hub.devices:
        dev = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
        if dev is None:
            continue
        if config_entry_id in dev.config_entries:
            device_registry.async_remove_device(dev.id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: BondConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove bond config entry from a device."""
    data = config_entry.runtime_data
    hub = data.hub
    for identifier in device_entry.identifiers:
        if identifier[0] != DOMAIN or len(identifier) != 3:
            continue
        bond_id: str = identifier[1]  # type: ignore[unreachable]
        # Bond still uses the 3 arg tuple before
        # the identifiers were typed
        device_id: str = identifier[2]
        # If device_id is no longer present on
        # the hub, we allow removal.
        if hub.bond_id != bond_id or not any(
            device_id == device.device_id for device in hub.devices
        ):
            return True
    return False
