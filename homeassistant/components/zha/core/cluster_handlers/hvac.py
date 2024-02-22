"""HVAC cluster handlers module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
from __future__ import annotations

from typing import Any

from zigpy.zcl.clusters.hvac import (
    Dehumidification,
    Fan,
    Pump,
    Thermostat,
    UserInterface,
)

from homeassistant.core import callback

from .. import registries
from ..const import (
    REPORT_CONFIG_MAX_INT,
    REPORT_CONFIG_MIN_INT,
    REPORT_CONFIG_OP,
    SIGNAL_ATTR_UPDATED,
)
from . import AttrReportConfig, ClusterHandler

REPORT_CONFIG_CLIMATE = (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 25)
REPORT_CONFIG_CLIMATE_DEMAND = (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 5)
REPORT_CONFIG_CLIMATE_DISCRETE = (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT, 1)


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Dehumidification.cluster_id)
class DehumidificationClusterHandler(ClusterHandler):
    """Dehumidification cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Fan.cluster_id)
class FanClusterHandler(ClusterHandler):
    """Fan cluster handler."""

    _value_attribute = 0

    REPORT_CONFIG = (
        AttrReportConfig(attr=Fan.AttributeDefs.fan_mode.name, config=REPORT_CONFIG_OP),
    )
    ZCL_INIT_ATTRS = {Fan.AttributeDefs.fan_mode_sequence.name: True}

    @property
    def fan_mode(self) -> int | None:
        """Return current fan mode."""
        return self.cluster.get(Fan.AttributeDefs.fan_mode.name)

    @property
    def fan_mode_sequence(self) -> int | None:
        """Return possible fan mode speeds."""
        return self.cluster.get(Fan.AttributeDefs.fan_mode_sequence.name)

    async def async_set_speed(self, value) -> None:
        """Set the speed of the fan."""
        await self.write_attributes_safe({Fan.AttributeDefs.fan_mode.name: value})

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self.get_attribute_value(
            Fan.AttributeDefs.fan_mode.name, from_cache=False
        )

    @callback
    def attribute_updated(self, attrid: int, value: Any, _: Any) -> None:
        """Handle attribute update from fan cluster."""
        attr_name = self._get_attribute_name(attrid)
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        if attr_name == "fan_mode":
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", attrid, attr_name, value
            )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Pump.cluster_id)
class PumpClusterHandler(ClusterHandler):
    """Pump cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Thermostat.cluster_id)
class ThermostatClusterHandler(ClusterHandler):
    """Thermostat cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.local_temperature.name,
            config=REPORT_CONFIG_CLIMATE,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.occupied_cooling_setpoint.name,
            config=REPORT_CONFIG_CLIMATE,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.occupied_heating_setpoint.name,
            config=REPORT_CONFIG_CLIMATE,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.unoccupied_cooling_setpoint.name,
            config=REPORT_CONFIG_CLIMATE,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.unoccupied_heating_setpoint.name,
            config=REPORT_CONFIG_CLIMATE,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.running_mode.name,
            config=REPORT_CONFIG_CLIMATE,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.running_state.name,
            config=REPORT_CONFIG_CLIMATE_DEMAND,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.system_mode.name,
            config=REPORT_CONFIG_CLIMATE,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.occupancy.name,
            config=REPORT_CONFIG_CLIMATE_DISCRETE,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.pi_cooling_demand.name,
            config=REPORT_CONFIG_CLIMATE_DEMAND,
        ),
        AttrReportConfig(
            attr=Thermostat.AttributeDefs.pi_heating_demand.name,
            config=REPORT_CONFIG_CLIMATE_DEMAND,
        ),
    )
    ZCL_INIT_ATTRS: dict[str, bool] = {
        Thermostat.AttributeDefs.abs_min_heat_setpoint_limit.name: True,
        Thermostat.AttributeDefs.abs_max_heat_setpoint_limit.name: True,
        Thermostat.AttributeDefs.abs_min_cool_setpoint_limit.name: True,
        Thermostat.AttributeDefs.abs_max_cool_setpoint_limit.name: True,
        Thermostat.AttributeDefs.ctrl_sequence_of_oper.name: False,
        Thermostat.AttributeDefs.max_cool_setpoint_limit.name: True,
        Thermostat.AttributeDefs.max_heat_setpoint_limit.name: True,
        Thermostat.AttributeDefs.min_cool_setpoint_limit.name: True,
        Thermostat.AttributeDefs.min_heat_setpoint_limit.name: True,
        Thermostat.AttributeDefs.local_temperature_calibration.name: True,
        Thermostat.AttributeDefs.setpoint_change_source.name: True,
    }

    @property
    def abs_max_cool_setpoint_limit(self) -> int:
        """Absolute maximum cooling setpoint."""
        return self.cluster.get(
            Thermostat.AttributeDefs.abs_max_cool_setpoint_limit.name, 3200
        )

    @property
    def abs_min_cool_setpoint_limit(self) -> int:
        """Absolute minimum cooling setpoint."""
        return self.cluster.get(
            Thermostat.AttributeDefs.abs_min_cool_setpoint_limit.name, 1600
        )

    @property
    def abs_max_heat_setpoint_limit(self) -> int:
        """Absolute maximum heating setpoint."""
        return self.cluster.get(
            Thermostat.AttributeDefs.abs_max_heat_setpoint_limit.name, 3000
        )

    @property
    def abs_min_heat_setpoint_limit(self) -> int:
        """Absolute minimum heating setpoint."""
        return self.cluster.get(
            Thermostat.AttributeDefs.abs_min_heat_setpoint_limit.name, 700
        )

    @property
    def ctrl_sequence_of_oper(self) -> int:
        """Control Sequence of operations attribute."""
        return self.cluster.get(
            Thermostat.AttributeDefs.ctrl_sequence_of_oper.name, 0xFF
        )

    @property
    def max_cool_setpoint_limit(self) -> int:
        """Maximum cooling setpoint."""
        sp_limit = self.cluster.get(
            Thermostat.AttributeDefs.max_cool_setpoint_limit.name
        )
        if sp_limit is None:
            return self.abs_max_cool_setpoint_limit
        return sp_limit

    @property
    def min_cool_setpoint_limit(self) -> int:
        """Minimum cooling setpoint."""
        sp_limit = self.cluster.get(
            Thermostat.AttributeDefs.min_cool_setpoint_limit.name
        )
        if sp_limit is None:
            return self.abs_min_cool_setpoint_limit
        return sp_limit

    @property
    def max_heat_setpoint_limit(self) -> int:
        """Maximum heating setpoint."""
        sp_limit = self.cluster.get(
            Thermostat.AttributeDefs.max_heat_setpoint_limit.name
        )
        if sp_limit is None:
            return self.abs_max_heat_setpoint_limit
        return sp_limit

    @property
    def min_heat_setpoint_limit(self) -> int:
        """Minimum heating setpoint."""
        sp_limit = self.cluster.get(
            Thermostat.AttributeDefs.min_heat_setpoint_limit.name
        )
        if sp_limit is None:
            return self.abs_min_heat_setpoint_limit
        return sp_limit

    @property
    def local_temperature(self) -> int | None:
        """Thermostat temperature."""
        return self.cluster.get(Thermostat.AttributeDefs.local_temperature.name)

    @property
    def occupancy(self) -> int | None:
        """Is occupancy detected."""
        return self.cluster.get(Thermostat.AttributeDefs.occupancy.name)

    @property
    def occupied_cooling_setpoint(self) -> int | None:
        """Temperature when room is occupied."""
        return self.cluster.get(Thermostat.AttributeDefs.occupied_cooling_setpoint.name)

    @property
    def occupied_heating_setpoint(self) -> int | None:
        """Temperature when room is occupied."""
        return self.cluster.get(Thermostat.AttributeDefs.occupied_heating_setpoint.name)

    @property
    def pi_cooling_demand(self) -> int:
        """Cooling demand."""
        return self.cluster.get(Thermostat.AttributeDefs.pi_cooling_demand.name)

    @property
    def pi_heating_demand(self) -> int:
        """Heating demand."""
        return self.cluster.get(Thermostat.AttributeDefs.pi_heating_demand.name)

    @property
    def running_mode(self) -> int | None:
        """Thermostat running mode."""
        return self.cluster.get(Thermostat.AttributeDefs.running_mode.name)

    @property
    def running_state(self) -> int | None:
        """Thermostat running state, state of heat, cool, fan relays."""
        return self.cluster.get(Thermostat.AttributeDefs.running_state.name)

    @property
    def system_mode(self) -> int | None:
        """System mode."""
        return self.cluster.get(Thermostat.AttributeDefs.system_mode.name)

    @property
    def unoccupied_cooling_setpoint(self) -> int | None:
        """Temperature when room is not occupied."""
        return self.cluster.get(
            Thermostat.AttributeDefs.unoccupied_cooling_setpoint.name
        )

    @property
    def unoccupied_heating_setpoint(self) -> int | None:
        """Temperature when room is not occupied."""
        return self.cluster.get(
            Thermostat.AttributeDefs.unoccupied_heating_setpoint.name
        )

    @callback
    def attribute_updated(self, attrid: int, value: Any, _: Any) -> None:
        """Handle attribute update cluster."""
        attr_name = self._get_attribute_name(attrid)
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        self.async_send_signal(
            f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
            attrid,
            attr_name,
            value,
        )

    async def async_set_operation_mode(self, mode) -> bool:
        """Set Operation mode."""
        await self.write_attributes_safe(
            {Thermostat.AttributeDefs.system_mode.name: mode}
        )
        return True

    async def async_set_heating_setpoint(
        self, temperature: int, is_away: bool = False
    ) -> bool:
        """Set heating setpoint."""
        attr = (
            Thermostat.AttributeDefs.unoccupied_heating_setpoint.name
            if is_away
            else Thermostat.AttributeDefs.occupied_heating_setpoint.name
        )
        await self.write_attributes_safe({attr: temperature})
        return True

    async def async_set_cooling_setpoint(
        self, temperature: int, is_away: bool = False
    ) -> bool:
        """Set cooling setpoint."""
        attr = (
            Thermostat.AttributeDefs.unoccupied_cooling_setpoint.name
            if is_away
            else Thermostat.AttributeDefs.occupied_cooling_setpoint.name
        )
        await self.write_attributes_safe({attr: temperature})
        return True

    async def get_occupancy(self) -> bool | None:
        """Get unreportable occupancy attribute."""
        res, fail = await self.read_attributes(
            [Thermostat.AttributeDefs.occupancy.name]
        )
        self.debug("read 'occupancy' attr, success: %s, fail: %s", res, fail)
        if Thermostat.AttributeDefs.occupancy.name not in res:
            return None
        return bool(self.occupancy)


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(UserInterface.cluster_id)
class UserInterfaceClusterHandler(ClusterHandler):
    """User interface (thermostat) cluster handler."""

    ZCL_INIT_ATTRS = {UserInterface.AttributeDefs.keypad_lockout.name: True}
