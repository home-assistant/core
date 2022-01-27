"""The Huawei Solar integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import TypedDict, TypeVar

import async_timeout
from huawei_solar import (
    AsyncHuaweiSolar,
    HuaweiSolarException,
    register_names as rn,
    register_values as rv,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BATTERY_UPDATE_INTERVAL,
    CONF_SLAVE_IDS,
    DATA_DEVICE_INFOS,
    DATA_MODBUS_CLIENT,
    DATA_SLAVE_IDS,
    DATA_UPDATE_COORDINATORS,
    DOMAIN,
    INVERTER_UPDATE_INTERVAL,
    METER_UPDATE_INTERVAL,
)
from .entity_descriptions import (
    BATTERY_ENTITY_DESCRIPTIONS,
    INVERTER_ENTITY_DESCRIPTIONS,
    SINGLE_PHASE_METER_ENTITY_DESCRIPTIONS,
    THREE_PHASE_METER_ENTITY_DESCRIPTIONS,
    HuaweiSolarEntityDescriptionMixin,
    get_pv_entity_descriptions,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huawei Solar from a config entry."""

    try:
        inverter = await AsyncHuaweiSolar.create(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            slave=entry.data[CONF_SLAVE_IDS][0],
        )

        primary_slave_devices = await _find_slave_devices(
            inverter,
            slave_id=entry.data[CONF_SLAVE_IDS][0],
            connecting_inverter_device_id=None,
        )

        slave_device_infos = [primary_slave_devices]
        inverter_device_info = primary_slave_devices["inverter"]
        inverter_device_id = next(iter(inverter_device_info["identifiers"]))

        for extra_slave_id in entry.data[CONF_SLAVE_IDS][1:]:
            slave_device_infos.append(
                await _find_slave_devices(
                    inverter,
                    slave_id=extra_slave_id,
                    connecting_inverter_device_id=inverter_device_id,
                )
            )

        # Now create update coordinators for the detected devices
        update_coordinators = []
        for device_info in slave_device_infos:
            update_coordinators.extend(
                await _create_update_coordinators(hass, inverter, device_info)
            )

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            DATA_MODBUS_CLIENT: inverter,
            DATA_SLAVE_IDS: entry.data[CONF_SLAVE_IDS],
            DATA_DEVICE_INFOS: slave_device_infos,
            DATA_UPDATE_COORDINATORS: update_coordinators,
        }
    except HuaweiSolarException as err:
        raise ConfigEntryNotReady from err

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = hass.data[DOMAIN][entry.entry_id][DATA_MODBUS_CLIENT]
        await client.stop()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HuaweiInverterSlaveDeviceInfos(TypedDict):
    """Device Infos from a slave."""

    slave_id: int | None  # When None, we are using the default slave-id from the inverter that we're directly connected to.
    inverter: DeviceInfo
    power_meter: DeviceInfo | None
    connected_energy_storage: DeviceInfo | None


class HuaweiSolarRegisterUpdateCoordinator(DataUpdateCoordinator):
    """A specialised DataUpdateCoordinator.

    It also has information on the entity descriptions of which it has information.
    This allows the platforms to discover which entities they should create from
    this coordinator during setup.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        entity_descriptions: list[HuaweiSolarEntityDescriptionMixin],
        device_info: DeviceInfo,
        slave_id: int | None,
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
        self.entity_descriptions = entity_descriptions
        self.device_info = device_info
        self.slave_id = slave_id


async def _find_slave_devices(
    inverter: AsyncHuaweiSolar,
    slave_id: int | None,
    connecting_inverter_device_id: tuple[str, str] | None,
) -> HuaweiInverterSlaveDeviceInfos:
    """Discover the child devices of this inverter."""

    model_name, serial_number = await inverter.get_multiple(
        [rn.MODEL_NAME, rn.SERIAL_NUMBER], slave_id
    )

    current_inverter_identifier_list = [DOMAIN, model_name.value, serial_number.value]

    if slave_id is not None:
        current_inverter_identifier_list.append(slave_id)

    current_inverter_identifier = tuple(current_inverter_identifier_list)

    inverter_device_info = DeviceInfo(
        identifiers={current_inverter_identifier},  # type: ignore
        name=model_name.value,
        manufacturer="Huawei",
        model=model_name.value,
        via_device=connecting_inverter_device_id,  # type: ignore
    )

    # Add power meter device if a power meter is detected
    power_meter_device_info = None

    has_power_meter = (
        await inverter.get(rn.METER_STATUS, slave_id)
    ).value == rv.MeterStatus.NORMAL

    if has_power_meter:

        power_meter_device_info = DeviceInfo(
            identifiers={
                (*current_inverter_identifier_list, "power_meter"),  # type: ignore
            },
            name="Power Meter",
            via_device=current_inverter_identifier,  # type: ignore
        )

    # Add battery device if a battery is detected
    battery_device_info = None

    has_battery = inverter.battery_type != rv.StorageProductModel.NONE

    if has_battery:
        battery_device_info = DeviceInfo(
            identifiers={
                (*current_inverter_identifier_list, "connected_energy_storage"),  # type: ignore
            },
            name=f"{inverter_device_info['name']} Connected Energy Storage",
            manufacturer=inverter_device_info["manufacturer"],
            model=f"{inverter_device_info['model']} Connected Energy Storage",
            via_device=current_inverter_identifier,  # type: ignore
        )

    return HuaweiInverterSlaveDeviceInfos(
        slave_id=slave_id,
        inverter=inverter_device_info,
        power_meter=power_meter_device_info,
        connected_energy_storage=battery_device_info,
    )


async def _create_update_coordinators(
    hass: HomeAssistant,
    inverter: AsyncHuaweiSolar,
    slave_device_info: HuaweiInverterSlaveDeviceInfos,
) -> list[HuaweiSolarRegisterUpdateCoordinator]:
    """Create the relevant HuaweiSolarRegisterUpdateCoordinator-instances as well."""

    update_coordinators = []

    slave_id = slave_device_info["slave_id"]

    update_coordinators.append(
        await _create_update_coordinator(
            hass,
            inverter,
            slave_id,
            INVERTER_ENTITY_DESCRIPTIONS,
            slave_device_info["inverter"],
            "inverter",
            INVERTER_UPDATE_INTERVAL,
        )
    )

    pv_string_count = (await inverter.get(rn.NB_PV_STRINGS, slave_id)).value
    pv_string_entity_descriptions = []

    for idx in range(1, pv_string_count + 1):
        pv_string_entity_descriptions.extend(get_pv_entity_descriptions(idx))
    update_coordinators.append(
        await _create_update_coordinator(
            hass,
            inverter,
            slave_id,
            pv_string_entity_descriptions,
            slave_device_info["inverter"],
            "pv_strings",
            INVERTER_UPDATE_INTERVAL,
        )
    )

    if slave_device_info["power_meter"]:
        power_meter_type = (await inverter.get(rn.METER_TYPE, slave_id)).value
        meter_entity_descriptions = (
            THREE_PHASE_METER_ENTITY_DESCRIPTIONS
            if power_meter_type == rv.MeterType.THREE_PHASE
            else SINGLE_PHASE_METER_ENTITY_DESCRIPTIONS
        )

        update_coordinators.append(
            await _create_update_coordinator(
                hass,
                inverter,
                slave_id,
                meter_entity_descriptions,
                slave_device_info["power_meter"],
                "power_meter",
                METER_UPDATE_INTERVAL,
            )
        )

    if slave_device_info["connected_energy_storage"]:
        update_coordinators.append(
            await _create_update_coordinator(
                hass,
                inverter,
                slave_id,
                BATTERY_ENTITY_DESCRIPTIONS,
                slave_device_info["connected_energy_storage"],
                "battery",
                BATTERY_UPDATE_INTERVAL,
            )
        )

    return update_coordinators


async def _create_update_coordinator(
    hass,
    inverter: AsyncHuaweiSolar,
    slave_id,
    entity_descriptions,
    device_info,
    coordinator_name,
    update_interval,
):
    entity_registers = [descr.key for descr in entity_descriptions]

    async def async_update_data():
        try:
            async with async_timeout.timeout(10):
                return dict(
                    zip(
                        entity_registers,
                        await inverter.get_multiple(entity_registers, slave_id),
                    )
                )
        except HuaweiSolarException as err:
            raise UpdateFailed(
                f"Could not update {coordinator_name} values: {err}"
            ) from err

    coordinator = HuaweiSolarRegisterUpdateCoordinator(
        hass,
        _LOGGER,
        entity_descriptions,
        device_info,
        slave_id,
        name=f"{coordinator_name}_sensors{f'_slave_{slave_id}' if slave_id else ''}",
        update_method=async_update_data,
        update_interval=update_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    return coordinator
