"""BSBLan base entity."""

from typing import Any, override

from bsblan import (
    BSBLANError,
    HotWaterConfig,
    HotWaterState,
    SetHotWaterParam,
    State,
    StaticState,
)

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BSBLanData, get_bsblan_device_info
from .const import DEFAULT_HOT_WATER_MAX_TEMP, DEFAULT_PORT, DOMAIN, Setpoint
from .coordinator import BSBLanCoordinator, BSBLanFastCoordinator, BSBLanSlowCoordinator
from .helpers import first_temperature, validate_setpoint_order


class BSBLanEntityBase[_T: BSBLanCoordinator](CoordinatorEntity[_T]):
    """Base BSBLan entity with common device info setup."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: _T, data: BSBLanData) -> None:
        """Initialize BSBLan entity with device info."""
        super().__init__(coordinator)
        host = coordinator.config_entry.data[CONF_HOST]
        port = coordinator.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._attr_device_info = get_bsblan_device_info(
            data.device, data.info, host, port
        )


class BSBLanEntity(BSBLanEntityBase[BSBLanFastCoordinator]):
    """Defines a base BSBLan entity using the fast coordinator."""

    def __init__(self, coordinator: BSBLanFastCoordinator, data: BSBLanData) -> None:
        """Initialize BSBLan entity."""
        super().__init__(coordinator, data)


class BSBLanDualCoordinatorEntity(BSBLanEntity):
    """Entity that listens to both fast and slow coordinators."""

    def __init__(
        self,
        fast_coordinator: BSBLanFastCoordinator,
        slow_coordinator: BSBLanSlowCoordinator,
        data: BSBLanData,
    ) -> None:
        """Initialize BSBLan entity with both coordinators."""
        super().__init__(fast_coordinator, data)
        self.slow_coordinator = slow_coordinator

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Also listen to slow coordinator updates
        self.async_on_remove(
            self.slow_coordinator.async_add_listener(self._handle_coordinator_update)
        )


class BSBLanCircuitEntity(BSBLanDualCoordinatorEntity):
    """BSBLan entity belonging to a heating circuit sub-device."""

    def __init__(
        self,
        fast_coordinator: BSBLanFastCoordinator,
        slow_coordinator: BSBLanSlowCoordinator,
        data: BSBLanData,
        circuit: int,
    ) -> None:
        """Initialize BSBLan circuit entity with sub-device info."""
        super().__init__(fast_coordinator, slow_coordinator, data)
        self._circuit = circuit
        mac = data.device.MAC
        host = fast_coordinator.config_entry.data[CONF_HOST]
        port = fast_coordinator.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
        main_info = get_bsblan_device_info(data.device, data.info, host, port)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}-circuit-{circuit}")},
            translation_key="heating_circuit",
            translation_placeholders={"circuit": str(circuit)},
            via_device_id=dr.async_get_device_id_by_identifier(
                fast_coordinator.hass,
                (DOMAIN, mac),
                config_entry_id=fast_coordinator.config_entry.entry_id,
            ),
            manufacturer=main_info.manufacturer,
            model=main_info.model,
            model_id=main_info.model_id,
        )

    @property
    def _circuit_state(self) -> State:
        """Return the state for this circuit."""
        return self.coordinator.data.states[self._circuit]

    @property
    def _circuit_config(self) -> StaticState | None:
        """Return the slow-polled config for this circuit."""
        return (
            self.slow_coordinator.data.heating_config.get(self._circuit)
            if self.slow_coordinator.data
            else None
        )

    @property
    def _comfort_setpoint(self) -> float | None:
        """Return the comfort setpoint."""
        return first_temperature(self._circuit_state.target_temperature)

    @property
    def _reduced_setpoint(self) -> float | None:
        """Return the reduced setpoint."""
        if (config := self._circuit_config) is None:
            return None
        return first_temperature(config.temp_reduced_setpoint)

    @property
    def _protection_setpoint(self) -> float | None:
        """Return the protection setpoint."""
        if (config := self._circuit_config) is None:
            return None
        return first_temperature(config.heating_protective_setpoint)

    def _validate_setpoint(self, temperature: float, setpoint: Setpoint) -> None:
        """Keep the reduced setpoint at or below the comfort setpoint."""
        if setpoint is Setpoint.REDUCED:
            validate_setpoint_order(
                temperature, "reduced_above_comfort", maximum=self._comfort_setpoint
            )
        else:
            validate_setpoint_order(
                temperature, "comfort_below_reduced", minimum=self._reduced_setpoint
            )

    async def _async_set_setpoint(self, temperature: float, setpoint: Setpoint) -> None:
        """Write the comfort or reduced setpoint."""
        if setpoint is Setpoint.REDUCED:
            await self._async_thermostat(
                temp_reduced_setpoint=temperature, refresh_config=True
            )
        else:
            await self._async_thermostat(target_temperature=temperature)

    async def _async_thermostat(
        self, *, refresh_config: bool = False, **kwargs: Any
    ) -> None:
        """Write a thermostat parameter, then refresh the state."""
        try:
            await self.coordinator.client.thermostat(**kwargs, circuit=self._circuit)
        except BSBLANError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_data_error",
            ) from err
        # The config holds the reduced setpoint, refresh it before the state
        # so the comfort level in effect is derived from up-to-date values
        if refresh_config:
            await self.slow_coordinator.async_refresh()
        await self.coordinator.async_refresh_circuit(self._circuit)


class BSBLanWaterHeaterDeviceEntity(BSBLanDualCoordinatorEntity):
    """BSBLan entity belonging to the water heater sub-device."""

    def __init__(
        self,
        fast_coordinator: BSBLanFastCoordinator,
        slow_coordinator: BSBLanSlowCoordinator,
        data: BSBLanData,
    ) -> None:
        """Initialize BSBLan water heater sub-device entity."""
        super().__init__(fast_coordinator, slow_coordinator, data)
        mac = data.device.MAC
        host = fast_coordinator.config_entry.data[CONF_HOST]
        port = fast_coordinator.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
        main_info = get_bsblan_device_info(data.device, data.info, host, port)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}-water-heater")},
            translation_key="water_heater",
            via_device_id=dr.async_get_device_id_by_identifier(
                fast_coordinator.hass,
                (DOMAIN, mac),
                config_entry_id=fast_coordinator.config_entry.entry_id,
            ),
            manufacturer=main_info.manufacturer,
            model=main_info.model,
            model_id=main_info.model_id,
        )

    @property
    def _dhw(self) -> HotWaterState:
        """Return DHW state data.

        Water heater entities are only created when DHW data is available.
        """
        dhw = self.coordinator.data.dhw
        assert dhw is not None
        return dhw

    @property
    def _dhw_config(self) -> HotWaterConfig | None:
        """Return the slow-coordinator DHW config.

        It may still be pending when the platform is set up.
        """
        return (
            self.slow_coordinator.data.dhw_config
            if self.slow_coordinator.data
            else None
        )

    @property
    def _setpoint_max(self) -> float:
        """Return the highest DHW setpoint, or the default until it is fetched."""
        if (dhw_config := self._dhw_config) is not None and (
            maximum := first_temperature(dhw_config.nominal_setpoint_max)
        ) is not None:
            return maximum
        return DEFAULT_HOT_WATER_MAX_TEMP

    @property
    def _nominal_setpoint(self) -> float | None:
        """Return the nominal DHW setpoint."""
        return first_temperature(self._dhw.nominal_setpoint)

    @property
    def _reduced_setpoint(self) -> float | None:
        """Return the reduced DHW setpoint."""
        if (dhw_config := self._dhw_config) is None:
            return None
        return first_temperature(dhw_config.reduced_setpoint)

    def _validate_setpoint(self, temperature: float, setpoint: Setpoint) -> None:
        """Keep the reduced setpoint at or below the nominal setpoint."""
        if setpoint is Setpoint.REDUCED:
            validate_setpoint_order(
                temperature, "reduced_above_nominal", maximum=self._nominal_setpoint
            )
        else:
            validate_setpoint_order(
                temperature, "nominal_below_reduced", minimum=self._reduced_setpoint
            )

    async def _async_set_setpoint(self, temperature: float, setpoint: Setpoint) -> None:
        """Write the nominal or reduced setpoint."""
        if setpoint is Setpoint.REDUCED:
            await self._async_set_hot_water(
                SetHotWaterParam(reduced_setpoint=temperature),
                "set_temperature_error",
                refresh_config=True,
            )
        else:
            await self._async_set_hot_water(
                SetHotWaterParam(nominal_setpoint=temperature),
                "set_temperature_error",
            )

    async def _async_set_hot_water(
        self,
        params: SetHotWaterParam,
        error_translation_key: str,
        *,
        refresh_config: bool = False,
    ) -> None:
        """Write a hot water parameter, then refresh the state."""
        try:
            await self.coordinator.client.set_hot_water(params)
        except BSBLANError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=error_translation_key,
            ) from err
        if refresh_config:
            await self.slow_coordinator.async_refresh()
        await self.coordinator.async_refresh_hot_water()
