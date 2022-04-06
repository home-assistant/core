"""The Huawei Solar integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import TypedDict, TypeVar

import async_timeout
from huawei_solar import HuaweiSolarBridge, HuaweiSolarException, register_values as rv

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SLAVE_IDS, DATA_UPDATE_COORDINATORS, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huawei Solar from a config entry."""

    primary_bridge = None
    try:
        # Multiple inverters can be connected to each other via a daisy chain,
        # via an internal modbus-network (ie. not the same modbus network that we are
        # using to talk to the inverter).
        #
        # Each inverter receives it's own 'slave id' in that case.
        # The inverter that we use as 'gateway' will then forward the request to
        # the proper inverter.

        #               ┌─────────────┐
        #               │  EXTERNAL   │
        #               │ APPLICATION │
        #               └──────┬──────┘
        #                      │
        #                 ┌────┴────┐
        #                 │PRIMARY  │
        #                 │INVERTER │
        #                 └────┬────┘
        #       ┌──────────────┼───────────────┐
        #       │              │               │
        #  ┌────┴────┐     ┌───┴─────┐    ┌────┴────┐
        #  │ SLAVE X │     │ SLAVE Y │    │SLAVE ...│
        #  └─────────┘     └─────────┘    └─────────┘

        primary_bridge = await HuaweiSolarBridge.create(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            slave_id=entry.data[CONF_SLAVE_IDS][0],
        )

        primary_bridge_device_infos = _compute_device_infos(
            primary_bridge,
            connecting_inverter_device_id=None,
        )

        bridges_with_device_infos: list[
            tuple[HuaweiSolarBridge, HuaweiInverterBridgeDeviceInfos]
        ] = [(primary_bridge, primary_bridge_device_infos)]

        for extra_slave_id in entry.data[CONF_SLAVE_IDS][1:]:
            extra_bridge = await HuaweiSolarBridge.create_extra_slave(
                primary_bridge, extra_slave_id
            )

            extra_bridge_device_infos = _compute_device_infos(
                extra_bridge,
                connecting_inverter_device_id=(DOMAIN, primary_bridge.serial_number),
            )

            bridges_with_device_infos.append((extra_bridge, extra_bridge_device_infos))

        # Now create update coordinators for each bridge
        update_coordinators = []
        for bridge, device_infos in bridges_with_device_infos:
            update_coordinators.append(
                await _create_update_coordinator(
                    hass, bridge, device_infos, UPDATE_INTERVAL
                )
            )

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            DATA_UPDATE_COORDINATORS: update_coordinators,
        }
    except HuaweiSolarException as err:
        if primary_bridge is not None:
            await primary_bridge.stop()

        raise ConfigEntryNotReady from err
    except Exception as err:
        # always try to stop the bridge, as it will keep retrying
        # in the background otherwise!
        if primary_bridge is not None:
            await primary_bridge.stop()

        raise err

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        update_coordinators = hass.data[DOMAIN][entry.entry_id][
            DATA_UPDATE_COORDINATORS
        ]
        for update_coordinator in update_coordinators:
            await update_coordinator.bridge.stop()

        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HuaweiInverterBridgeDeviceInfos(TypedDict):
    """Device Infos for a specific inverter."""

    inverter: DeviceInfo
    power_meter: DeviceInfo | None
    connected_energy_storage: DeviceInfo | None


def _compute_device_infos(
    bridge: HuaweiSolarBridge,
    connecting_inverter_device_id: tuple[str, str] | None,
) -> HuaweiInverterBridgeDeviceInfos:
    """Create the correct DeviceInfo-objects, which can be used to correctly assign to entities in this integration."""

    inverter_device_info = DeviceInfo(
        identifiers={(DOMAIN, bridge.serial_number)},
        name=bridge.model_name,
        manufacturer="Huawei",
        model=bridge.model_name,
        via_device=connecting_inverter_device_id,  # type: ignore[typeddict-item]
    )

    # Add power meter device if a power meter is detected
    power_meter_device_info = None

    if bridge.power_meter_type is not None:
        power_meter_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{bridge.serial_number}/power_meter"),
            },
            name="Power Meter",
            via_device=(DOMAIN, bridge.serial_number),
        )

    # Add battery device if a battery is detected
    battery_device_info = None

    if bridge.battery_1_type != rv.StorageProductModel.NONE:
        battery_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{bridge.serial_number}/connected_energy_storage"),
            },
            name=f"{inverter_device_info['name']} Connected Energy Storage",
            manufacturer=inverter_device_info["manufacturer"],
            model=f"{inverter_device_info['model']} Connected Energy Storage",
            via_device=(DOMAIN, bridge.serial_number),
        )

    return HuaweiInverterBridgeDeviceInfos(
        inverter=inverter_device_info,
        power_meter=power_meter_device_info,
        connected_energy_storage=battery_device_info,
    )


class HuaweiSolarUpdateCoordinator(DataUpdateCoordinator):
    """A specialised DataUpdateCoordinator for Huawei Solar."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        bridge: HuaweiSolarBridge,
        device_infos: HuaweiInverterBridgeDeviceInfos,
        name: str,
        update_interval: timedelta | None = None,
        update_method: Callable[[], Awaitable[T]] | None = None,
        request_refresh_debouncer: Debouncer | None = None,
    ) -> None:
        """Create a HuaweiSolarRegisterUpdateCoordinator."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
            request_refresh_debouncer=request_refresh_debouncer,
        )
        self.bridge = bridge
        self.device_infos = device_infos


async def _create_update_coordinator(
    hass,
    bridge: HuaweiSolarBridge,
    device_infos: HuaweiInverterBridgeDeviceInfos,
    update_interval,
):
    async def async_update_data():
        try:
            async with async_timeout.timeout(20):
                return await bridge.update()
        except HuaweiSolarException as err:
            raise UpdateFailed(
                f"Could not update {bridge.serial_number} values: {err}"
            ) from err

    coordinator = HuaweiSolarUpdateCoordinator(
        hass,
        _LOGGER,
        bridge=bridge,
        device_infos=device_infos,
        name=f"{bridge.serial_number}_data_update_coordinator",
        update_method=async_update_data,
        update_interval=update_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    return coordinator


class HuaweiSolarEntity(Entity):
    """Huawei Solar Entity."""

    def add_name_suffix(self, suffix) -> None:
        """Add a suffix after the current entity name."""
        self._attr_name = f"{self.name}{suffix}"
