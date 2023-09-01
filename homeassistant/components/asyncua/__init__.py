"""The asyncua integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import functools
import logging
import time
from typing import Any, Union

from asyncua import Client, ua
from asyncua.common import ua_utils
from asyncua.ua.uatypes import DataValue
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .const import (
    ATTR_NODE_HUB,
    ATTR_NODE_ID,
    ATTR_VALUE,
    CONF_HUB_ID,
    CONF_HUB_MANUFACTURER,
    CONF_HUB_MODEL,
    CONF_HUB_PASSWORD,
    CONF_HUB_SCAN_INTERVAL,
    CONF_HUB_URL,
    CONF_HUB_USERNAME,
    CONF_NODE_ID,
    CONF_NODE_NAME,
    DOMAIN,
    SERVICE_SET_VALUE,
)

_LOGGER = logging.getLogger("asyncua")
_LOGGER.setLevel(logging.WARNING)

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HUB_ID): cv.string,
        vol.Required(CONF_HUB_URL): cv.string,
        vol.Optional(CONF_HUB_MANUFACTURER, default=""): cv.string,
        vol.Optional(CONF_HUB_MODEL, default=""): cv.string,
        vol.Optional(CONF_HUB_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.string,
        vol.Inclusive(CONF_HUB_USERNAME, None): cv.string,
        vol.Inclusive(CONF_HUB_PASSWORD, None): cv.string,
    }
)

SERVICE_SET_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NODE_HUB): cv.string,
        vol.Required(ATTR_NODE_ID): cv.string,
        vol.Required(ATTR_VALUE): vol.Any(
            float,
            int,
            str,
            cv.byte,
            cv.boolean,
            cv.time,
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Any(BASE_SCHEMA),
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(
    hass: HomeAssistant,
    config: ConfigType,
) -> bool:
    """Set up the template for asyncua including OpcuaHub and AsyncuaCoordinator."""
    hass.data[DOMAIN] = {}

    async def _set_value(service):
        hub = hass.data[DOMAIN][service.data.get(ATTR_NODE_HUB)].hub
        await hub.set_value(
            nodeid=service.data[ATTR_NODE_ID],
            value=service.data[ATTR_VALUE],
        )
        return True

    async def _configure_hub(hub: dict) -> None:
        if hub[CONF_HUB_ID] in hass.data[DOMAIN]:
            raise ConfigEntryError(
                f"Duplicated hub detected {hub[CONF_HUB_ID]}. "
                f"OPCUA hub name must be unique."
            )
        hass.data[DOMAIN][hub[CONF_HUB_ID]] = AsyncuaCoordinator(
            hass=hass,
            name=hub[CONF_HUB_ID],
            hub=OpcuaHub(
                hub_name=hub[CONF_HUB_ID],
                hub_manufacturer=hub[CONF_HUB_MANUFACTURER],
                hub_model=hub[CONF_HUB_MODEL],
                hub_url=hub[CONF_HUB_URL],
                username=hub.get(CONF_HUB_USERNAME),
                password=hub.get(CONF_HUB_PASSWORD),
            ),
            update_interval_in_second=hub.get(
                CONF_HUB_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        )
        await hass.data[DOMAIN][hub[CONF_HUB_ID]].async_config_entry_first_refresh()
        hass.services.async_register(
            domain=DOMAIN,
            service=f"{hub[CONF_HUB_ID]}.{SERVICE_SET_VALUE}",
            service_func=_set_value,
            schema=SERVICE_SET_VALUE_SCHEMA,
        )

    configure_hub_tasks = [_configure_hub(hub) for hub in config[DOMAIN]]
    await asyncio.gather(*configure_hub_tasks)

    return True


class OpcuaHub:
    """Hub that coordinate communicate to OPCUA server."""

    def __init__(
        self,
        hub_name: str,
        hub_manufacturer: str,
        hub_model: str,
        hub_url: str,
        username: Union[str, None] = None,
        password: Union[str, None] = None,
        timeout: float = 4,
    ) -> None:
        """Initialize the OPCUA hub."""
        self._hub_name = hub_name
        self._hub_url = hub_url
        self._username = username
        self._password = password
        self._timeout = timeout
        self.device_info = DeviceInfo(
            configuration_url=hub_url,
            manufacturer=hub_manufacturer,
            model=hub_model,
        )

        """Asyncua client"""
        self.client: Client = Client(
            url=hub_url,
            timeout=5,
        )
        self.client.secure_channel_timeout = 60000  # 1 minute
        self.client.session_timeout = 60000  # 1 minute
        if self._username is not None:
            self.client.set_user(username=self._username)
        if self._password is not None:
            self.client.set_password(pwd=self._password)

        self.packet_count: int = 0
        self.elapsed_time: float = 0

    @property
    def hub_name(self) -> str:
        """Return opcua hub name."""
        return self._hub_name

    @property
    def hub_url(self) -> str:
        """Return opcua hub url."""
        return self._hub_url

    @staticmethod
    def asyncua_wrapper(
        func: Callable[..., Any],
    ) -> Callable[..., Any]:
        """Wrap function to manage OPCUA transaction."""

        @functools.wraps(func)
        async def get_set_wrapper(self, *args: Any, **kwargs: Any) -> Any:
            try:
                start_time = time.perf_counter()
                async with self.client:
                    data = await func(self, *args, **kwargs)
                    self.packet_count += 1
                    self.elapsed_time = time.perf_counter() - start_time
                return data
            except RuntimeError as e:
                _LOGGER.error(f"Runtime error: {e}")
            except (asyncio.TimeoutError, TimeoutError) as e:
                raise ConfigEntryNotReady(
                    f"Timeout while connecting to {self.hub_name} {self.hub_url}"
                ) from e
            except ConnectionRefusedError as e:
                raise ConfigEntryAuthFailed(
                    f"Authentication failed while connecting to {self.hub_name}"
                ) from e

        return get_set_wrapper

    @asyncua_wrapper
    async def get_values(self, node_key_pair: dict[str, str]) -> Union[dict, None]:
        """Get multiple node values and return value in zip dictionary format."""
        if not (node_key_pair):
            return {}
        nodes = [
            self.client.get_node(nodeid=nodeid) for key, nodeid in node_key_pair.items()
        ]
        vals = await self.client.read_values(nodes=nodes)
        return dict(zip(node_key_pair.keys(), vals))

    @asyncua_wrapper
    async def set_value(self, nodeid: str, value: Any) -> bool:
        """Get node variant type automatically and set the value."""
        node = self.client.get_node(nodeid=nodeid)
        node_type = await node.read_data_type_as_variant_type()
        var = ua.Variant(
            ua_utils.string_to_val(
                string=str(value),
                vtype=node_type,
            )
        )
        await node.write_value(DataValue(var))
        return True


class AsyncuaCoordinator(DataUpdateCoordinator):
    """Coordinator to manage fetching data using OpcuaHub from OPCUA server."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        hub: OpcuaHub,
        update_interval_in_second: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        self._hub = hub
        self._sensors: list = []
        self._node_key_pair: dict[str, str] = {}
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=update_interval_in_second,
        )

    @property
    def hub(self) -> OpcuaHub:
        """Return OpcuaHub class."""
        return self._hub

    @property
    def sensors(self) -> list:
        """Return all sensors mapped to the OpcuaHub."""
        return self._sensors

    @property
    def node_key_pair(self) -> dict:
        """Return all the node key pairs mapped to the OpcuaHub."""
        return self._node_key_pair

    def add_sensors(self, sensors: list[dict[str, str]]) -> bool:
        """Add new sensors to the sensor list."""
        self._sensors.extend(sensors)
        for _idx_sensor, val_sensor in enumerate(self._sensors):
            self._node_key_pair[val_sensor[CONF_NODE_NAME]] = val_sensor[CONF_NODE_ID]
        return True

    async def _async_update_data(self) -> Union[dict[str, Any], None]:
        """Update the state of the sensor."""
        vals = await self.hub.get_values(node_key_pair=self.node_key_pair)
        return {**vals} if vals is not None else {}
