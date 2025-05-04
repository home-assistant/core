"""The nut component."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aionut import AIONUTClient, NUTError, NUTLoginError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, INTEGRATION_SUPPORTED_COMMANDS, PLATFORMS

NUT_FAKE_SERIAL = ["unknown", "blank"]

_LOGGER = logging.getLogger(__name__)

type NutConfigEntry = ConfigEntry[NutRuntimeData]


@dataclass
class NutRuntimeData:
    """Runtime data definition."""

    coordinator: DataUpdateCoordinator
    data: PyNUTData
    unique_id: str
    user_available_commands: set[str]


async def async_setup_entry(hass: HomeAssistant, entry: NutConfigEntry) -> bool:
    """Set up Network UPS Tools (NUT) from a config entry."""

    # strip out the stale options CONF_RESOURCES,
    # maintain the entry in data in case of version rollback
    if CONF_RESOURCES in entry.options:
        new_data = {**entry.data, CONF_RESOURCES: entry.options[CONF_RESOURCES]}
        new_options = {k: v for k, v in entry.options.items() if k != CONF_RESOURCES}
        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options
        )

    config = entry.data
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    alias = config.get(CONF_ALIAS)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    if CONF_SCAN_INTERVAL in entry.options:
        current_options = {**entry.options}
        current_options.pop(CONF_SCAN_INTERVAL)
        hass.config_entries.async_update_entry(entry, options=current_options)

    data = PyNUTData(host, port, alias, username, password)

    entry.async_on_unload(data.async_shutdown)

    async def async_update_data() -> dict[str, str]:
        """Fetch data from NUT."""
        try:
            return await data.async_update()
        except NUTLoginError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="device_authentication",
                translation_placeholders={
                    "err": str(err),
                },
            ) from err
        except NUTError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="data_fetch_error",
                translation_placeholders={
                    "err": str(err),
                },
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name="NUT resource status",
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
        always_update=False,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Note that async_listen_once is not used here because the listener
    # could be removed after the event is fired.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, data.async_shutdown)
    )
    status = coordinator.data

    _LOGGER.debug("NUT Sensors Available: %s", status if status else None)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    unique_id = _unique_id_from_status(status)
    if unique_id is None:
        unique_id = entry.entry_id

    elif entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=unique_id)

    if username is not None and password is not None:
        # Dynamically add outlet integration commands
        additional_integration_commands = set()
        if (num_outlets := status.get("outlet.count")) is not None:
            for outlet_num in range(1, int(num_outlets) + 1):
                outlet_num_str: str = str(outlet_num)
                additional_integration_commands |= {
                    f"outlet.{outlet_num_str}.load.cycle",
                    f"outlet.{outlet_num_str}.load.on",
                    f"outlet.{outlet_num_str}.load.off",
                }

        valid_integration_commands = (
            INTEGRATION_SUPPORTED_COMMANDS | additional_integration_commands
        )

        user_available_commands = {
            device_command
            for device_command in await data.async_list_commands() or {}
            if device_command in valid_integration_commands
        }
    else:
        user_available_commands = set()

    _LOGGER.debug(
        "NUT Commands Available: %s",
        user_available_commands if user_available_commands else None,
    )

    entry.runtime_data = NutRuntimeData(
        coordinator, data, unique_id, user_available_commands
    )

    connections: set[tuple[str, str]] | None = None
    if data.device_info.mac_address is not None:
        connections = {(CONNECTION_NETWORK_MAC, data.device_info.mac_address)}

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        connections=connections,
        name=data.name.title(),
        manufacturer=data.device_info.manufacturer,
        model=data.device_info.model,
        model_id=data.device_info.model_id,
        sw_version=data.device_info.firmware,
        serial_number=data.device_info.serial,
        suggested_area=data.device_info.device_location,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NutConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove NUT config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and identifier[1] in config_entry.runtime_data.unique_id
    )


async def _async_update_listener(hass: HomeAssistant, entry: NutConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _manufacturer_from_status(status: dict[str, str]) -> str | None:
    """Find the best manufacturer value from the status."""
    return (
        status.get("device.mfr")
        or status.get("ups.mfr")
        or status.get("ups.vendorid")
        or status.get("driver.version.data")
    )


def _model_from_status(status: dict[str, str]) -> str | None:
    """Find the best model value from the status."""
    return (
        status.get("device.model")
        or status.get("ups.model")
        or status.get("ups.productid")
    )


def _firmware_from_status(status: dict[str, str]) -> str | None:
    """Find the best firmware value from the status."""
    return status.get("ups.firmware") or status.get("ups.firmware.aux")


def _serial_from_status(status: dict[str, str]) -> str | None:
    """Find the best serial value from the status."""
    serial = status.get("device.serial") or status.get("ups.serial")
    if serial and (
        serial.lower() in NUT_FAKE_SERIAL or serial.count("0") == len(serial.strip())
    ):
        return None
    return serial


def _unique_id_from_status(status: dict[str, str]) -> str | None:
    """Find the best unique id value from the status."""
    serial = _serial_from_status(status)
    # We must have a serial for this to be unique
    if not serial:
        return None

    manufacturer = _manufacturer_from_status(status)
    model = _model_from_status(status)

    unique_id_group = []
    if manufacturer:
        unique_id_group.append(manufacturer)
    if model:
        unique_id_group.append(model)
    if serial:
        unique_id_group.append(serial)
    return "_".join(unique_id_group)


@dataclass
class NUTDeviceInfo:
    """Device information for NUT."""

    manufacturer: str | None = None
    model: str | None = None
    model_id: str | None = None
    firmware: str | None = None
    serial: str | None = None
    mac_address: str | None = None
    device_location: str | None = None


class PyNUTData:
    """Stores the data retrieved from NUT.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(
        self,
        host: str,
        port: int,
        alias: str | None,
        username: str | None,
        password: str | None,
        persistent: bool = True,
    ) -> None:
        """Initialize the data object."""

        self._host = host
        self._alias = alias

        self._client = AIONUTClient(self._host, port, username, password, 5, persistent)
        self.ups_list: dict[str, str] | None = None
        self.device_name: str | None = None
        self._status: dict[str, str] | None = None
        self._device_info: NUTDeviceInfo | None = None

    @property
    def status(self) -> dict[str, str] | None:
        """Get latest update if throttle allows. Return status."""
        return self._status

    @property
    def name(self) -> str:
        """Return the name of the NUT device."""
        return self._alias or f"Nut-{self._host}"

    @property
    def device_info(self) -> NUTDeviceInfo:
        """Return the device info for the ups."""
        return self._device_info or NUTDeviceInfo()

    async def _async_get_alias(self) -> str | None:
        """Get the ups alias from NUT."""
        if not (ups_list := await self._client.list_ups()):
            _LOGGER.error("Empty list while getting NUT ups aliases")
            return None
        self.ups_list = ups_list
        return list(ups_list)[0]

    def _get_device_info(self) -> NUTDeviceInfo | None:
        """Get the ups device info from NUT."""
        if not self._status:
            return None

        manufacturer = _manufacturer_from_status(self._status)
        model = _model_from_status(self._status)
        model_id: str | None = self._status.get("device.part")
        firmware = _firmware_from_status(self._status)
        serial = _serial_from_status(self._status)
        mac_address: str | None = self._status.get("device.macaddr")
        if mac_address is not None:
            mac_address = format_mac(mac_address.rstrip().replace(" ", ":"))
        device_location: str | None = self._status.get("device.location")
        return NUTDeviceInfo(
            manufacturer,
            model,
            model_id,
            firmware,
            serial,
            mac_address,
            device_location,
        )

    async def _async_get_status(self) -> dict[str, str]:
        """Get the ups status from NUT."""
        if self._alias is None:
            self._alias = await self._async_get_alias()
        if TYPE_CHECKING:
            assert self._alias is not None
        return await self._client.list_vars(self._alias)

    async def async_update(self) -> dict[str, str]:
        """Fetch the latest status from NUT."""
        self._status = await self._async_get_status()
        if self._device_info is None:
            self._device_info = self._get_device_info()
        if self.device_name is None:
            self.device_name = self.name.title()
        return self._status

    async def async_run_command(self, command_name: str) -> None:
        """Invoke instant command in UPS."""
        if TYPE_CHECKING:
            assert self._alias is not None

        try:
            await self._client.run_command(self._alias, command_name)
        except NUTError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="nut_command_error",
                translation_placeholders={
                    "command_name": command_name,
                    "err": str(err),
                },
            ) from err

    async def async_list_commands(self) -> set[str] | None:
        """Fetch the list of supported commands."""
        if TYPE_CHECKING:
            assert self._alias is not None

        try:
            return await self._client.list_commands(self._alias)
        except NUTError as err:
            _LOGGER.error("Error retrieving supported commands %s", err)
            return None

    @callback
    def async_shutdown(self, _: Event | None = None) -> None:
        """Shutdown the client connection."""
        self._client.shutdown()
