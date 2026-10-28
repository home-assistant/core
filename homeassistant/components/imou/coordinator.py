"""Provides the Imou DataUpdateCoordinator."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import override

from pyimouapi.device import ImouDevice
from pyimouapi.exceptions import ImouException, InvalidAppIdOrSecretException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_TIMEOUT, imou_device_identifier

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)
_QUOTA_CODE = "OP1013"

type ImouConfigEntry = ConfigEntry[ImouDataUpdateCoordinator]


class ImouDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for Imou devices."""

    config_entry: ImouConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        device_manager: ImouHaDeviceManager,
        config_entry: ImouConfigEntry,
    ) -> None:
        """Initialize the Imou data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ImouDataUpdateCoordinator",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
            always_update=True,
        )
        self._device_manager = device_manager
        self.devices_by_key: dict[str, ImouHaDevice] = {}
        self._devices_initialized = False
        self._ability_refs_pending: set[str] = set()
        self.new_device_callbacks: list[Callable[[list[ImouHaDevice]], None]] = []
        self.open_api_quota_exceeded = False

    @property
    def devices(self) -> list[ImouHaDevice]:
        """Return the list of devices."""
        return list(self.devices_by_key.values())

    @property
    def device_manager(self) -> ImouHaDeviceManager:
        """Return the device manager."""
        return self._device_manager

    @callback
    def register_new_device_callback(
        self, callback_func: Callable[[list[ImouHaDevice]], None]
    ) -> Callable[[], None]:
        """Register a callback for new devices and return an unregister callback."""
        self.new_device_callbacks.append(callback_func)

        @callback
        def remove_callback() -> None:
            self.new_device_callbacks.remove(callback_func)

        return remove_callback

    def get_device(self, device_key: str) -> ImouHaDevice | None:
        """Return the current device for device_key, if still on the account."""
        return self.devices_by_key.get(device_key)

    async def _async_list_devices(
        self, fetch_ability_refs: bool | set[str]
    ) -> tuple[list[ImouHaDevice], set[str]]:
        """List devices and note which ability-ref reads failed.

        A failed read is logged by the library and the device is still
        returned. The device id is only available where that read runs.
        """
        failed: set[str] = set()
        delegate = self._device_manager.delegate
        # pyimouapi keeps this callback private. It is the only place a single
        # device's failed ability-ref read can be told apart from the list.
        update_refs = getattr(delegate, "_async_update_device_ability_refs", None)
        if update_refs is not None and fetch_ability_refs is not False:

            async def noting(imou_device: ImouDevice) -> None:
                try:
                    await update_refs(imou_device)
                except Exception:
                    failed.add(imou_device.device_id)
                    raise

            delegate._async_update_device_ability_refs = noting  # noqa: SLF001
        try:
            async with asyncio.timeout(UPDATE_TIMEOUT):
                devices = await self._device_manager.async_get_devices(
                    fetch_ability_refs=fetch_ability_refs
                )
        except TimeoutError as err:
            self.open_api_quota_exceeded = False
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_timeout",
            ) from err
        except InvalidAppIdOrSecretException as err:
            self.open_api_quota_exceeded = False
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except ImouException as err:
            raise self._update_failed(err, "fetch_devices_failed") from err
        finally:
            if update_refs is not None and fetch_ability_refs is not False:
                delegate._async_update_device_ability_refs = update_refs  # noqa: SLF001
        return devices, failed

    def _remember_unresolved(self, asked: bool | set[str], failed: set[str]) -> None:
        """Keep asking for ability refs that did not load."""
        if asked is False:
            return
        if asked is True:
            self._ability_refs_pending = set(failed)
            return
        self._ability_refs_pending.difference_update(asked)
        self._ability_refs_pending.update(failed)

    def _drop_unresolved_new_devices(
        self,
        fresh_by_key: dict[str, ImouHaDevice],
        failed: set[str],
    ) -> None:
        """Leave out devices whose entities cannot be created yet."""
        if not failed:
            return
        for key, device in list(fresh_by_key.items()):
            if device.device_id in failed and key not in self.devices_by_key:
                del fresh_by_key[key]

    @override
    async def _async_update_data(self) -> None:
        """Update coordinator data."""
        # Ability refs decide which entities to create. Ask again only for a
        # device that is new or whose last read failed.
        if not self._devices_initialized:
            fetch: bool | set[str] = True
        elif self._ability_refs_pending:
            fetch = set(self._ability_refs_pending)
        else:
            fetch = False

        fresh_devices, failed = await self._async_list_devices(fetch)
        self._remember_unresolved(fetch, failed)
        fresh_by_key = {
            imou_device_identifier(device): device for device in fresh_devices
        }
        self._drop_unresolved_new_devices(fresh_by_key, failed)
        if self._devices_initialized and (
            new_keys := set(fresh_by_key) - set(self.devices_by_key)
        ):
            new_ids = {fresh_by_key[key].device_id for key in new_keys}
            if fetch is False:
                missing = new_ids
            elif fetch is True:
                missing = set()
            else:
                missing = new_ids - fetch
            if missing:
                detailed, failed_detail = await self._async_list_devices(missing)
                self._remember_unresolved(missing, failed_detail)
                detailed_by_key = {
                    imou_device_identifier(device): device for device in detailed
                }
                for key in new_keys:
                    if key not in fresh_by_key:
                        continue
                    if fresh_by_key[key].device_id not in missing:
                        continue
                    if (
                        fresh_by_key[key].device_id in failed_detail
                        or key not in detailed_by_key
                    ):
                        fresh_by_key.pop(key)
                    else:
                        fresh_by_key[key] = detailed_by_key[key]
        self._async_add_remove_devices(fresh_by_key)
        devices = list(self.devices_by_key.values())
        if not devices:
            self.open_api_quota_exceeded = False
            return

        try:
            async with asyncio.timeout(UPDATE_TIMEOUT):
                await self._device_manager.async_update_devices_status(devices)
        except TimeoutError as err:
            self.open_api_quota_exceeded = False
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_timeout",
            ) from err
        except InvalidAppIdOrSecretException as err:
            self.open_api_quota_exceeded = False
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except ImouException as err:
            raise self._update_failed(err, "update_devices_failed") from err

        self.open_api_quota_exceeded = False

    def _update_failed(
        self, error: ImouException, translation_key: str
    ) -> UpdateFailed:
        """Record whether this failure is a used-up monthly quota."""
        if _quota_exceeded(error):
            self.open_api_quota_exceeded = True
            translation_key = "quota_exceeded"
        else:
            self.open_api_quota_exceeded = False
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key=translation_key,
        )

    def _async_add_remove_devices(self, fresh_by_key: dict[str, ImouHaDevice]) -> None:
        """Add new devices, remove devices no longer in the account.

        This only tracks which devices exist on the account; per-device state
        is updated in place by `async_update_devices_status`, so devices that
        remain on the account keep their existing object and are not replaced.
        """
        if not self._devices_initialized:
            self.devices_by_key = fresh_by_key
            self._devices_initialized = True
            return

        current_keys = set(fresh_by_key)
        known_keys = set(self.devices_by_key)

        if current_keys == known_keys:
            return

        if removed_keys := known_keys - current_keys:
            _LOGGER.debug("Removed Imou device(s): %s", ", ".join(removed_keys))
            device_registry = dr.async_get(self.hass)
            for device_key in removed_keys:
                del self.devices_by_key[device_key]
                if device := device_registry.async_get_device_by_identifier(
                    (DOMAIN, device_key), self.config_entry.entry_id
                ):
                    device_registry.async_remove_device(device.id)

        if new_keys := current_keys - known_keys:
            _LOGGER.debug("New Imou device(s) found: %s", ", ".join(new_keys))
            new_devices = []
            for device_key in new_keys:
                self.devices_by_key[device_key] = fresh_by_key[device_key]
                new_devices.append(fresh_by_key[device_key])
            for new_device_callback in self.new_device_callbacks:
                new_device_callback(new_devices)


def _quota_exceeded(error: ImouException) -> bool:
    """Return True when the Open Platform monthly call limit is used up."""
    return _QUOTA_CODE in error.message
