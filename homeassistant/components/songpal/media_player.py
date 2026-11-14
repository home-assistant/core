"""Support for Songpal-enabled (Sony) media devices."""

import asyncio
from collections import OrderedDict
from collections.abc import Iterable
from datetime import timedelta
import logging
from typing import Any, override
from urllib.parse import urlparse

from async_upnp_client.exceptions import UpnpError
import attr
from songpal import (
    ConnectChange,
    ContentChange,
    Device,
    PowerChange,
    SettingChange,
    SongpalException,
    VolumeChange,
)
from songpal.containers import Setting
from songpal.group import GroupControl, GroupState

from homeassistant.components import ssdp
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import (
    HomeAssistantError,
    PlatformNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.network import is_ip_address

from .const import CONF_ENDPOINT, DOMAIN, ERROR_REQUEST_RETRY, UPNP_ST_SCALARWEBAPI

_LOGGER = logging.getLogger(__name__)

INITIAL_RETRY_DELAY = 10

# The group service is UPnP based and does not push notifications, so poll it.
GROUP_SCAN_INTERVAL = timedelta(seconds=30)
# Devices take about a second to report a group change.
GROUP_SETTLE_DELAY = 2
GROUP_MODE_GROUP = "GROUP"
GROUP_MODE_IDLE = "IDLE"
# Devices reject longer group names when creating and truncate them when renaming
GROUP_NAME_MAX_BYTES = 64
# Larger groups are named after the leader and the number of other members
GROUP_NAME_MAX_LISTED = 3
# Codec Sony's app uses for groups, as reported by the leader of a group created
# in the app. Groups created with python-songpal's CodecType 0x40 and
# CodecBitrate 3 had dropouts when resuming playback after a pause.
GROUP_CODEC_TYPE = 48
GROUP_CODEC_BITRATE = 0

GROUP_ENTITIES: HassKey[dict[str, SongpalEntity]] = HassKey(f"{DOMAIN}_group_entities")


def _member_udns(state: GroupState) -> list[str]:
    """Return the UDNs of the group members listed in a leader's state."""
    return [udn.strip() for udn in state.SlaveList.split(",") if udn.strip()]


def _with_group(
    state: GroupState,
    mode: str = GROUP_MODE_IDLE,
    leader_udn: str | None = "",
    member_udns: Iterable[str] = (),
) -> GroupState:
    """Return the state with its group replaced, ungrouped by default."""
    return attr.evolve(
        state,
        GroupMode=mode,
        MasterUUID=leader_udn or "",
        SlaveList=",".join(member_udns),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up songpal media player."""
    name = config_entry.data[CONF_NAME]
    endpoint = config_entry.data[CONF_ENDPOINT]

    device = Device(endpoint)
    try:
        async with asyncio.timeout(
            10
        ):  # set timeout to avoid blocking the setup process
            await device.get_supported_methods()
    except (SongpalException, TimeoutError) as ex:
        _LOGGER.warning("[%s(%s)] Unable to connect", name, endpoint)
        _LOGGER.debug("Unable to get methods from songpal: %s", ex)
        raise PlatformNotReady from ex

    songpal_entity = SongpalEntity(name, device)
    async_add_entities([songpal_entity], True)


class SongpalEntity(MediaPlayerEntity):
    """Class representing a Songpal device."""

    _attr_should_poll = False
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, name, device):
        """Init."""
        self._name = name
        self._dev = device
        self._sysinfo = None
        self._model = None

        self._state = False
        self._attr_available = False
        self._initialized = False

        self._volume_control = None
        self._volume_min = 0
        self._volume_max = 1
        self._volume = 0
        self._attr_is_volume_muted = False

        self._active_source = None
        self._sources = {}
        self._active_sound_mode = None
        self._sound_modes = {}

        self._group_control: GroupControl | None = None
        self._group_state: GroupState | None = None
        self._udn: str | None = None
        self._friendly_name: str = name
        # Polling is paused until a group change settled, see GROUP_SETTLE_DELAY
        self._group_settling_until = 0.0
        self._group_control_outdated = False
        self._removed = False
        self._cancel_group_refresh: CALLBACK_TYPE | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        entry = await self.async_activate_websocket()
        # Connecting to the group service can take a while, don't block the setup
        group_setup = entry.async_create_background_task(
            self.hass, self._async_update_group_state(), "songpal-group-setup"
        )

        @callback
        def _cancel_group_setup() -> None:
            group_setup.cancel()

        self.async_on_remove(_cancel_group_setup)
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_poll_group_state, GROUP_SCAN_INTERVAL
            )
        )
        self.async_on_remove(self._async_cancel_group_refresh)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._removed = True
        await self._dev.stop_listen_notifications()

    async def _get_sound_modes_info(self):
        """Get available sound modes and the active one."""
        for settings in await self._dev.get_sound_settings():
            if settings.target == "soundField":
                break
        else:
            return None, {}

        if isinstance(settings, Setting):
            settings = [settings]

        sound_modes = {}
        active_sound_mode = None
        for setting in settings:
            cur = setting.currentValue
            for opt in setting.candidate:
                if not opt.isAvailable:
                    continue
                if opt.value == cur:
                    active_sound_mode = opt.value
                sound_modes[opt.value] = opt

        _LOGGER.debug("Got sound modes: %s", sound_modes)
        _LOGGER.debug("Active sound mode: %s", active_sound_mode)

        return active_sound_mode, sound_modes

    async def async_activate_websocket(self) -> ConfigEntry:
        """Activate websocket for listening if wanted."""
        _LOGGER.debug("Activating websocket connection")

        # Narrowed once here rather than at each call site: the entity is only
        # ever added from async_setup_entry, so the platform always has an entry.
        entry = self.platform.config_entry
        assert entry is not None

        async def _volume_changed(volume: VolumeChange):
            _LOGGER.debug("Volume changed: %s", volume)
            self._volume = volume.volume
            self._attr_is_volume_muted = volume.mute
            self.async_write_ha_state()

        async def _source_changed(content: ContentChange):
            _LOGGER.debug("Source changed: %s", content)
            if content.is_input:
                self._active_source = self._sources[content.uri]
                _LOGGER.debug("New active source: %s", self._active_source)
                self.async_write_ha_state()
            else:
                _LOGGER.debug("Got non-handled content change: %s", content)

        async def _setting_changed(setting: SettingChange):
            _LOGGER.debug("Setting changed: %s", setting)

            if setting.target == "soundField":
                self._active_sound_mode = setting.currentValue
                _LOGGER.debug("New active sound mode: %s", self._active_sound_mode)
                self.async_write_ha_state()
            else:
                _LOGGER.debug("Got non-handled setting change: %s", setting)

        async def _power_changed(power: PowerChange):
            _LOGGER.debug("Power changed: %s", power)
            self._state = power.status
            self.async_write_ha_state()

        async def _try_reconnect(connect: ConnectChange):
            _LOGGER.warning(
                "[%s(%s)] Got disconnected, trying to reconnect",
                self.name,
                self._dev.endpoint,
            )
            _LOGGER.debug("Disconnected: %s", connect.exception)
            self._attr_available = False
            self.async_write_ha_state()

            # Try to reconnect forever, a successful reconnect will initialize
            # the websocket connection again.
            delay = INITIAL_RETRY_DELAY
            while not self._attr_available and not self._removed:
                _LOGGER.debug("Trying to reconnect in %s seconds", delay)
                await asyncio.sleep(delay)

                try:
                    await self._dev.get_supported_methods()
                except SongpalException as ex:
                    _LOGGER.debug("Failed to reconnect: %s", ex)
                    delay = min(2 * delay, 300)
                else:
                    # We need to inform HA about the state in case we are coming
                    # back from a disconnected state.
                    await self.async_update_ha_state(force_refresh=True)

            if self._removed:
                return
            entry.async_create_background_task(
                self.hass,
                self._dev.listen_notifications(),
                "songpal-listen-notifications",
            )
            _LOGGER.warning(
                "[%s(%s)] Connection reestablished", self.name, self._dev.endpoint
            )
            # The UPnP location may have changed while the device was gone,
            # keep looking it up with the polls until that succeeds
            self._group_control_outdated = True
            await self._async_setup_group_control()

        self._dev.on_notification(VolumeChange, _volume_changed)
        self._dev.on_notification(ContentChange, _source_changed)
        self._dev.on_notification(PowerChange, _power_changed)
        self._dev.on_notification(SettingChange, _setting_changed)
        self._dev.on_notification(ConnectChange, _try_reconnect)

        async def handle_stop(event):
            await self._dev.stop_listen_notifications()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_stop)
        )

        entry.async_create_background_task(
            self.hass, self._dev.listen_notifications(), "songpal-listen-notifications"
        )
        return entry

    @property
    @override
    def unique_id(self):
        """Return a unique ID."""
        return self._sysinfo.macAddr or self._sysinfo.wirelessMacAddr

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        connections = set()
        if self._sysinfo.macAddr:
            connections.add((dr.CONNECTION_NETWORK_MAC, self._sysinfo.macAddr))
        if self._sysinfo.wirelessMacAddr:
            connections.add((dr.CONNECTION_NETWORK_MAC, self._sysinfo.wirelessMacAddr))
        return DeviceInfo(
            connections=connections,
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Sony Corporation",
            model=self._model,
            name=self._name,
            sw_version=self._sysinfo.version,
        )

    async def async_set_sound_setting(self, name, value):
        """Change a setting on the device."""
        _LOGGER.debug("Calling set_sound_setting with %s: %s", name, value)
        await self._dev.set_sound_settings(name, value)

    async def async_update(self) -> None:
        """Fetch updates from the device."""
        try:
            if self._sysinfo is None:
                self._sysinfo = await self._dev.get_system_info()

            if self._model is None:
                interface_info = await self._dev.get_interface_information()
                self._model = interface_info.modelName

            volumes = await self._dev.get_volume_information()
            if not volumes:
                _LOGGER.error("Got no volume controls, bailing out")
                self._attr_available = False
                return

            if len(volumes) > 1:
                _LOGGER.debug("Got %s volume controls, using the first one", volumes)

            volume = volumes[0]
            _LOGGER.debug("Current volume: %s", volume)

            self._volume_max = volume.maxVolume
            self._volume_min = volume.minVolume
            self._volume = volume.volume
            self._volume_control = volume
            if self._volume_max:
                self._attr_volume_step = 1 / self._volume_max
            self._attr_is_volume_muted = self._volume_control.is_muted

            status = await self._dev.get_power()
            self._state = status.status
            _LOGGER.debug("Got state: %s", status)

            inputs = await self._dev.get_inputs()
            _LOGGER.debug("Got ins: %s", inputs)

            self._sources = OrderedDict()
            for input_ in inputs:
                self._sources[input_.uri] = input_
                if input_.active:
                    self._active_source = input_

            _LOGGER.debug("Active source: %s", self._active_source)

            (
                self._active_sound_mode,
                self._sound_modes,
            ) = await self._get_sound_modes_info()

            self._attr_available = True

        except SongpalException as ex:
            _LOGGER.error("Unable to update: %s", ex)
            self._attr_available = False

    @override
    async def async_select_source(self, source: str) -> None:
        """Select source."""
        for out in self._sources.values():
            if out.title == source:
                await out.activate()
                return

        _LOGGER.error("Unable to find output: %s", source)

    @property
    @override
    def source_list(self):
        """Return list of available sources."""
        return [src.title for src in self._sources.values()]

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        for mode in self._sound_modes.values():
            if mode.title == sound_mode:
                await self._dev.set_sound_settings("soundField", mode.value)
                return

        _LOGGER.error("Unable to find sound mode: %s", sound_mode)

    @property
    @override
    def sound_mode_list(self) -> list[str] | None:
        """Return list of available sound modes.

        When active mode is None it means that sound mode is
        unavailable on the sound bar.
        Can be due to incompatible sound bar or the sound bar is in a mode that does not
        support sound mode changes.
        """
        if not self._active_sound_mode:
            return None
        return [sound_mode.title for sound_mode in self._sound_modes.values()]

    @property
    @override
    def state(self) -> MediaPlayerState:
        """Return current state."""
        if self._state:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    @override
    def source(self):
        """Return currently active source."""
        # Avoid a KeyError when _active_source is not (yet) populated
        return getattr(self._active_source, "title", None)

    @property
    @override
    def sound_mode(self) -> str | None:
        """Return currently active sound_mode."""
        active_sound_mode = self._sound_modes.get(self._active_sound_mode)
        return active_sound_mode.title if active_sound_mode else None

    @property
    @override
    def volume_level(self):
        """Return volume level."""
        return self._volume / self._volume_max

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        volume = round(volume * self._volume_max)
        _LOGGER.debug("Setting volume to %s", volume)
        return await self._volume_control.set_volume(volume)

    @override
    async def async_turn_on(self) -> None:
        """Turn the device on."""
        try:
            await self._dev.set_power(True)
        except SongpalException as ex:
            if ex.code == ERROR_REQUEST_RETRY:
                _LOGGER.debug(
                    "Swallowing %s, the device might be already in the wanted state", ex
                )
                return
            raise

    @override
    async def async_turn_off(self) -> None:
        """Turn the device off."""
        try:
            await self._dev.set_power(False)
        except SongpalException as ex:
            if ex.code == ERROR_REQUEST_RETRY:
                _LOGGER.debug(
                    "Swallowing %s, the device might be already in the wanted state", ex
                )
                return
            raise

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the device."""
        _LOGGER.debug("Set mute: %s", mute)
        return await self._volume_control.set_mute(mute)

    @property
    def udn(self) -> str | None:
        """Return the UPnP UDN identifying the device in groups."""
        return self._udn

    @property
    def _is_group_leader(self) -> bool:
        """Return whether the device leads a group."""
        state = self._group_state
        return (
            state is not None
            and state.GroupMode == GROUP_MODE_GROUP
            and not state.MasterUUID
        )

    def _get_group_control(self) -> GroupControl:
        """Return the group control of a device that supports grouping."""
        assert self._group_control is not None
        return self._group_control

    async def _async_find_ssdp_info(self) -> SsdpServiceInfo | None:
        """Return the SSDP discovery info of the device."""
        infos = [
            info
            for info in await ssdp.async_get_discovery_info_by_st(
                self.hass, UPNP_ST_SCALARWEBAPI
            )
            if info.ssdp_location
        ]
        endpoint = self._dev.endpoint
        for info in infos:
            device_info = info.upnp.get("X_ScalarWebAPI_DeviceInfo") or {}
            if device_info.get("X_ScalarWebAPI_BaseURL") == endpoint:
                return info

        # Endpoints entered manually may use a host name instead of the address
        if host := urlparse(endpoint).hostname:
            addresses = {host}
            if not is_ip_address(host):
                try:
                    addresses.update(
                        address[4][0]
                        for address in await self.hass.loop.getaddrinfo(host, None)
                    )
                except OSError as ex:
                    _LOGGER.debug("Unable to resolve %s: %s", host, ex)
            for info in infos:
                if urlparse(info.ssdp_location).hostname in addresses:
                    return info

        _LOGGER.debug("No SSDP discovery info found for %s", endpoint)
        return None

    async def _async_setup_group_control(self) -> None:
        """Connect to the UPnP group service of the device, if it was discovered."""
        if "ssdp" not in self.hass.config.components:
            return
        if (info := await self._async_find_ssdp_info()) is None:
            return
        assert info.ssdp_location is not None

        group_control = GroupControl(info.ssdp_location)
        try:
            async with asyncio.timeout(10):
                if not await group_control.connect():
                    return
        except (UpnpError, KeyError, TimeoutError) as ex:
            _LOGGER.debug("Unable to connect to the group service: %s", ex)
            return
        if self._removed:
            return

        udn = info.upnp[ATTR_UPNP_UDN]
        self._group_control = group_control
        self._group_control_outdated = False
        self._udn = udn
        self._friendly_name = info.upnp.get(ATTR_UPNP_FRIENDLY_NAME) or self._name
        self._attr_supported_features |= MediaPlayerEntityFeature.GROUPING

        entities = self.hass.data.setdefault(GROUP_ENTITIES, {})
        if entities.get(udn) is not self:
            entities[udn] = self

            @callback
            def _unregister() -> None:
                if entities.get(udn) is self:
                    del entities[udn]
                    # Their group members may have included this device
                    for entity in entities.values():
                        entity.async_write_ha_state()

            self.async_on_remove(_unregister)
        self.async_write_ha_state()

    @property
    def _is_group_settling(self) -> bool:
        """Return whether a group change of the device is still settling."""
        return self.hass.loop.time() < self._group_settling_until

    async def _async_poll_group_state(self, _now: Any) -> None:
        """Poll the group state, unless a group change is still settling."""
        if not self._is_group_settling:
            await self._async_update_group_state()

    async def _async_update_group_state(self) -> None:
        """Fetch the group state and update the entities whose groups changed."""
        if self._group_control is None or self._group_control_outdated:
            await self._async_setup_group_control()
            if self._group_control is None:
                return

        try:
            group_state = await self._group_control.state()
        except UpnpError as ex:
            # The group service sometimes stops responding for about a minute,
            # keep the last known state instead of showing the device ungrouped
            _LOGGER.debug("Unable to get the group state: %s", ex)
            return

        def _group_key(state: GroupState | None) -> tuple[str, str, str] | None:
            if state is None:
                return None
            return (state.GroupMode, state.MasterUUID, state.SlaveList)

        changed = _group_key(group_state) != _group_key(self._group_state)
        self._group_state = group_state
        if changed:
            # The group members of the other devices may depend on this device
            for entity in self.hass.data[GROUP_ENTITIES].values():
                entity.async_write_ha_state()

    async def _async_update_all_group_states(self, _now: Any = None) -> None:
        """Fetch the group state of all devices."""
        self._cancel_group_refresh = None
        entities = list(self.hass.data[GROUP_ENTITIES].values())
        for entity in entities:
            entity._group_settling_until = 0  # noqa: SLF001
        await asyncio.gather(
            *(entity._async_update_group_state() for entity in entities)  # noqa: SLF001
        )

    @callback
    def _async_set_expected_group_states(
        self, expected: dict[SongpalEntity, GroupState]
    ) -> None:
        """Show the expected group states and verify them once the devices settled."""
        # Ends by itself in case the refresh below is cancelled with this entity
        settling_until = self.hass.loop.time() + GROUP_SETTLE_DELAY
        for entity, state in expected.items():
            entity._group_state = state  # noqa: SLF001
            entity._group_settling_until = settling_until  # noqa: SLF001
        for entity in self.hass.data[GROUP_ENTITIES].values():
            entity.async_write_ha_state()

        self._async_cancel_group_refresh()
        self._cancel_group_refresh = async_call_later(
            self.hass, GROUP_SETTLE_DELAY, self._async_update_all_group_states
        )

    @callback
    def _async_cancel_group_refresh(self) -> None:
        """Cancel a pending group refresh."""
        if self._cancel_group_refresh is not None:
            self._cancel_group_refresh()
            self._cancel_group_refresh = None

    def _leader_group_members(self) -> list[str]:
        """Return the members of the group led by this device, leader first."""
        assert self._group_state is not None
        entities = self.hass.data[GROUP_ENTITIES]
        members = [self.entity_id]
        members.extend(
            member.entity_id
            for udn in _member_udns(self._group_state)
            if (member := entities.get(udn)) is not None
        )
        return members

    @property
    @override
    def group_members(self) -> list[str] | None:
        """Return the entities in the group of this device, leader first."""
        if self._udn is None:
            return None
        if self._is_group_leader:
            return self._leader_group_members()

        state = self._group_state
        if state is not None and state.GroupMode == GROUP_MODE_GROUP:
            leader = self.hass.data[GROUP_ENTITIES].get(state.MasterUUID)
            if leader is not None and leader._is_group_leader:  # noqa: SLF001
                return leader._leader_group_members()  # noqa: SLF001
        return [self.entity_id]

    async def _async_remove_member(self, member: SongpalEntity) -> None:
        """Remove a member from the group led by this device."""
        await self._get_group_control().remove(member.udn)

        expected: dict[SongpalEntity, GroupState] = {}
        if member._group_state is not None:
            expected[member] = _with_group(member._group_state)
        if self._group_state is not None:
            # The leader dissolves the group when its last member leaves
            remaining = [
                udn for udn in _member_udns(self._group_state) if udn != member.udn
            ]
            if remaining:
                await self._async_rename_group(remaining)
            expected[self] = _with_group(
                self._group_state,
                GROUP_MODE_GROUP if remaining else GROUP_MODE_IDLE,
                member_udns=remaining,
            )
        self._async_set_expected_group_states(expected)

    def _group_name(self, member_udns: Iterable[str]) -> str:
        """Return a group name listing the leader and its members."""
        member_udns = list(member_udns)
        entities = self.hass.data[GROUP_ENTITIES]
        names = [self._friendly_name]
        names.extend(
            member._friendly_name  # noqa: SLF001
            for udn in member_udns
            if (member := entities.get(udn)) is not None
        )
        name = " + ".join(names)
        if (
            len(member_udns) + 1 > GROUP_NAME_MAX_LISTED
            or len(name.encode()) > GROUP_NAME_MAX_BYTES
        ):
            name = f"{self._friendly_name} + {len(member_udns)}"
        return name.encode()[:GROUP_NAME_MAX_BYTES].decode(errors="ignore")

    async def _async_rename_group(self, member_udns: list[str]) -> None:
        """Rename the group led by this device after its members changed."""
        try:
            await self._get_group_control().set_group_name(
                self._group_name(member_udns)
            )
        except UpnpError as ex:
            # The members changed already, a stale name is no reason to fail
            _LOGGER.warning("Unable to rename the group of %s: %s", self.entity_id, ex)

    @override
    async def async_join_players(self, group_members: list[str]) -> None:
        """Join group_members as a player group with this device as leader."""
        group_control = self._get_group_control()
        entities = {
            entity.entity_id: entity
            for entity in self.hass.data[GROUP_ENTITIES].values()
        }
        members: list[SongpalEntity] = []
        udns: list[str] = []
        for entity_id in group_members:
            if entity_id == self.entity_id:
                continue
            if (member := entities.get(entity_id)) is None or member.udn is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="group_member_not_supported",
                    translation_placeholders={"entity_id": entity_id},
                )
            members.append(member)
            udns.append(member.udn)
        if not udns:
            return

        try:
            state = await group_control.state()
            if state.MasterUUID:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="group_member_of_other_group",
                    translation_placeholders={"entity_id": self.entity_id},
                )
            if state.GroupMode == GROUP_MODE_GROUP:
                member_udns = _member_udns(state)
                if new_udns := [udn for udn in udns if udn not in member_udns]:
                    await group_control.add(",".join(new_udns))
                    member_udns += new_udns
                    await self._async_rename_group(member_udns)
            else:
                await group_control.call(
                    "X_Start",
                    GroupMode=GROUP_MODE_GROUP,
                    GroupName=self._group_name(udns),
                    SlaveList=",".join(udns),
                    CodecType=GROUP_CODEC_TYPE,
                    CodecBitrate=GROUP_CODEC_BITRATE,
                )
                member_udns = udns
        except UpnpError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="grouping_failed",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "error": str(ex),
                },
            ) from ex

        expected = {self: _with_group(state, GROUP_MODE_GROUP, member_udns=member_udns)}
        for member in members:
            if member._group_state is not None:  # noqa: SLF001
                expected[member] = _with_group(
                    member._group_state,  # noqa: SLF001
                    GROUP_MODE_GROUP,
                    leader_udn=self._udn,
                )
        self._async_set_expected_group_states(expected)

    @override
    async def async_unjoin_player(self) -> None:
        """Remove this device from its group, dissolving it if it is the leader."""
        group_control = self._get_group_control()
        entities = self.hass.data[GROUP_ENTITIES]
        try:
            state = await group_control.state()
            if state.MasterUUID and (leader := entities.get(state.MasterUUID)):
                # Leaving from the member side keeps it listed on the leader
                await leader._async_remove_member(self)  # noqa: SLF001
                return
            if state.MasterUUID:
                await group_control.call("X_Exit", SlaveSessionID=state.SessionID)
            elif state.GroupMode == GROUP_MODE_GROUP:
                await group_control.abort()
            else:
                return
        except UpnpError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="grouping_failed",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "error": str(ex),
                },
            ) from ex

        expected = {self: _with_group(state)}
        if not state.MasterUUID:
            for udn in _member_udns(state):
                member = entities.get(udn)
                if member is not None and member._group_state is not None:  # noqa: SLF001
                    expected[member] = _with_group(member._group_state)  # noqa: SLF001
        self._async_set_expected_group_states(expected)
