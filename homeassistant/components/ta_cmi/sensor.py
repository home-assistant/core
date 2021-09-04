"""C.M.I sensor platform."""
import asyncio
from typing import Dict, List

from ta_cmi import (
    ApiError,
    Channel,
    ChannelMode,
    Device,
    InvalidCredentialsError,
    RateLimitError,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    _LOGGER,
    CONF_CHANNELS,
    CONF_CHANNELS_DEVICE_CLASS,
    CONF_CHANNELS_ID,
    CONF_CHANNELS_NAME,
    CONF_CHANNELS_TYPE,
    CONF_DEVICE_FETCH_MODE,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    DEFAULT_DEVICE_CLASS_MAP,
    DOMAIN,
    SCAN_INTERVAL,
)

API_VERSION: str = "api_version"
DEVICE_TYPE: str = "device_type"


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up entries."""
    config = hass.data[DOMAIN][config_entry.entry_id]

    host: str = config[CONF_HOST]
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]

    devices: Dict = config[CONF_DEVICES]

    async def async_update_data():
        """Fetch data from C.M.I."""
        try:
            data: Dict = {}

            for dev in devices:
                id: str = dev[CONF_DEVICE_ID]
                device: Device = Device(id, host, username, password)
                await device.update()

                fetchmode: str = dev[CONF_DEVICE_FETCH_MODE]

                data[id] = {
                    "I": {},
                    "O": {},
                    API_VERSION: device.apiVersion,
                    DEVICE_TYPE: device.getDeviceType(),
                }

                channelOptions: List = []

                for ch in dev[CONF_CHANNELS]:
                    channelOptions.append(
                        {
                            CONF_CHANNELS_ID: ch[CONF_CHANNELS_ID],
                            CONF_CHANNELS_TYPE: ch[CONF_CHANNELS_TYPE],
                            CONF_CHANNELS_NAME: ch[CONF_CHANNELS_NAME],
                            CONF_CHANNELS_DEVICE_CLASS: ch[CONF_CHANNELS_DEVICE_CLASS],
                        }
                    )

                for chID in device.inputs:
                    name = None
                    deviceClass = None

                    for i in channelOptions:
                        if (
                            chID == i[CONF_CHANNELS_ID]
                            and i[CONF_CHANNELS_TYPE] == "input"
                        ):
                            name = i[CONF_CHANNELS_NAME]
                            if len(i[CONF_CHANNELS_DEVICE_CLASS]) != 0:
                                deviceClass = i[CONF_CHANNELS_DEVICE_CLASS]
                            break

                    if (
                        name is not None and fetchmode == "defined"
                    ) or fetchmode == "all":
                        ch: Channel = device.inputs[chID]

                        data[id]["I"][chID] = {
                            "channel": ch,
                            "name": name,
                            "deviceClass": deviceClass,
                        }

                for chID in device.outputs:
                    name = None
                    deviceClass = None

                    for i in channelOptions:
                        if (
                            chID == i[CONF_CHANNELS_ID]
                            and i[CONF_CHANNELS_TYPE] == "output"
                        ):
                            name = i[CONF_CHANNELS_NAME]
                            if len(i[CONF_CHANNELS_DEVICE_CLASS]) != 0:
                                deviceClass = i[CONF_CHANNELS_DEVICE_CLASS]
                            break

                    if (
                        name is not None and fetchmode == "defined"
                    ) or fetchmode == "all":
                        ch: Channel = device.outputs[chID]

                        data[id]["O"][chID] = {
                            "channel": ch,
                            "name": name,
                            "deviceClass": deviceClass,
                        }

                if len(devices) != 1:
                    await asyncio.sleep(61)

            return data

        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed from err
        except RateLimitError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    entities: List[DeviceChannel] = []

    device_registry = dr.async_get(hass)

    for idx, ent in enumerate(coordinator.data):
        inputs: Dict = coordinator.data[ent]["I"]
        outputs: Dict = coordinator.data[ent]["O"]

        for chID in inputs:
            entities.append(DeviceChannel(coordinator, ent, chID, "I"))

        for chID in outputs:
            entities.append(DeviceChannel(coordinator, ent, chID, "O"))

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, ent)},
            manufacturer="Technische Alternative",
            name=coordinator.data[ent][DEVICE_TYPE],
            model=coordinator.data[ent][DEVICE_TYPE],
            sw_version=coordinator.data[ent][API_VERSION],
        )

    async_add_entities(entities)


class DeviceChannel(CoordinatorEntity, SensorEntity):
    """Representation of an C.M.I channel."""

    def __init__(self, coordinator, nodeID, id, inputType):
        """Initialize."""
        super().__init__(coordinator)
        self._id = id
        self._value = None
        self._unit = None
        self._nodeID = nodeID
        self._name = None
        self._mode = None
        self._device_class = None
        self._inputType = inputType
        self._coordinator = coordinator

        self._device_Name = None
        self._device_Api_type = None

        self.parseUpdate()

    def parseUpdate(self):
        """Parse data from coordinator."""
        ch: Channel = self._coordinator.data[self._nodeID][self._inputType][self._id][
            "channel"
        ]
        self._name = self._coordinator.data[self._nodeID][self._inputType][self._id][
            "name"
        ]
        self._device_class = self._coordinator.data[self._nodeID][self._inputType][
            self._id
        ]["deviceClass"]

        self._value = ch.value
        self._unit = ch.getUnit()

        self._device_Api_type = self._coordinator.data[self._nodeID][API_VERSION]
        self._device_Name = self._coordinator.data[self._nodeID][DEVICE_TYPE]

        if ch.mode == ChannelMode.INPUT:
            self._mode = "Input"
        else:
            self._mode = "Output"

        if self._unit == "On/Off":
            self._unit = ""
            if bool(self._value):
                self._value = "On"
            else:
                self._value = "Off"

        if self._unit == "No/Yes":
            self._unit = ""
            if bool(self._value):
                self._value = "Yes"
            else:
                self._value = "No"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        if self._name is not None:
            return self._name

        return f"Node: {self._nodeID} - {self._mode} {self._id}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self._nodeID}-{self._mode}{self._id}"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        self.parseUpdate()
        return self._value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def state_class(self) -> str:
        """Return the state class of the sensor."""
        return "measurement"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            ATTR_NAME: self._device_Name,
            ATTR_IDENTIFIERS: {(DOMAIN, self._nodeID)},
            ATTR_MANUFACTURER: "Technische Alternative",
            ATTR_MODEL: self._device_Name,
            ATTR_SW_VERSION: self._device_Api_type,
        }

    @property
    def device_class(self) -> str:
        """Return the device class of this entity, if any."""
        if self._device_class is None:
            return DEFAULT_DEVICE_CLASS_MAP.get(self._unit, "")
        else:
            return self._device_class
