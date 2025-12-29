"""Roborock Coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, TypeVar

from propcache.api import cached_property
from roborock import B01Props
from roborock.data import HomeDataScene
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.a01 import DyadApi, ZeoApi
from roborock.devices.traits.b01 import Q7PropertiesApi
from roborock.devices.traits.v1 import PropertiesApi
from roborock.exceptions import RoborockDeviceBusy, RoborockException
from roborock.roborock_message import (
    RoborockB01Props,
    RoborockDyadDataProtocol,
    RoborockZeoProtocol,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify

from .const import (
    A01_UPDATE_INTERVAL,
    DOMAIN,
    IMAGE_CACHE_INTERVAL,
    V1_CLOUD_IN_CLEANING_INTERVAL,
    V1_CLOUD_NOT_CLEANING_INTERVAL,
    V1_LOCAL_IN_CLEANING_INTERVAL,
    V1_LOCAL_NOT_CLEANING_INTERVAL,
)
from .models import DeviceState

SCAN_INTERVAL = timedelta(seconds=30)

# Roborock devices have a known issue where they go offline for a short period
# around 3AM local time for ~1 minute and reset both the local connection
# and MQTT connection. To avoid log spam, we will avoid reporting failures refreshing
# data until this duration has passed.
MIN_UNAVAILABLE_DURATION = timedelta(minutes=2)

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockCoordinators:
    """Roborock coordinators type."""

    v1: list[RoborockDataUpdateCoordinator]
    a01: list[RoborockDataUpdateCoordinatorA01]
    b01: list[RoborockDataUpdateCoordinatorB01]

    def values(
        self,
    ) -> list[
        RoborockDataUpdateCoordinator
        | RoborockDataUpdateCoordinatorA01
        | RoborockDataUpdateCoordinatorB01
    ]:
        """Return all coordinators."""
        return self.v1 + self.a01 + self.b01


type RoborockConfigEntry = ConfigEntry[RoborockCoordinators]


class RoborockDataUpdateCoordinator(DataUpdateCoordinator[DeviceState]):
    """Class to manage fetching data from the API."""

    config_entry: RoborockConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
        properties_api: PropertiesApi,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            # Assume we can use the local api.
            update_interval=V1_LOCAL_NOT_CLEANING_INTERVAL,
        )
        self._device = device
        self.properties_api = properties_api
        self.device_info = DeviceInfo(
            name=self._device.device_info.name,
            identifiers={(DOMAIN, self.duid)},
            manufacturer="Roborock",
            model=self._device.product.model,
            model_id=self._device.product.model,
            sw_version=self._device.device_info.fv,
        )
        if mac := properties_api.network_info.mac:
            self.device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
            }
        self.last_update_state: str | None = None
        # Keep track of last attempt to refresh maps/rooms to know when to try again.
        self._last_home_update_attempt: datetime
        self.last_home_update: datetime | None = None
        # Tracks the last successful update to control when we report failure
        # to the base class. This is reset on successful data update.
        self._last_update_success_time: datetime | None = None
        self._has_connected_locally: bool = False

    @cached_property
    def dock_device_info(self) -> DeviceInfo:
        """Gets the device info for the dock.

        This must happen after the coordinator does the first update.
        Which will be the case when this is called.
        """
        dock_type = self.properties_api.status.dock_type
        return DeviceInfo(
            name=f"{self._device.device_info.name} Dock",
            identifiers={(DOMAIN, f"{self.duid}_dock")},
            manufacturer="Roborock",
            model=f"{self._device.product.model} Dock",
            model_id=str(dock_type.value) if dock_type is not None else "Unknown",
            sw_version=self._device.device_info.fv,
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        await self._verify_api()
        try:
            await self.properties_api.status.refresh()
        except RoborockException as err:
            _LOGGER.debug("Failed to update data during setup: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from err

        self._last_home_update_attempt = dt_util.utcnow()

        # This populates a cache of maps/rooms so we have the information
        # even for maps that are inactive but is a no-op if we already have
        # the information. This will cycle through all the available maps and
        # requires the device to be idle. If the device is busy cleaning, then
        # we'll retry later in `update_map` and in the mean time we won't have
        # all map/room information.
        try:
            await self.properties_api.home.discover_home()
        except RoborockDeviceBusy:
            _LOGGER.info("Home discovery skipped while device is busy/cleaning")
        except RoborockException as err:
            _LOGGER.debug("Failed to get maps: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="map_failure",
                translation_placeholders={"error": str(err)},
            ) from err
        else:
            # Force a map refresh on first setup
            self.last_home_update = dt_util.utcnow() - IMAGE_CACHE_INTERVAL

    async def update_map(self) -> None:
        """Update the currently selected map."""
        try:
            await self.properties_api.home.discover_home()
            await self.properties_api.home.refresh()
        except RoborockException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            ) from ex
        else:
            self.last_home_update = dt_util.utcnow()

    async def _verify_api(self) -> None:
        """Verify that the api is reachable."""
        if self._device.is_connected:
            self._has_connected_locally |= self._device.is_local_connected
            if self._has_connected_locally:
                async_delete_issue(
                    self.hass, DOMAIN, f"cloud_api_used_{self.duid_slug}"
                )
            else:
                self.update_interval = V1_CLOUD_NOT_CLEANING_INTERVAL
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"cloud_api_used_{self.duid_slug}",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="cloud_api_used",
                    translation_placeholders={"device_name": self._device.name},
                    learn_more_url="https://www.home-assistant.io/integrations/roborock/#the-integration-tells-me-it-cannot-reach-my-vacuum-and-is-using-the-cloud-api-and-that-this-is-not-supported-or-i-am-having-any-networking-issues",
                )

    async def _update_device_prop(self) -> None:
        """Update device properties."""
        await _refresh_traits(
            [
                trait
                for trait in (
                    self.properties_api.status,
                    self.properties_api.consumables,
                    self.properties_api.clean_summary,
                    self.properties_api.dnd,
                    self.properties_api.dust_collection_mode,
                    self.properties_api.wash_towel_mode,
                    self.properties_api.smart_wash_params,
                    self.properties_api.sound_volume,
                    self.properties_api.child_lock,
                    self.properties_api.dust_collection_mode,
                    self.properties_api.flow_led_status,
                    self.properties_api.valley_electricity_timer,
                )
                if trait is not None
            ]
        )
        _LOGGER.debug("Updated device properties")

    async def _async_update_data(self) -> DeviceState:
        """Update data via library."""
        await self._verify_api()
        try:
            # Update device props and standard api information
            await self._update_device_prop()
        except UpdateFailed:
            if self._should_suppress_update_failure():
                _LOGGER.debug(
                    "Suppressing update failure until unavailable duration passed"
                )
                return self.data
            raise

        # If the vacuum is currently cleaning and it has been IMAGE_CACHE_INTERVAL
        # since the last map update, you can update the map.
        new_status = self.properties_api.status
        if (
            new_status.in_cleaning
            and (dt_util.utcnow() - self._last_home_update_attempt)
            > IMAGE_CACHE_INTERVAL
        ) or self.last_update_state != new_status.state_name:
            self._last_home_update_attempt = dt_util.utcnow()
            try:
                await self.update_map()
            except HomeAssistantError as err:
                _LOGGER.debug("Failed to update map: %s", err)

        if self.properties_api.status.in_cleaning:
            if self._device.is_local_connected:
                self.update_interval = V1_LOCAL_IN_CLEANING_INTERVAL
            else:
                self.update_interval = V1_CLOUD_IN_CLEANING_INTERVAL
        elif self._device.is_local_connected:
            self.update_interval = V1_LOCAL_NOT_CLEANING_INTERVAL
        else:
            self.update_interval = V1_CLOUD_NOT_CLEANING_INTERVAL
        self.last_update_state = self.properties_api.status.state_name
        self._last_update_success_time = dt_util.utcnow()
        _LOGGER.debug("Data update successful %s", self._last_update_success_time)
        return DeviceState(
            status=self.properties_api.status,
            dnd_timer=self.properties_api.dnd,
            consumable=self.properties_api.consumables,
            clean_summary=self.properties_api.clean_summary,
        )

    def _should_suppress_update_failure(self) -> bool:
        """Determine if we should suppress update failure reporting.

        We suppress reporting update failures until a minimum duration has
        passed since the last successful update. This is used to avoid reporting
        the device as unavailable for short periods, a known issue.

        The intent is to apply to routine background state refreshes and not
        other failures such as the first update or map updates.
        """
        if self._last_update_success_time is None:
            # Never had a successful update, do not suppress
            return False
        failure_duration = dt_util.utcnow() - self._last_update_success_time
        _LOGGER.debug("Update failure duration: %s", failure_duration)
        return failure_duration < MIN_UNAVAILABLE_DURATION

    async def get_routines(self) -> list[HomeDataScene]:
        """Get routines."""
        try:
            return await self.properties_api.routines.get_routines()
        except RoborockException as err:
            _LOGGER.error("Failed to get routines %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "get_scenes",
                },
            ) from err

    async def execute_routines(self, routine_id: int) -> None:
        """Execute routines."""
        try:
            await self.properties_api.routines.execute_routine(routine_id)
        except RoborockException as err:
            _LOGGER.error("Failed to execute routines %s %s", routine_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "execute_scene",
                },
            ) from err

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self._device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)

    @property
    def device(self) -> RoborockDevice:
        """Get the RoborockDevice."""
        return self._device


async def _refresh_traits(traits: list[Any]) -> None:
    """Refresh a list of traits serially.

    We refresh traits serially to avoid overloading the cloud servers or device
    with requests. If any single trait fails to refresh, we stop the whole
    update process and raise UpdateFailed.
    """
    for trait in traits:
        try:
            await trait.refresh()
        except RoborockException as ex:
            _LOGGER.debug(
                "Failed to update data (%s): %s", trait.__class__.__name__, ex
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from ex


_V = TypeVar("_V", bound=RoborockDyadDataProtocol | RoborockZeoProtocol)


class RoborockDataUpdateCoordinatorA01(DataUpdateCoordinator[dict[_V, StateType]]):
    """Class to manage fetching data from the API for A01 devices."""

    config_entry: RoborockConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=A01_UPDATE_INTERVAL,
        )
        self._device = device
        self.device_info = DeviceInfo(
            name=device.name,
            identifiers={(DOMAIN, device.duid)},
            manufacturer="Roborock",
            model=device.product.model,
            sw_version=device.device_info.fv,
        )
        self.request_protocols: list[_V] = []

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self._device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)

    @property
    def device(self) -> RoborockDevice:
        """Get the RoborockDevice."""
        return self._device


class RoborockWashingMachineUpdateCoordinator(
    RoborockDataUpdateCoordinatorA01[RoborockZeoProtocol]
):
    """Coordinator for Zeo devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
        api: ZeoApi,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, device)
        self.api = api
        self.request_protocols: list[RoborockZeoProtocol] = []
        # This currently only supports the washing machine protocols
        self.request_protocols = [
            RoborockZeoProtocol.STATE,
            RoborockZeoProtocol.COUNTDOWN,
            RoborockZeoProtocol.WASHING_LEFT,
            RoborockZeoProtocol.ERROR,
        ]

    async def _async_update_data(
        self,
    ) -> dict[RoborockZeoProtocol, StateType]:
        try:
            return await self.api.query_values(self.request_protocols)
        except RoborockException as ex:
            _LOGGER.debug("Failed to update washing machine data: %s", ex)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from ex


class RoborockWetDryVacUpdateCoordinator(
    RoborockDataUpdateCoordinatorA01[RoborockDyadDataProtocol]
):
    """Coordinator for Dyad devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
        api: DyadApi,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, device)
        self.api = api
        # This currenltly only supports the WetDryVac protocols
        self.request_protocols: list[RoborockDyadDataProtocol] = [
            RoborockDyadDataProtocol.STATUS,
            RoborockDyadDataProtocol.POWER,
            RoborockDyadDataProtocol.MESH_LEFT,
            RoborockDyadDataProtocol.BRUSH_LEFT,
            RoborockDyadDataProtocol.ERROR,
            RoborockDyadDataProtocol.TOTAL_RUN_TIME,
        ]

    async def _async_update_data(
        self,
    ) -> dict[RoborockDyadDataProtocol, StateType]:
        try:
            return await self.api.query_values(self.request_protocols)
        except RoborockException as ex:
            _LOGGER.debug("Failed to update wet dry vac data: %s", ex)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from ex


class RoborockDataUpdateCoordinatorB01(DataUpdateCoordinator[B01Props]):
    """Class to manage fetching data from the API for B01 devices."""

    config_entry: RoborockConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=A01_UPDATE_INTERVAL,
        )
        self._device = device
        self.device_info = DeviceInfo(
            name=device.name,
            identifiers={(DOMAIN, device.duid)},
            manufacturer="Roborock",
            model=device.product.model,
            sw_version=device.device_info.fv,
        )

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self._device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)

    @property
    def device(self) -> RoborockDevice:
        """Get the RoborockDevice."""
        return self._device


class RoborockB01Q7UpdateCoordinator(RoborockDataUpdateCoordinatorB01):
    """Coordinator for B01 Q7 devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
        api: Q7PropertiesApi,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, device)
        self.api = api
        self.request_protocols: list[RoborockB01Props] = [
            RoborockB01Props.STATUS,
            RoborockB01Props.MAIN_BRUSH,
            RoborockB01Props.SIDE_BRUSH,
            RoborockB01Props.DUST_BAG_USED,
            RoborockB01Props.MOP_LIFE,
            RoborockB01Props.MAIN_SENSOR,
            RoborockB01Props.CLEANING_TIME,
            RoborockB01Props.REAL_CLEAN_TIME,
            RoborockB01Props.HYPA,
        ]

    async def _async_update_data(
        self,
    ) -> B01Props:
        try:
            data = await self.api.query_values(self.request_protocols)
        except RoborockException as ex:
            _LOGGER.debug("Failed to update Q7 data: %s", ex)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from ex
        if data is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            )
        return data
