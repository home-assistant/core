"""Update coordinator for Luxtronik integration."""
# region Imports
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
import re
import threading
from types import MappingProxyType
from typing import Any, Concatenate, Final, TypeVar

from luxtronik import Calculations, Luxtronik, Parameters, Visibilities
from typing_extensions import ParamSpec

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CALCULATIONS,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    DOMAIN,
    LOGGER,
    LUX_PARAMETER_MK_SENSORS,
    DeviceKey,
    LuxCalculation,
    LuxMkTypes,
    LuxParameter,
    LuxVisibility,
)
from .lux_helper import get_manufacturer_by_model
from .model import LuxtronikEntityDescription

# endregion Imports

_LuxtronikCoordinatorT = TypeVar("_LuxtronikCoordinatorT", bound="LuxtronikCoordinator")
_P = ParamSpec("_P")

SCAN_INTERVAL: Final = timedelta(seconds=10)


def catch_luxtronik_errors(
    func: Callable[Concatenate[_LuxtronikCoordinatorT, _P], Awaitable[None]]
) -> Callable[Concatenate[_LuxtronikCoordinatorT, _P], Coroutine[Any, Any, None]]:
    """Catch Luxtronik errors."""

    @wraps(func)
    async def wrapper(
        self: _LuxtronikCoordinatorT,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Catch Luxtronik errors and log message."""
        try:
            await func(self, *args, **kwargs)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Command error: %s", err)
        await self.async_request_refresh()

    return wrapper


@dataclass
class LuxtronikCoordinatorData:
    """Data Type of LuxtronikCoordinator's data."""

    parameters: Parameters
    calculations: Calculations
    visibilities: Visibilities


class LuxtronikCoordinator(DataUpdateCoordinator[LuxtronikCoordinatorData]):
    """Representation of a Luxtronik Coordinator."""

    device_infos = dict[str, DeviceInfo]()

    def __init__(
        self,
        hass: HomeAssistant,
        client: Luxtronik,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize Luxtronik Client."""

        self.lock = threading.Lock()
        self.client = client
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=SCAN_INTERVAL,
        )
        self._create_device_infos(config)

    async def _async_update_data(self) -> LuxtronikCoordinatorData:
        """Connect and fetch data."""
        self.data = await self._read_data()
        return self.data

    async def _read_data(self) -> LuxtronikCoordinatorData:
        return await self._read_or_write(False, None, None)

    async def write(self, parameter, value) -> LuxtronikCoordinatorData:
        """Write a parameter to the Luxtronik heatpump."""
        return await self._read_or_write(True, parameter, value)

    async def _read_or_write(self, write, parameter, value) -> LuxtronikCoordinatorData:
        if write:
            data = self._write(parameter, value)
        else:
            data = self._read()
        self.async_set_updated_data(data)
        return data

    def _read(self) -> LuxtronikCoordinatorData:
        try:
            with self.lock:
                self.client.read()
        except ConnectionRefusedError as err:
            raise UpdateFailed("Read: Error communicating with device") from err
        except ConnectionResetError as err:
            raise UpdateFailed("Read: Error communicating with device") from err
        except OSError as err:
            raise UpdateFailed("Read: Error communicating with device") from err
        except UpdateFailed:
            pass
        except Exception as err:
            raise UpdateFailed("Read: Error communicating with device") from err
        self.data = LuxtronikCoordinatorData(
            parameters=self.client.parameters,
            calculations=self.client.calculations,
            visibilities=self.client.visibilities,
        )
        return self.data

    def _write(self, parameter, value) -> LuxtronikCoordinatorData:
        try:
            self.client.parameters.set(parameter, value)
            with self.lock:
                self.client.write()
        except ConnectionRefusedError as err:
            LOGGER.exception(err)
            raise UpdateFailed("Read: Error communicating with device") from err
        except ConnectionResetError as err:
            LOGGER.exception(err)
            raise UpdateFailed("Read: Error communicating with device") from err
        except UpdateFailed as err:
            LOGGER.exception(err)
        except Exception as err:
            LOGGER.exception(err)
            raise UpdateFailed("Write: Error communicating with device") from err
        finally:
            self.data = LuxtronikCoordinatorData(
                parameters=self.client.parameters,
                calculations=self.client.calculations,
                visibilities=self.client.visibilities,
            )
            LOGGER.info(
                'LuxtronikDevice.write finished %s value: "%s"',
                parameter,
                value,
            )
        return self.data

    @staticmethod
    def connect(
        hass: HomeAssistant, config_entry: ConfigEntry | dict
    ) -> LuxtronikCoordinator:
        """Connect to heatpump."""
        config: dict[Any, Any] | MappingProxyType[str, Any] | None = None
        if isinstance(config_entry, ConfigEntry):
            host = config_entry.data[CONF_HOST]
            port = config_entry.data[CONF_PORT]
            config = config_entry.data
        else:
            host = config_entry[CONF_HOST]
            port = config_entry[CONF_PORT]
            config = config_entry

        client = Luxtronik(host=host, port=port, safe=False)
        return LuxtronikCoordinator(
            hass=hass,
            client=client,
            config=config,
        )

    def _create_device_infos(self, config: Mapping[str, Any]):
        host = config[CONF_HOST]
        self.device_infos[DeviceKey.domestic_water.value] = self._build_device_info(
            DeviceKey.domestic_water, f"http://{host}/"
        )

    def _build_device_info(self, key: DeviceKey, configuration_url: str) -> DeviceInfo:
        text = self.get_device_entity_title(key.value, "device")
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.unique_id}_{key.value}".lower(),
                )
            },
            configuration_url=configuration_url,
            name=f"{text}",
            manufacturer=self.manufacturer,
            model=self.model,
            suggested_area="Utility room",
            sw_version=self.firmware_version,
        )

    def get_device_entity_title(self, key: str, platform: Platform | str) -> str:
        """Get a device or entity title text in locale language."""
        return key

    @property
    def serial_number(self) -> str:
        """Return the serial number."""
        serial_number_date = self.get_value(LuxParameter.P0874_SERIAL_NUMBER)
        serial_number_hex = hex(
            int(self.get_value(LuxParameter.P0875_SERIAL_NUMBER_MODEL))
        )
        return f"{serial_number_date}-{serial_number_hex}".replace("x", "")

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self.serial_number.lower().replace("-", "_")

    @property
    def model(self) -> str:
        """Return the heatpump model."""
        return self.get_value(LuxCalculation.C0078_MODEL_CODE)

    @property
    def manufacturer(self) -> str | None:
        """Return the heatpump manufacturer."""
        return get_manufacturer_by_model(self.model)

    @property
    def firmware_version(self) -> str:
        """Return the heatpump firmware version."""
        return str(self.get_value(LuxCalculation.C0081_FIRMWARE_VERSION))

    @property
    def firmware_version_minor(self) -> int:
        """Return the heatpump firmware minor version."""
        ver = self.firmware_version
        if ver is None:
            return 0
        return int(ver.split(".")[1])

    def entity_visible(self, description: LuxtronikEntityDescription) -> bool:
        """Is description visible."""
        if description.visibility is None:
            return True
        # Detecting some options based on visibilities doesn't work reliably.
        # Use special functions
        if description.visibility in [
            LuxVisibility.V0038_SOLAR_COLLECTOR,
            LuxVisibility.V0039_SOLAR_BUFFER,
            LuxVisibility.V0250_SOLAR,
        ]:
            return self.detect_solar_present()
        return self.get_value(description.visibility) > 0

    def entity_active(self, description: LuxtronikEntityDescription) -> bool:
        """Is description activated."""
        if (
            description.min_firmware_version_minor is not None
            and description.min_firmware_version_minor.value
            > self.firmware_version_minor
        ):
            return False
        if not self.device_key_active(description.device_key):
            return False
        if description.invisibly_if_value is not None:
            return description.invisibly_if_value != self.get_value(
                description.luxtronik_key
            )
        return True

    def device_key_active(self, device_key: DeviceKey) -> bool:
        """Is device key activated."""
        if device_key == DeviceKey.heatpump:
            return True
        if device_key == DeviceKey.heating:
            return self.has_heating
        if device_key == DeviceKey.domestic_water:
            return self.has_domestic_water
        if device_key == DeviceKey.cooling:
            return self.detect_cooling_present()
        raise NotImplementedError

    @property
    def has_heating(self) -> bool:
        """Is heating activated."""
        return bool(self.get_value(LuxVisibility.V0023_FLOW_IN_TEMPERATURE))

    @property
    def has_domestic_water(self) -> bool:
        """Is domestic water activated."""
        return bool(self.get_value(LuxVisibility.V0029_DOMESTIC_WATER_TEMPERATURE))

    def get_value(
        self, group_sensor_id: str | LuxParameter | LuxCalculation | LuxVisibility
    ):
        """Get a sensor value from Luxtronik."""
        if not isinstance(group_sensor_id, str):
            group_sensor_id = group_sensor_id.value
        sensor = self.get_sensor_by_id(str(group_sensor_id))
        if sensor is None:
            return None
        return sensor.value

    def get_sensor_by_id(self, group_sensor_id: str):
        """Get a sensor object by id from Luxtronik."""
        try:
            group = group_sensor_id.split(".")[0]
            sensor_id = group_sensor_id.split(".")[1]
            return self.get_sensor(group, sensor_id)
        except IndexError as error:
            LOGGER.critical(group_sensor_id, error, exc_info=True)

    def get_sensor(self, group, sensor_id):
        """Get sensor by configured sensor ID."""
        sensor = None
        if group == CONF_PARAMETERS:
            sensor = self.client.parameters.get(sensor_id)
        if group == CONF_CALCULATIONS:
            sensor = self.client.calculations.get(sensor_id)
        if group == CONF_VISIBILITIES:
            sensor = self.client.visibilities.get(sensor_id)
        return sensor

    def detect_cooling_mk(self):
        """We iterate over the mk sensors, detect cooling and return a list of parameters that are may show cooling is enabled."""
        cooling_mk = []
        for mk_sensor in LUX_PARAMETER_MK_SENSORS:
            sensor_value = self.get_value(mk_sensor)
            if sensor_value in [
                LuxMkTypes.cooling.value,
                LuxMkTypes.heating_cooling.value,
            ]:
                cooling_mk = cooling_mk + [mk_sensor]

        return cooling_mk

    def detect_solar_present(self) -> bool:
        """Detect and returns True if solar is present."""
        return (
            bool(self.get_value(LuxVisibility.V0250_SOLAR))
            or self.get_value(LuxParameter.P0882_SOLAR_OPERATION_HOURS) > 0.01
            or bool(self.get_value(LuxVisibility.V0038_SOLAR_COLLECTOR))
            or float(self.get_value(LuxCalculation.C0026_SOLAR_COLLECTOR_TEMPERATURE))
            != 5.0
            or bool(self.get_value(LuxVisibility.V0039_SOLAR_BUFFER))
            or float(self.get_value(LuxCalculation.C0027_SOLAR_BUFFER_TEMPERATURE))
            != 150.0
        )

    def detect_cooling_present(self) -> bool:
        """Detect and returns True if Cooling is present."""
        cooling_present = len(self.detect_cooling_mk()) > 0
        return cooling_present

    def detect_cooling_target_temperature_sensor(self):
        """
        If only 1 MK parameter related to cooling is returned.

        The corresponding cooling_target_temperature sensor is returned.
        """
        mk_param = self.detect_cooling_mk()
        if len(mk_param) == 1:
            mk_number = re.findall("[0-9]+", mk_param[0])[0]
            cooling_target_temperature_sensor = (
                f"parameters.ID_Sollwert_KuCft{mk_number}_akt"
            )
        else:
            cooling_target_temperature_sensor = None
        return cooling_target_temperature_sensor

    async def async_shutdown(self):
        """Make sure a coordinator is shut down as well as it's connection."""
        if self.client is not None:
            del self.client
