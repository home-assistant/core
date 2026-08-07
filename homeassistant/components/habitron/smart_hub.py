"""SmartHub class — the integration's thin binding to the habitron_client model."""

import logging

from habitron_client import (
    Diagnostic,
    HabitronError,
    Router,
    Sensor,
    async_build_system,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .communicate import HbtnComm
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _area_name(router: Router, area_no: int) -> str:
    """Return the bus area name for ``area_no`` (or ``House``)."""
    for area in router.areas:
        if area.nmbr == area_no:
            return area.name
    return "House"


class SmartHub:
    """Habitron SmartHub: connects and builds the device model.

    Receives the ``HbtnComm`` transport from the coordinator (which owns both);
    the SmartHub connects, builds the bus model, registers the hub/bus devices
    and refreshes the hub host-diagnostics.
    """

    manufacturer = "Habitron GmbH"

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, comm: HbtnComm
    ) -> None:
        """Init SmartHub."""
        self.hass: HomeAssistant = hass
        self.config: ConfigEntry = config
        self._name: str = config.title
        self.comm = comm

        # Temporary placeholders until async_setup runs
        self._mac = "00:00:00:00:00:00"
        self._uid_from_mac = False
        self.uid = "pending"
        self._version = "0.0.0"
        self._type = "Unknown"

        self.online: bool = True
        # Empty model until async_setup builds it from the bus.
        self.router: Router = Router()
        self.addon_slug: str = ""
        self.base_url: str = ""
        self.host = self.comm.com_ip
        self._port = self.comm.com_port

        # Hub-level (SmartHub host) diagnostics — separate from the bus model.
        self.sensors: list[Sensor] = []
        self.diags: list[Diagnostic] = []
        self.loglvl: list[Sensor] = []
        # ``Diagnostic``/``Sensor`` default to 0, which for a CPU load or a disk
        # usage is a plausible reading rather than an obvious placeholder. Until
        # the first host query has actually answered, the entities must report
        # ``unknown`` instead of publishing that zero as a measurement.
        self.host_diags_valid = False

    @property
    def smhub_version(self) -> str:
        """Version for SmartHub."""
        return self._version

    @property
    def smhub_type(self) -> str:
        """Hardware platform type of the SmartHub."""
        return self._type

    @property
    def smhub_name(self) -> str:
        """Configured name of the SmartHub (the config entry title)."""
        return self._name

    @property
    def has_mac_uid(self) -> bool:
        """Whether ``uid`` was derived from the hub's MAC (its true identity).

        False until ``async_setup`` has actually read a MAC, so nothing keys on
        the placeholder the instance starts with.
        """
        return self._uid_from_mac

    async def async_setup(self) -> None:
        """Connect, register the hub device and build the bus model."""
        await self.comm.async_setup()
        await self.comm.get_smhub_info()

        self._mac = self.comm.com_mac
        # The hub reports its MAC with either separator and in either case, and
        # the uid becomes the device identifier plus every entity's unique id
        # prefix -- so normalise it, or the same hub can end up with two sets.
        # Lower case on purpose: the custom (HACS) integration derives the same
        # uid and writes it lower case, and both share this domain's registry.
        # Upper-casing here would give every migrating installation a fresh set
        # of devices and entities, orphaning their history.
        mac_uid = self._mac.replace(":", "").replace("-", "").lower()
        self._uid_from_mac = bool(mac_uid)
        if not mac_uid:
            # A hub that reports no MAC is accepted by the config flow, which
            # then keys the entry by its host. Carrying an empty uid from here
            # would give every device the same blank identifier.
            mac_uid = self.config.unique_id or self.config.entry_id
            _LOGGER.debug("Hub reported no MAC; using %s as uid", mac_uid)
        self.uid = mac_uid
        self._version = self.comm.com_version
        self._type = self.comm.com_hwtype
        self.host = self.comm.com_ip
        self.addon_slug = self.comm.slugname

        if self.comm.is_addon:
            self.base_url = f"http://{self.host}:8123/{self.addon_slug}/ingress?index="
        else:
            self.base_url = f"http://{self.host}:7780"
        conf_url = f"{self.base_url}/hub" if self.host else None

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config.entry_id,
            configuration_url=conf_url,
            # Every interface, not just the identifying one: the hub answers
            # over whichever is up, so a discovery that saw the other one must
            # still match this device. An empty MAC is not a connection --
            # registering one would collide with every device reporting none.
            connections={
                (dr.CONNECTION_NETWORK_MAC, mac) for mac in self.comm.com_macs if mac
            },
            identifiers={(DOMAIN, self.uid)},
            manufacturer="Habitron GmbH",
            suggested_area="House",
            name=self._name,
            # ``_type`` is the hardware platform (e.g. "Raspberry Pi 5"), i.e.
            # the model. ``_name`` is the user-renameable entry title, so it is
            # not stable model metadata; there is no separate hardware revision
            # to report as ``hw_version``.
            model=self._type,
            sw_version=self._version,
        )

        if self._type.startswith("Raspberry Pi"):
            self.diags = [
                Diagnostic(name="CPU Frequency", nmbr=0, type=10),
                Diagnostic(name="CPU load", nmbr=1, type=10),
                Diagnostic(name="CPU Temperature", nmbr=2, type=10),
            ]
            self.sensors = [
                Sensor(name="Memory usage", nmbr=0, type=2, value=0),
                Sensor(name="Disk usage", nmbr=1, type=2, value=0),
            ]
            self.loglvl = [
                Sensor(name="Logging level console", nmbr=0, type=2, value=0),
                Sensor(name="Logging level file", nmbr=1, type=2, value=0),
            ]

        # ``reinit_hub(0)`` stops the hub's event server for the duration of the
        # setup; ``reinit_hub(1)`` must always restore it, even when building the
        # model or registering devices raises, or the hub would stay stopped
        # while Home Assistant retries the setup.
        await self.comm.reinit_hub(0)
        try:
            self.router = await async_build_system(self.comm.client, b_uid=self.uid)
            self.comm.set_router(self.router)
            await self._register_bus_devices()
        finally:
            await self.comm.reinit_hub(1)

    async def _register_bus_devices(self) -> None:
        """Register the router + module devices and push their registry ids."""
        dev_reg = dr.async_get(self.hass)
        router = self.router

        # ``via_device`` is deprecated (removal in 2027.8), so link through the
        # registry id of the hub device registered in ``async_setup``.
        hub_dev = dev_reg.async_get_device(identifiers={(DOMAIN, self.uid)})
        rt_dev = dev_reg.async_get_or_create(
            config_entry_id=self.config.entry_id,
            configuration_url=f"{self.base_url}/router" if self.host else None,
            identifiers={(DOMAIN, router.uid)},
            manufacturer="Habitron GmbH",
            name=router.name,
            model="Smart Router",
            sw_version=router.version,
            serial_number=router.serial,
            via_device_id=hub_dev.id if hub_dev else None,
        )
        await self.comm.send_devregid(0, rt_dev.id)

        for module in router.modules:
            raddr = module.addr - router.id
            # ``suggested_area`` seeds the area only on device creation; a
            # forced ``async_update_device(area_id=...)`` here would clobber the
            # user's manually chosen area on every reload, so it is intentionally
            # not done.
            area_name = _area_name(router, module.area)
            dev = dev_reg.async_get_or_create(
                config_entry_id=self.config.entry_id,
                configuration_url=(
                    f"{self.base_url}/module-{raddr}" if self.host else None
                ),
                identifiers={(DOMAIN, module.uid)},
                manufacturer="Habitron GmbH",
                suggested_area=area_name,
                name=module.name,
                model=module.mod_type,
                sw_version=module.sw_version,
                hw_version=module.hw_version,
                via_device_id=rt_dev.id,
            )
            await self.comm.send_devregid(raddr, dev.id)

    async def update(self) -> None:
        """Refresh the hub-level diagnostics from the SmartHub info query.

        These are non-essential host sensors (CPU/memory/disk/log levels),
        decoupled from the bus status: a transient bad/dropped response must not
        fail the coordinator tick (which would mark *every* entity unavailable)
        or abort entry setup. Swallow the library's protocol/connection errors
        and keep the last values; the next tick refreshes them. Genuine
        connectivity loss still surfaces through the bus refresh that follows.
        """
        if not self.diags:
            # Only Raspberry-Pi-based hubs expose host diagnostics; on any other
            # platform there is nothing to fill, so skip the query entirely
            # instead of fetching and discarding it every tick.
            return
        try:
            host = await self.comm.get_host_diagnostics()
        except (HabitronError, OSError, TimeoutError) as err:
            # The coordinator calls this outside its guarded bus refresh, so a
            # socket error, a timeout or a payload the library cannot read
            # (``HabitronProtocolError``) would otherwise fail the whole tick
            # and mark every entity unavailable. ``host_diags_valid`` stays
            # False, so the next good read still publishes every member.
            _LOGGER.debug("SmartHub diagnostics update skipped: %s", err)
            return
        readings: tuple[tuple[Diagnostic | Sensor, float], ...] = (
            (self.diags[0], host.cpu_frequency),
            (self.diags[1], host.cpu_load),
            (self.diags[2], host.cpu_temperature),
            (self.sensors[0], host.memory_usage),
            (self.sensors[1], host.disk_usage),
            (self.loglvl[0], host.log_level_console),
            (self.loglvl[1], host.log_level_file),
        )
        was_valid = self.host_diags_valid
        self.host_diags_valid = True
        unchanged = [
            member for member, value in readings if not self._set(member, value)
        ]
        if not was_valid:
            # First successful read after setup-time failures: ``_set`` notifies
            # what it changed, so only the members that happen to match their
            # placeholder (a log level of 0, an unchanged CPU frequency) are left
            # -- they would stay ``unknown`` until some *other* value moves.
            for member in unchanged:
                member.notify()

    @staticmethod
    def _set(member: Diagnostic | Sensor, value: float) -> bool:
        """Set a hub member's value, notifying listeners on a change.

        Returns whether the value changed, so a caller can tell which members
        still need a notification.
        """
        if member.value == value:
            return False
        member.value = value
        member.notify()
        return True

    async def async_close(self) -> None:
        """Close the hub's bus client when the entry is unloaded."""
        await self.comm.async_close()
