"""The nuki component."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Generic, TypeVar

from aiohttp import web
from pynuki import NukiBridge, NukiLock, NukiOpener
from pynuki.bridge import InvalidCredentialsException
from pynuki.device import NukiDevice
from requests.exceptions import RequestException

from homeassistant import exceptions
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.network import NoURLAvailableError, get_url
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
from .helpers import NukiWebhookException, parse_id

_NukiDeviceT = TypeVar("_NukiDeviceT", bound=NukiDevice)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]
UPDATE_INTERVAL = timedelta(seconds=30)


def _get_bridge_devices(bridge: NukiBridge) -> tuple[list[NukiLock], list[NukiOpener]]:
    return bridge.locks, bridge.openers


async def _create_webhook(
    hass: HomeAssistant, entry: ConfigEntry, bridge: NukiBridge
) -> None:
    # Create HomeAssistant webhook
    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle webhook callback."""
        try:
            data = await request.json()
        except ValueError:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        locks = hass.data[DOMAIN][entry.entry_id][DATA_LOCKS]
        openers = hass.data[DOMAIN][entry.entry_id][DATA_OPENERS]

        devices = [x for x in locks + openers if x.nuki_id == data["nukiId"]]
        if len(devices) == 1:
            devices[0].update_from_callback(data)

        coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        coordinator.async_set_updated_data(None)

        return web.Response(status=HTTPStatus.OK)

    webhook.async_register(
        hass, DOMAIN, entry.title, entry.entry_id, handle_webhook, local_only=True
    )

    webhook_url = webhook.async_generate_path(entry.entry_id)

    try:
        hass_url = get_url(
            hass,
            allow_cloud=False,
            allow_external=False,
            allow_ip=True,
            require_ssl=False,
        )
    except NoURLAvailableError:
        webhook.async_unregister(hass, entry.entry_id)
        raise NukiWebhookException(
            f"Error registering URL for webhook {entry.entry_id}: "
            "HomeAssistant URL is not available"
        ) from None

    url = f"{hass_url}{webhook_url}"

    if hass_url.startswith("https"):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "https_webhook",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="https_webhook",
            translation_placeholders={
                "base_url": hass_url,
                "network_link": "https://my.home-assistant.io/redirect/network/",
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, "https_webhook")

        try:
            async with asyncio.timeout(10):
                await hass.async_add_executor_job(
                    _register_webhook, bridge, entry.entry_id, url
                )
        except InvalidCredentialsException as err:
            webhook.async_unregister(hass, entry.entry_id)
            raise NukiWebhookException(
                f"Invalid credentials for Bridge: {err}"
            ) from err
        except RequestException as err:
            webhook.async_unregister(hass, entry.entry_id)
            raise NukiWebhookException(
                f"Error communicating with Bridge: {err}"
            ) from err


def _register_webhook(bridge: NukiBridge, entry_id: str, url: str) -> bool:
    # Register HA URL as webhook if not already
    callbacks = bridge.callback_list()
    for item in callbacks["callbacks"]:
        if entry_id in item["url"]:
            if item["url"] == url:
                return True
            bridge.callback_remove(item["id"])

    if bridge.callback_add(url)["success"]:
        return True

    return False


def _remove_webhook(bridge: NukiBridge, entry_id: str) -> None:
    # Remove webhook if set
    callbacks = bridge.callback_list()
    for item in callbacks["callbacks"]:
        if entry_id in item["url"]:
            bridge.callback_remove(item["id"])


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

    try:
        await _create_webhook(hass, entry, bridge)
    except NukiWebhookException as err:
        _LOGGER.warning("Error registering HomeAssistant webhook: %s", err)

    async def _stop_nuki(_: Event):
        """Stop and remove the Nuki webhook."""
        webhook.async_unregister(hass, entry.entry_id)
        try:
            async with asyncio.timeout(10):
                await hass.async_add_executor_job(
                    _remove_webhook, bridge, entry.entry_id
                )
        except InvalidCredentialsException as err:
            _LOGGER.error(
                "Error unregistering webhook, invalid credentials for bridge: %s", err
            )
        except RequestException as err:
            _LOGGER.error("Error communicating with bridge: %s", err)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_nuki)
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
    webhook.async_unregister(hass, entry.entry_id)
    try:
        async with asyncio.timeout(10):
            await hass.async_add_executor_job(
                _remove_webhook,
                hass.data[DOMAIN][entry.entry_id][DATA_BRIDGE],
                entry.entry_id,
            )
    except InvalidCredentialsException as err:
        raise UpdateFailed(
            f"Unable to remove callback. Invalid credentials for Bridge: {err}"
        ) from err
    except RequestException as err:
        raise UpdateFailed(
            f"Unable to remove callback. Error communicating with Bridge: {err}"
        ) from err

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
            async with asyncio.timeout(10):
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
    def device_info(self) -> DeviceInfo:
        """Device info for Nuki entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, parse_id(self._nuki_device.nuki_id))},
            name=self._nuki_device.name,
            manufacturer="Nuki Home Solutions GmbH",
            model=self._nuki_device.device_model_str.capitalize(),
            sw_version=self._nuki_device.firmware_version,
            via_device=(DOMAIN, self.coordinator.bridge_id),
        )
