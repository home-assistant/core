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

    async def async_setup(self) -> None:
        """Connect, register the hub device and build the bus model."""
        # 1. Open the client connection and fetch hub info (mac/version/host).
        await self.comm.async_setup()
        await self.comm.get_smhub_info()

        self._mac = self.comm.com_mac
        self.uid = self._mac.replace(":", "")
        self._version = self.comm.com_version
        self._type = self.comm.com_hwtype
        self.host = self.comm.com_ip
        self.addon_slug = self.comm.slugname

        if self.comm.is_addon:
            self.base_url = f"http://{self.host}:8123/{self.addon_slug}/ingress?index="
        else:
            self.base_url = f"http://{self.host}:7780"
        conf_url = f"{self.base_url}/hub" if self.host else None

        # 2. Register the hub device.
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config.entry_id,
            configuration_url=conf_url,
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac)},
            identifiers={(DOMAIN, self.uid)},
            manufacturer="Habitron GmbH",
            suggested_area="House",
            name=self._name,
            model=self._name,
            sw_version=self._version,
            hw_version=self._type,
        )

        # 3. Hub diagnostics (depends on the platform type).
        if self._type[:12] == "Raspberry Pi":
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

        # 4. Build the bus model (router + modules), register their devices.
        await self.comm.reinit_hub(0)
        await self.comm.send_network_info(self.config.data["websock_token"])
        self.router = await async_build_system(self.comm.client, b_uid=self.uid)
        self.comm.set_router(self.router)
        await self._register_bus_devices()
        await self.comm.reinit_hub(1)

        # 5. First hub-diagnostics update.
        await self.update()

    async def _register_bus_devices(self) -> None:
        """Register the router + module devices and push their registry ids."""
        dev_reg = dr.async_get(self.hass)
        router = self.router

        dev_reg.async_get_or_create(
            config_entry_id=self.config.entry_id,
            configuration_url=f"{self.base_url}/router" if self.host else None,
            identifiers={(DOMAIN, router.uid)},
            manufacturer="Habitron GmbH",
            name=router.name,
            model="Smart Router",
            sw_version=router.version,
            hw_version=router.serial,
            via_device=(DOMAIN, self.uid),
        )
        rt_dev = dev_reg.async_get_device(identifiers={(DOMAIN, router.uid)})
        if rt_dev is not None:
            await self.comm.send_devregid(0, rt_dev.id)

        for module in router.modules:
            raddr = module.addr - router.id
            # ``suggested_area`` seeds the area only on device creation; a
            # forced ``async_update_device(area_id=...)`` here would clobber the
            # user's manually chosen area on every reload, so it is intentionally
            # not done.
            area_name = _area_name(router, module.area)
            dev_reg.async_get_or_create(
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
                via_device=(DOMAIN, router.uid),
            )
            dev = dev_reg.async_get_device(identifiers={(DOMAIN, module.uid)})
            if dev is not None:
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
        try:
            info = await self.comm.get_smhub_update()
        except HabitronError as err:
            _LOGGER.debug("SmartHub diagnostics update skipped: %s", err)
            return
        if not info or not self.diags:
            return
        hardware = info["hardware"]
        software = info["software"]
        self._set(
            self.diags[0], float(hardware["cpu"]["frequency current"].rstrip("MHz"))
        )
        self._set(self.diags[1], float(hardware["cpu"]["load"].rstrip("%")))
        self._set(self.diags[2], float(hardware["cpu"]["temperature"].rstrip("°C")))
        self._set(self.sensors[0], float(hardware["memory"]["percent"].rstrip("%")))
        self._set(self.sensors[1], float(hardware["disk"]["percent"].rstrip("%")))
        self._set(self.loglvl[0], int(software["loglevel"]["console"]))
        self._set(self.loglvl[1], int(software["loglevel"]["file"]))

    @staticmethod
    def _set(member: Diagnostic | Sensor, value: float) -> None:
        """Set a hub member's value and notify listeners on a change."""
        if member.value != value:
            member.value = value
            member.notify()

    async def async_close(self) -> None:
        """Close the hub's bus client when the entry is unloaded."""
        await self.comm.async_close()
