"""
HVAC channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import asyncio
from collections import namedtuple
from typing import Any, Dict, List, Optional, Tuple, Union

from zigpy.exceptions import ZigbeeException
import zigpy.zcl.clusters.hvac as hvac
from zigpy.zcl.foundation import Status

from homeassistant.core import callback

from .. import registries, typing as zha_typing
from ..const import (
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
    REPORT_CONFIG_OP,
    SIGNAL_ATTR_UPDATED,
)
from ..helpers import retryable_req
from .base import ZigbeeChannel

AttributeUpdateRecord = namedtuple("AttributeUpdateRecord", "attr_id, attr_name, value")
REPORT_CONFIG_CLIMATE = (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 25)
REPORT_CONFIG_CLIMATE_DEMAND = (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 5)
REPORT_CONFIG_CLIMATE_DISCRETE = (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 1)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.Dehumidification.cluster_id)
class Dehumidification(ZigbeeChannel):
    """Dehumidification channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.Fan.cluster_id)
class FanChannel(ZigbeeChannel):
    """Fan channel."""

    _value_attribute = 0

    REPORT_CONFIG = ({"attr": "fan_mode", "config": REPORT_CONFIG_OP},)

    @property
    def fan_mode(self) -> Optional[int]:
        """Return current fan mode."""
        return self.cluster.get("fan_mode")

    async def async_set_speed(self, value) -> None:
        """Set the speed of the fan."""

        try:
            await self.cluster.write_attributes({"fan_mode": value})
        except ZigbeeException as ex:
            self.error("Could not set speed: %s", ex)
            return

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self.get_attribute_value("fan_mode", from_cache=False)

    @callback
    def attribute_updated(self, attrid: int, value: Any) -> None:
        """Handle attribute update from fan cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        if attr_name == "fan_mode":
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", attrid, attr_name, value
            )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.Pump.cluster_id)
class Pump(ZigbeeChannel):
    """Pump channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.Thermostat.cluster_id)
class ThermostatChannel(ZigbeeChannel):
    """Thermostat channel."""

    def __init__(
        self, cluster: zha_typing.ZigpyClusterType, ch_pool: zha_typing.ChannelPoolType
    ) -> None:
        """Init Thermostat channel instance."""
        super().__init__(cluster, ch_pool)
        self._init_attrs = {
            "abs_min_heat_setpoint_limit": True,
            "abs_max_heat_setpoint_limit": True,
            "abs_min_cool_setpoint_limit": True,
            "abs_max_cool_setpoint_limit": True,
            "ctrl_seqe_of_oper": False,
            "local_temp": False,
            "max_cool_setpoint_limit": True,
            "max_heat_setpoint_limit": True,
            "min_cool_setpoint_limit": True,
            "min_heat_setpoint_limit": True,
            "occupancy": False,
            "occupied_cooling_setpoint": False,
            "occupied_heating_setpoint": False,
            "pi_cooling_demand": False,
            "pi_heating_demand": False,
            "running_mode": False,
            "running_state": False,
            "system_mode": False,
            "unoccupied_heating_setpoint": False,
            "unoccupied_cooling_setpoint": False,
        }
        self._abs_max_cool_setpoint_limit = 3200  # 32C
        self._abs_min_cool_setpoint_limit = 1600  # 16C
        self._ctrl_seqe_of_oper = 0xFF
        self._abs_max_heat_setpoint_limit = 3000  # 30C
        self._abs_min_heat_setpoint_limit = 700  # 7C
        self._running_mode = None
        self._max_cool_setpoint_limit = None
        self._max_heat_setpoint_limit = None
        self._min_cool_setpoint_limit = None
        self._min_heat_setpoint_limit = None
        self._local_temp = None
        self._occupancy = None
        self._occupied_cooling_setpoint = None
        self._occupied_heating_setpoint = None
        self._pi_cooling_demand = None
        self._pi_heating_demand = None
        self._running_state = None
        self._system_mode = None
        self._unoccupied_cooling_setpoint = None
        self._unoccupied_heating_setpoint = None
        self._report_config = [
            {"attr": "local_temp", "config": REPORT_CONFIG_CLIMATE},
            {"attr": "occupied_cooling_setpoint", "config": REPORT_CONFIG_CLIMATE},
            {"attr": "occupied_heating_setpoint", "config": REPORT_CONFIG_CLIMATE},
            {"attr": "unoccupied_cooling_setpoint", "config": REPORT_CONFIG_CLIMATE},
            {"attr": "unoccupied_heating_setpoint", "config": REPORT_CONFIG_CLIMATE},
            {"attr": "running_mode", "config": REPORT_CONFIG_CLIMATE},
            {"attr": "running_state", "config": REPORT_CONFIG_CLIMATE_DEMAND},
            {"attr": "system_mode", "config": REPORT_CONFIG_CLIMATE},
            {"attr": "occupancy", "config": REPORT_CONFIG_CLIMATE_DISCRETE},
            {"attr": "pi_cooling_demand", "config": REPORT_CONFIG_CLIMATE_DEMAND},
            {"attr": "pi_heating_demand", "config": REPORT_CONFIG_CLIMATE_DEMAND},
        ]

    @property
    def abs_max_cool_setpoint_limit(self) -> int:
        """Absolute maximum cooling setpoint."""
        return self._abs_max_cool_setpoint_limit

    @property
    def abs_min_cool_setpoint_limit(self) -> int:
        """Absolute minimum cooling setpoint."""
        return self._abs_min_cool_setpoint_limit

    @property
    def abs_max_heat_setpoint_limit(self) -> int:
        """Absolute maximum heating setpoint."""
        return self._abs_max_heat_setpoint_limit

    @property
    def abs_min_heat_setpoint_limit(self) -> int:
        """Absolute minimum heating setpoint."""
        return self._abs_min_heat_setpoint_limit

    @property
    def ctrl_seqe_of_oper(self) -> int:
        """Control Sequence of operations attribute."""
        return self._ctrl_seqe_of_oper

    @property
    def max_cool_setpoint_limit(self) -> int:
        """Maximum cooling setpoint."""
        if self._max_cool_setpoint_limit is None:
            return self.abs_max_cool_setpoint_limit
        return self._max_cool_setpoint_limit

    @property
    def min_cool_setpoint_limit(self) -> int:
        """Minimum cooling setpoint."""
        if self._min_cool_setpoint_limit is None:
            return self.abs_min_cool_setpoint_limit
        return self._min_cool_setpoint_limit

    @property
    def max_heat_setpoint_limit(self) -> int:
        """Maximum heating setpoint."""
        if self._max_heat_setpoint_limit is None:
            return self.abs_max_heat_setpoint_limit
        return self._max_heat_setpoint_limit

    @property
    def min_heat_setpoint_limit(self) -> int:
        """Minimum heating setpoint."""
        if self._min_heat_setpoint_limit is None:
            return self.abs_min_heat_setpoint_limit
        return self._min_heat_setpoint_limit

    @property
    def local_temp(self) -> Optional[int]:
        """Thermostat temperature."""
        return self._local_temp

    @property
    def occupancy(self) -> Optional[int]:
        """Is occupancy detected."""
        return self._occupancy

    @property
    def occupied_cooling_setpoint(self) -> Optional[int]:
        """Temperature when room is occupied."""
        return self._occupied_cooling_setpoint

    @property
    def occupied_heating_setpoint(self) -> Optional[int]:
        """Temperature when room is occupied."""
        return self._occupied_heating_setpoint

    @property
    def pi_cooling_demand(self) -> int:
        """Cooling demand."""
        return self._pi_cooling_demand

    @property
    def pi_heating_demand(self) -> int:
        """Heating demand."""
        return self._pi_heating_demand

    @property
    def running_mode(self) -> Optional[int]:
        """Thermostat running mode."""
        return self._running_mode

    @property
    def running_state(self) -> Optional[int]:
        """Thermostat running state, state of heat, cool, fan relays."""
        return self._running_state

    @property
    def system_mode(self) -> Optional[int]:
        """System mode."""
        return self._system_mode

    @property
    def unoccupied_cooling_setpoint(self) -> Optional[int]:
        """Temperature when room is not occupied."""
        return self._unoccupied_cooling_setpoint

    @property
    def unoccupied_heating_setpoint(self) -> Optional[int]:
        """Temperature when room is not occupied."""
        return self._unoccupied_heating_setpoint

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        setattr(self, f"_{attr_name}", value)
        self.async_send_signal(
            f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
            AttributeUpdateRecord(attrid, attr_name, value),
        )

    async def _chunk_attr_read(self, attrs, cached=False):
        chunk, attrs = attrs[:4], attrs[4:]
        while chunk:
            res, fail = await self.cluster.read_attributes(chunk, allow_cache=cached)
            self.debug("read attributes: Success: %s. Failed: %s", res, fail)
            for attr in chunk:
                self._init_attrs.pop(attr, None)
                if attr in fail:
                    continue
                if isinstance(attr, str):
                    setattr(self, f"_{attr}", res[attr])
                self.async_send_signal(
                    f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                    AttributeUpdateRecord(None, attr, res[attr]),
                )

            chunk, attrs = attrs[:4], attrs[4:]

    async def configure_reporting(self):
        """Configure attribute reporting for a cluster.

        This also swallows DeliveryError exceptions that are thrown when
        devices are unreachable.
        """
        kwargs = {}
        if self.cluster.cluster_id >= 0xFC00 and self._ch_pool.manufacturer_code:
            kwargs["manufacturer"] = self._ch_pool.manufacturer_code

        chunk, rest = self._report_config[:4], self._report_config[4:]
        while chunk:
            attrs = {record["attr"]: record["config"] for record in chunk}
            try:
                res = await self.cluster.configure_reporting_multiple(attrs, **kwargs)
                self._configure_reporting_status(attrs, res[0])
            except (ZigbeeException, asyncio.TimeoutError) as ex:
                self.debug(
                    "failed to set reporting on '%s' cluster for: %s",
                    self.cluster.ep_attribute,
                    str(ex),
                )
                break
            chunk, rest = rest[:4], rest[4:]

    def _configure_reporting_status(
        self, attrs: Dict[Union[int, str], Tuple], res: Union[List, Tuple]
    ) -> None:
        """Parse configure reporting result."""
        if not isinstance(res, list):
            # assume default response
            self.debug(
                "attr reporting for '%s' on '%s': %s",
                attrs,
                self.name,
                res,
            )
            return
        if res[0].status == Status.SUCCESS and len(res) == 1:
            self.debug(
                "Successfully configured reporting for '%s' on '%s' cluster: %s",
                attrs,
                self.name,
                res,
            )
            return

        failed = [
            self.cluster.attributes.get(r.attrid, [r.attrid])[0]
            for r in res
            if r.status != Status.SUCCESS
        ]
        attrs = {self.cluster.attributes.get(r, [r])[0] for r in attrs}
        self.debug(
            "Successfully configured reporting for '%s' on '%s' cluster",
            attrs - set(failed),
            self.name,
        )
        self.debug(
            "Failed to configure reporting for '%s' on '%s' cluster: %s",
            failed,
            self.name,
            res,
        )

    @retryable_req(delays=(1, 1, 3))
    async def async_initialize_channel_specific(self, from_cache: bool) -> None:
        """Initialize channel."""

        cached = [a for a, cached in self._init_attrs.items() if cached]
        uncached = [a for a, cached in self._init_attrs.items() if not cached]

        await self._chunk_attr_read(cached, cached=True)
        await self._chunk_attr_read(uncached, cached=False)

    async def async_set_operation_mode(self, mode) -> bool:
        """Set Operation mode."""
        if not await self.write_attributes({"system_mode": mode}):
            self.debug("couldn't set '%s' operation mode", mode)
            return False

        self._system_mode = mode
        self.debug("set system to %s", mode)
        return True

    async def async_set_heating_setpoint(
        self, temperature: int, is_away: bool = False
    ) -> bool:
        """Set heating setpoint."""
        if is_away:
            data = {"unoccupied_heating_setpoint": temperature}
        else:
            data = {"occupied_heating_setpoint": temperature}
        if not await self.write_attributes(data):
            self.debug("couldn't set heating setpoint")
            return False

        if is_away:
            self._unoccupied_heating_setpoint = temperature
        else:
            self._occupied_heating_setpoint = temperature
        self.debug("set heating setpoint to %s", temperature)
        return True

    async def async_set_cooling_setpoint(
        self, temperature: int, is_away: bool = False
    ) -> bool:
        """Set cooling setpoint."""
        if is_away:
            data = {"unoccupied_cooling_setpoint": temperature}
        else:
            data = {"occupied_cooling_setpoint": temperature}
        if not await self.write_attributes(data):
            self.debug("couldn't set cooling setpoint")
            return False
        if is_away:
            self._unoccupied_cooling_setpoint = temperature
        else:
            self._occupied_cooling_setpoint = temperature
        self.debug("set cooling setpoint to %s", temperature)
        return True

    async def get_occupancy(self) -> Optional[bool]:
        """Get unreportable occupancy attribute."""
        try:
            res, fail = await self.cluster.read_attributes(["occupancy"])
            self.debug("read 'occupancy' attr, success: %s, fail: %s", res, fail)
            if "occupancy" not in res:
                return None
            self._occupancy = res["occupancy"]
            return bool(self.occupancy)
        except ZigbeeException as ex:
            self.debug("Couldn't read 'occupancy' attribute: %s", ex)

    async def write_attributes(self, data, **kwargs):
        """Write attributes helper."""
        try:
            res = await self.cluster.write_attributes(data, **kwargs)
        except ZigbeeException as exc:
            self.debug("couldn't write %s: %s", data, exc)
            return False

        self.debug("wrote %s attrs, Status: %s", data, res)
        return self.check_result(res)

    @staticmethod
    def check_result(res: list) -> bool:
        """Normalize the result."""
        if not isinstance(res, list):
            return False

        return all([record.status == Status.SUCCESS for record in res[0]])


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.UserInterface.cluster_id)
class UserInterface(ZigbeeChannel):
    """User interface (thermostat) channel."""
