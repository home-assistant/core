"""The nuki component."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import logging
from typing import Generic, TypeVar

import async_timeout
from pynuki import NukiBridge, NukiLock, NukiOpener
from pynuki.bridge import InvalidCredentialsException
from pynuki.device import NukiDevice
from requests.exceptions import RequestException

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DATA_BRIDGE,
    DATA_COORDINATOR,
    DATA_LOCKS,
    DATA_OPENERS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ERROR_STATES,
)
from .helpers import parse_id

_NukiDeviceT = TypeVar("_NukiDeviceT", bound=NukiDevice)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]
UPDATE_INTERVAL = timedelta(seconds=30)


def _get_bridge_devices(bridge: NukiBridge) -> tuple[list[NukiLock], list[NukiOpener]]:
    return bridge.locks, bridge.openers


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Nuki entry."""

    hass.data.setdefault(DOMAIN, {})

    # Migration of entry unique_id
    if isinstance(entry.unique_id, int):
        new_id = parse_id(entry.unique_id)
        params = {"unique_id": new_id}
        if entry.title == entry.unique_id:
            params["title"] = new_id
        hass.config_entries.async_update_entry(entry, **params)

    try:
        bridge = await hass.async_add_executor_job(
            NukiBridge,
            entry.data[CONF_HOST],
            entry.data[CONF_TOKEN],
            entry.data[CONF_PORT],
            True,
            DEFAULT_TIMEOUT,
        )

        locks, openers = await hass.async_add_executor_job(_get_bridge_devices, bridge)
    except InvalidCredentialsException as err:
        raise exceptions.ConfigEntryAuthFailed from err
    except RequestException as err:
        raise exceptions.ConfigEntryNotReady from err

    # Device registration for the bridge
    info = bridge.info()
    bridge_id = parse_id(info["ids"]["hardwareId"])
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, bridge_id)},
        manufacturer="Nuki Home Solutions GmbH",
        name=f"Nuki Bridge {bridge_id}",
        model="Hardware Bridge",
        sw_version=info["versions"]["firmwareVersion"],
    )

    coordinator = NukiCoordinator(hass, bridge, locks, openers)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_BRIDGE: bridge,
        DATA_LOCKS: locks,
        DATA_OPENERS: openers,
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Nuki entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NukiCoordinator(DataUpdateCoordinator[None]):
    """Data Update Coordinator for the Nuki integration."""

    def __init__(self, hass, bridge, locks, openers):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="nuki devices",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=UPDATE_INTERVAL,
        )
        self.bridge = bridge
        self.locks = locks
        self.openers = openers

    @property
    def bridge_id(self):
        """Return the parsed id of the Nuki bridge."""
        return parse_id(self.bridge.info()["ids"]["hardwareId"])

    async def _async_update_data(self) -> None:
        """Fetch data from Nuki bridge."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                events = await self.hass.async_add_executor_job(
                    self.update_devices, self.locks + self.openers
                )
        except InvalidCredentialsException as err:
            raise UpdateFailed(f"Invalid credentials for Bridge: {err}") from err
        except RequestException as err:
            raise UpdateFailed(f"Error communicating with Bridge: {err}") from err

        ent_reg = er.async_get(self.hass)
        for event, device_ids in events.items():
            for device_id in device_ids:
                entity_id = ent_reg.async_get_entity_id(
                    Platform.LOCK, DOMAIN, device_id
                )
                event_data = {
                    "entity_id": entity_id,
                    "type": event,
                }
                self.hass.bus.async_fire("nuki_event", event_data)

    def update_devices(self, devices: list[NukiDevice]) -> dict[str, set[str]]:
        """Update the Nuki devices.

        Returns:
            A dict with the events to be fired. The event type is the key and the device ids are the value
        """

        events: dict[str, set[str]] = defaultdict(set)

        for device in devices:
            for level in (False, True):
                try:
                    if isinstance(device, NukiOpener):
                        last_ring_action_state = device.ring_action_state

                        device.update(level)

                        if not last_ring_action_state and device.ring_action_state:
                            events["ring"].add(device.nuki_id)
                    else:
                        device.update(level)
                except RequestException:
                    continue

                if device.state not in ERROR_STATES:
                    break

        return events


class NukiEntity(CoordinatorEntity[NukiCoordinator], Generic[_NukiDeviceT]):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator: NukiCoordinator, nuki_device: _NukiDeviceT) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._nuki_device = nuki_device

    @property
    def device_info(self):
        """Device info for Nuki entities."""
        return {
            "identifiers": {(DOMAIN, parse_id(self._nuki_device.nuki_id))},
            "name": self._nuki_device.name,
            "manufacturer": "Nuki Home Solutions GmbH",
            "model": self._nuki_device.device_model_str.capitalize(),
            "sw_version": self._nuki_device.firmware_version,
            "via_device": (DOMAIN, self.coordinator.bridge_id),
        }
