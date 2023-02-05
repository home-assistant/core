"""The Sungrow Solar Energy integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Optional

from aiohttp import ClientConnectorError
from pymodbus.exceptions import ModbusException
from pysungrow import SungrowClient, identify
from pysungrow.compat import AsyncModbusTcpClient
from pysungrow.definitions.variable import VariableDefinition
from pysungrow.identify import NotASungrowDeviceException

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import BATTERY_DEVICE_VARIABLES, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def has_configuration_page(hass: HomeAssistant, host: str) -> bool:
    """Determine if the Sungrow device has a configuration page.

    It is the WiNet-S dongle that provides the web interface, so if we are connected to the non-dongle Ethernet port
    we will not have a web interface that we can link the user to.
    """
    session = async_get_clientsession(hass)
    try:
        resp = await session.get(f"http://{host}")
        return resp.status == 200
    except ClientConnectorError:
        return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sungrow Solar Energy from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 502)

    client = AsyncModbusTcpClient(
        host, port=port, retry_on_empty=True, retries=3, timeout=5
    )
    try:
        identity = await identify(client, slave=1)
    except NotASungrowDeviceException as err:
        raise ConfigEntryError from err
    except ModbusException as err:
        raise ConfigEntryNotReady from err

    sungrow_client = SungrowClient(client, identity, slave=1)
    await sungrow_client.refresh(
        ["arm_software_version", "dsp_software_version", "battery_type"]
    )

    configuration_url = (
        f"http://{host}" if await has_configuration_page(hass, host) else None
    )

    data = SungrowData(
        hass, identity.serial_number, sungrow_client, configuration_url, entry
    )
    hass.data[DOMAIN][entry.entry_id] = data
    await data.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug(
        "Sungrow setting with host: %s",
        host,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SungrowData(update_coordinator.DataUpdateCoordinator[dict]):
    """Get and update the latest data."""

    def __init__(
        self,
        hass: HomeAssistant,
        serial_number: str,
        client: SungrowClient,
        configuration_url: Optional[str],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the data object."""

        self.serial_number = serial_number
        self._client = client

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{self.serial_number}",
            update_interval=timedelta(seconds=60),
        )

        arm_version = self._client.data.get("arm_software_version", None)
        dsp_version = self._client.data.get("dsp_software_version", None)
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.serial_number)},
            name=entry.title,
            manufacturer="Sungrow",
            model=self._client.device.name,
            sw_version=f"{arm_version}\n{dsp_version}"
            if arm_version and dsp_version
            else None,
            configuration_url=configuration_url,
        )

        battery_type = (
            self._client.data["battery_type"]
            if "battery_type" in self._client.keys
            else None
        )
        self.battery_info = DeviceInfo(
            identifiers={(DOMAIN, self.serial_number + "-battery")},
            name=f"{entry.title} Battery",
            via_device=(DOMAIN, self.serial_number),
            manufacturer=battery_type.manufacturer if battery_type else None,
        )

        self._last_update_was_successful = False

    @property
    def client(self) -> SungrowClient:
        """Retrieve the client used for this coordinator."""
        return self._client

    async def _async_update_data(self):
        """Update the data from the Sungrow device."""
        try:
            await self._client.refresh()
            return self._client.data
        except ModbusException as err:
            raise UpdateFailed(f"Error communicating with inverter: {err}") from err


class SungrowCoordinatorEntity(CoordinatorEntity[SungrowData]):
    """A base entity for entities using the coordinator in this integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SungrowData,
        device_info: DeviceInfo,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{DOMAIN}-{coordinator.serial_number}-{description.key}"
        self.entity_description = description

    @property
    def variable(self) -> VariableDefinition:
        """Retrieve the variable used for this entity, from which additional metadata can be gotten."""
        variable = self.coordinator.client.variable(self.entity_description.key)
        if not variable:
            raise KeyError("Attempting to retrieve a variable using an unknown key")
        return variable

    @property
    def name(self) -> Optional[str]:
        """Compute the name of this entity."""
        if self.entity_description.name is not None:
            return self.entity_description.name
        name = self.entity_description.key
        if self.entity_description.key in BATTERY_DEVICE_VARIABLES:
            name = name.replace("battery_", "")
        name = name.replace("_", " ").title()
        name = (
            name.replace("Dc", "DC")
            .replace("Arm", "ARM")
            .replace("Dsp", "DSP")
            .replace("Mppt", "MPPT")
            .replace("Drm", "DRM")
            .replace("Pv", "PV")
        )
        return name

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Compute the device class of this entity."""
        if self.entity_description.device_class:
            return (
                SensorDeviceClass(self.entity_description.device_class)
                if self.entity_description.device_class
                else None
            )

        if issubclass(self.__class__, SensorEntity):
            if self.variable.unit == "A":
                return SensorDeviceClass.CURRENT
            if self.variable.unit in ("h", "min", "s"):
                return SensorDeviceClass.DURATION
            if self.variable.unit in ("Wh", "kWh"):
                return SensorDeviceClass.ENERGY
            if self.variable.unit == "Hz":
                return SensorDeviceClass.FREQUENCY
            if self.variable.unit in ("W", "kW"):
                return SensorDeviceClass.POWER
            if self.variable.unit == "var":
                return SensorDeviceClass.REACTIVE_POWER
            if self.variable.unit == "°C":
                return SensorDeviceClass.TEMPERATURE
            if self.variable.unit == "V":
                return SensorDeviceClass.VOLTAGE
            if self.variable.unit == "kg":
                return SensorDeviceClass.WEIGHT

        super_device_class = super().device_class
        return SensorDeviceClass(super_device_class) if super_device_class else None

    @property
    def data(self):
        """Get the variable data for this entity, based on the key in the entity description."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key, None)
