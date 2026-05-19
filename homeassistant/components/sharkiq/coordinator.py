# Data update coordinator for shark iq vacuums.

import asyncio
from datetime import datetime, timedelta

from .sharkiq_pypi.sharkiq import (
    AylaApi,
    SharkIqAuthError,
    SharkIqAuthExpiringError,
    SharkIqNotAuthedError,
    SharkIqVacuum,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DOMAIN, LOGGER, UPDATE_INTERVAL
from .skegox_api import SkegoxApi, SkegoxApiError
from .skegox_auth import SkegoxAuthError, SkegoxAuthManager
from .skegox_device import SkegoxDevice

type SharkIqConfigEntry = ConfigEntry[SharkIqUpdateCoordinator | SkegoxUpdateCoordinator]
type SharkDevice = SharkIqVacuum | SkegoxDevice

# Return the device model number, preferring vac_model_number over oem_model_number.
def get_device_model(device: SharkDevice) -> str:
    if device.vac_model_number:
        return device.vac_model_number
    return device.oem_model_number

# Base coordinator shared by Ayla and Skegox backends.
class BaseSharkIqCoordinator(DataUpdateCoordinator[bool]):
    config_entry: SharkIqConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SharkIqConfigEntry,
    ) -> None:
        # Set up the base coordinator.

        # shark_vacs -> is keyed by device serial number (DSN).
        self.shark_vacs: dict[str, SharkDevice] = {}
        # _online_dsns -> tracks which DSNs are currently reachable.
        self._online_dsns: set[str] = set()

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    # Get the set of all online DSNs.
    @property
    def online_dsns(self) -> set[str]:
        return self._online_dsns
    # Return the online state of a given vacuum dsn.
    def device_is_online(self, dsn: str) -> bool:
        return dsn in self._online_dsns

# Define a wrapper class to update Shark IQ data via the Ayla API.
class SharkIqUpdateCoordinator(BaseSharkIqCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SharkIqConfigEntry,
        ayla_api: AylaApi,
        shark_vacs: list[SharkIqVacuum],
    ) -> None:
        # Set up the SharkIqUpdateCoordinator class.
        super().__init__(hass, config_entry)
        self.ayla_api = ayla_api
        self.shark_vacs: dict[str, SharkIqVacuum] = {
            sharkiq.serial_number: sharkiq for sharkiq in shark_vacs
        }

    # Asynchronously update the data for a single vacuum.
    @staticmethod
    async def _async_update_vacuum(sharkiq: SharkIqVacuum) -> None:
        dsn = sharkiq.serial_number
        LOGGER.debug("Updating sharkiq data for device DSN %s", dsn)
        async with asyncio.timeout(API_TIMEOUT):
            await sharkiq.async_update()
    
    # Update data device by device.
    async def _async_update_data(self) -> bool:
        try:
            # Refresh auth via two checks: the library's built-in flag and a
            # manual 10-minute-before-expiry window. Both are needed because
            # token_expiring_soon may not cover all expiry edge cases.
            if (
                self.ayla_api.token_expiring_soon
                or datetime.now()
                > self.ayla_api.auth_expiration - timedelta(seconds=600)
            ):
                await self.ayla_api.async_refresh_auth()

            all_vacuums = await self.ayla_api.async_list_devices()
            self._online_dsns = {
                v["dsn"]
                for v in all_vacuums
                if v["connection_status"] == "Online" and v["dsn"] in self.shark_vacs
            }

            LOGGER.debug("Updating sharkiq data")
            online_vacs = [self.shark_vacs[dsn] for dsn in self.online_dsns]
            await asyncio.gather(*[self._async_update_vacuum(v) for v in online_vacs])
        except (
            SharkIqAuthError,
            SharkIqNotAuthedError,
            SharkIqAuthExpiringError,
        ) as err:
            LOGGER.debug("Bad auth state.  Attempting re-auth", exc_info=err)
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            LOGGER.exception("Unexpected error updating SharkIQ.  Attempting re-auth")
            raise UpdateFailed(err) from err

        return True

# Define a wrapper class to update Shark IQ data via the Skegox API.
class SkegoxUpdateCoordinator(BaseSharkIqCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SharkIqConfigEntry,
        skegox_api: SkegoxApi,
        auth_manager: SkegoxAuthManager,
        devices: list[SkegoxDevice],
    ) -> None:
        # Set up the SkegoxUpdateCoordinator class.
        super().__init__(hass, config_entry)
        self.skegox_api = skegox_api
        self.auth_manager = auth_manager
        self.shark_vacs: dict[str, SkegoxDevice] = {
            device.serial_number: device for device in devices
        }
        self._mard_failed_dsns: set[str] = set()
        self._mard_retry_count: dict[str, int] = {}
        self._mard_retry_interval = 10

    # Get the list of all Skegox devices.
    @property
    def devices(self) -> list[SkegoxDevice]:
        return list(self.shark_vacs.values())

    # Update data for all Skegox devices.
    async def _async_update_data(self) -> bool:
        try:
            await self.auth_manager.ensure_authenticated()

            raw_devices = await self.skegox_api.get_all_devices()

            self._online_dsns = set()
            for raw in raw_devices:
                registry = raw.get("registry", {})
                connectivity = raw.get("connectivityStatus", {})

                snd = SkegoxDevice.extract_snd(registry)
                is_online = connectivity.get("connected", False)

                if is_online:
                    self._online_dsns.add(snd)

                existing = self.shark_vacs.get(snd)
                
                # Update in-place to preserve MARD/room data already loaded
                if existing:
                    existing.update_from_response(raw)
                # New device discovered during a running session
                else:
                    new_device = SkegoxDevice(self.skegox_api, raw)
                    self.shark_vacs[snd] = new_device

            for device in self.shark_vacs.values():
                snd = device.serial_number
                
                # avoid spamming the API for persistently missing data.
                if snd in self._mard_failed_dsns:
                    retry_count = self._mard_retry_count.get(snd, 0) + 1
                    self._mard_retry_count[snd] = retry_count
                    # Retries are throttled to every _mard_retry_interval cycles
                    if retry_count % self._mard_retry_interval != 0:
                        continue
                # Retry MARD fetch periodically after initial failure.
                if not device.room_polygons and not device.mard_data:
                    mard_body = await self.skegox_api.fetch_property_file(device.serial_number, "zones")
                    if mard_body:
                        device.load_mard(mard_body)
                        self._mard_failed_dsns.discard(device.serial_number)
                        self._mard_retry_count.pop(device.serial_number, None)
                    else:
                        self._mard_failed_dsns.add(device.serial_number)

            LOGGER.debug("Skegox update: %d devices, %d online", len(self.shark_vacs), len(self._online_dsns),)
        except SkegoxAuthError as err:
            LOGGER.debug("Skegox auth error during update", exc_info=err)
            raise ConfigEntryAuthFailed from err
        except SkegoxApiError as err:
            LOGGER.exception("Skegox API error during update")
            raise UpdateFailed(err) from err
        except Exception as err:
            LOGGER.exception("Unexpected error updating Skegox devices")
            raise UpdateFailed(err) from err

        return True