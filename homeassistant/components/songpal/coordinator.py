"""Client implementation for Songpal-enable (Sony) media devices."""
from __future__ import annotations

import asyncio
import dataclasses
from datetime import timedelta
import logging

import async_timeout
from songpal import Device, SongpalException
from songpal.containers import (
    Input,
    InterfaceInfo,
    PlayInfo,
    Power,
    Setting,
    SettingsEntry,
    SoftwareUpdateInfo,
    Sysinfo,
    Volume,
)
from songpal.notification import (
    ChangeNotification,
    ConnectChange,
    ContentChange,
    PowerChange,
    SettingChange,
    SoftwareUpdateChange,
    VolumeChange,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, TITLE_TEXTID_VERSION

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class SongpalState:
    """Single container of state for the SongpalCoordinator."""

    system_information: Sysinfo
    interface_info: InterfaceInfo
    power: Power
    settings: dict[str, Setting]
    sw_update_info: SoftwareUpdateInfo
    volume: Volume
    inputs: list[Input]
    playing_content: PlayInfo

    @property
    def unique_id(self) -> str:
        """Return an Unique ID for the device.

        If present, use the serialNumber. If not, use the MAC address,
        either wired or wireless.
        """
        return (
            self.system_information.serialNumber
            or self.system_information.macAddr
            or self.system_information.wirelessMacAddr
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the common device information of the Songpal device."""
        connections = set()

        if self.system_information.macAddr:
            connections.add((CONNECTION_NETWORK_MAC, self.system_information.macAddr))
        if self.system_information.wirelessMacAddr:
            connections.add(
                (CONNECTION_NETWORK_MAC, self.system_information.wirelessMacAddr)
            )

        identifiers = set()
        if self.system_information.serialNumber:
            identifiers = {(DOMAIN, self.system_information.serialNumber)}

        return DeviceInfo(
            identifiers=identifiers,
            connections=connections,
            manufacturer="Sony Corporation",
            default_name=self.interface_info.modelName,
            sw_version=self.system_information.version,
            model=self.interface_info.modelName,
        )


class SongpalCoordinator(DataUpdateCoordinator[SongpalState]):
    """Wrapper for the Songpal Device object to be shared among entities."""

    _listener_task: asyncio.Task | None = None
    settings_definitions: list[SettingsEntry] = []

    def __init__(self, name: str, hass: HomeAssistant, device: Device) -> None:
        """Create but don't activate the client wrapper."""
        self.device = device
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_method=self.async_update_data,
            # Interval is only used if there was no data pushed by the API in the same time,
            # or if we lost connection.
            update_interval=timedelta(seconds=45),
        )

    async def _handle_notification(self, change: ChangeNotification) -> None:
        _LOGGER.debug("[%s] received notification: %r", self.name, change)
        new_data = self.data
        if isinstance(change, PowerChange):
            new_data.power = change
        elif isinstance(change, SettingChange):
            new_setting = new_data.settings.get(change.titleTextID, None)
            if new_setting is None:
                _LOGGER.warning(
                    "[%s] Received change for unknown setting %s",
                    self.name,
                    change.titleTextID,
                )

            new_setting.currentValue = change.currentValue
            if change.isAvailable is not None:
                new_setting.isAvailable = change.isAvailable

            if new_setting.type != change.type:
                _LOGGER.warning(
                    "[%s] Setting %s change type from %s to %s, will likely break",
                    self.name,
                    change.target,
                    new_setting.type,
                    change.type,
                )

            new_data.settings[change.titleTextID] = new_setting
        elif isinstance(change, SoftwareUpdateChange):
            new_data.sw_update_info = change
        elif isinstance(change, VolumeChange):
            # The change volume notification does not repeat the min/max/step settings, so only override
            # the new parameters.

            new_data.volume.volume = change.volume
            new_data.volume.output = change.output
            # This is annoying: Volume keeps the mute attribute as string and converts it when requesting
            # isMuted, while VolumeChange converts it on creation, so we need to re-synthesize the string.
            new_data.volume.mute = "on" if change.mute else "off"
        elif isinstance(change, ContentChange):
            new_data.playing_content = change
        elif isinstance(change, ConnectChange):
            # This is only sent when one of the notifications listeners failed, and implies the connection
            # to the device dropped.
            _LOGGER.warning("[%s] Disconnected: %r", self.name, change.exception)
            await self.async_request_refresh()
        else:
            _LOGGER.debug("[%s] unknown notification", self.name)
            return

        self.async_set_updated_data(new_data)

    async def async_request_refresh(self) -> None:
        """Stop the listeners, and request a refresh."""
        _LOGGER.debug("[%s] Stopping listeners for refresh", self.name)
        await self.device.stop_listen_notifications()

        return await super().async_request_refresh()

    async def async_update_data(self) -> SongpalState:
        """Fetch all the information from the Songpal device."""
        try:
            # set timeout to avoid blocking the setup process
            async with async_timeout.timeout(10):
                await self.device.get_supported_methods()
        except (SongpalException, asyncio.TimeoutError) as ex:
            _LOGGER.warning("[%s] Unable to connect", self.device.endpoint)
            _LOGGER.debug("Unable to get methods from songpal", exc_info=True)
            if isinstance(ex, asyncio.TimeoutError):
                raise ex
            raise UpdateFailed(str(ex)) from ex

        if not self._listener_task or self._listener_task.done():
            self._listener_task = self.hass.loop.create_task(
                self.device.listen_notifications(self._handle_notification)
            )

        # We only need to fetch the settings definition once, as the only thing that do change are the
        # current values and their availability.
        if not self.settings_definitions:
            settings_tree = await self.device.get_settings()
            _LOGGER.debug("[%s] Retrieved settings tree: %r", self.name, settings_tree)

            def _append_settings(entry: SettingsEntry) -> None:
                if entry.is_directory:
                    # Ignore the initial settings in particular, as they should not be changed!
                    if entry.usage == "initialSetting":
                        return

                    for sub_entry in entry.settings or []:
                        _append_settings(sub_entry)
                else:
                    self.settings_definitions.append(entry)

            for entry in settings_tree:
                # Ignore nullTarget entries or it'll fail to fetch their state.
                if entry.type == "nullTarget":
                    continue
                if entry.titleTextID == TITLE_TEXTID_VERSION:
                    continue
                _append_settings(entry)

        all_settings = {}
        settings_fetchers = [
            setting.get_value(self.device) for setting in self.settings_definitions
        ]
        settings_fetched = asyncio.gather(*settings_fetchers, return_exceptions=True)
        for result in await settings_fetched:
            if isinstance(result, Exception):
                _LOGGER.warning(
                    "[%s] Exception while fetching settings: %s", self.name, result
                )
                continue

            # The titleTextID field seems to be more stable than the target!
            if result.titleTextID in all_settings:
                _LOGGER.warning(
                    "[%s] Duplicate setting retrieved for %s",
                    self.name,
                    result.titleTextID,
                )

            # Some boolean settings are reported as enum for some reason, and sometimes
            # even change between the two types depending on whether the device is on or off
            # as is the case on the HT-A7000. Set the correct type here to avoid repeating
            # ourselves in all the places.

            if result.type == "enumTarget":
                possible_values = {
                    candidate.value
                    for candidate in result.candidate
                    if candidate.isAvailable
                }
                if possible_values == {"on", "off"}:
                    result.type = "booleanTarget"
                    # Also look through the settings definition to update it!
                    for setting in self.settings_definitions:
                        if setting.titleTextID == result.titleTextID:
                            setting.type = "booleanTarget"

            all_settings[result.titleTextID] = result

        all_volumes = await self.device.get_volume_information()
        if len(all_volumes) > 1:
            raise ConfigEntryNotReady(
                f"Multiple volume controls found (unsupported): {all_volumes!r}"
            )

        play_info = await self.device.get_play_info()

        return SongpalState(
            system_information=await self.device.get_system_info(),
            interface_info=await self.device.get_interface_information(),
            power=await self.device.get_power(),
            settings=all_settings,
            sw_update_info=await self.device.get_update_info(),
            volume=all_volumes[0],
            inputs=await self.device.get_inputs(),
            playing_content=play_info,
        )
