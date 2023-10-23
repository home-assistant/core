"""Support for retrieving usage data from Contact Energy."""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, cast

from contact_energy_nz import ContactEnergyApi, UsageDatum

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import InvalidStateError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, UPDATE_INTERVAL_HOURS

ENTITY_ID_SENSOR_FORMAT = SENSOR_DOMAIN + ".contact_energy_nz_{}"


@dataclass
class ContactEnergyUsageMixin:
    """Extra fields to pass."""

    value_fn: Callable[[UsageDatum], float]
    unit_fn: Callable[[UsageDatum], str]


@dataclass
class ContactEnergyUsageSensorEntityDescription(
    SensorEntityDescription, ContactEnergyUsageMixin
):
    """Describes sensor entity."""


_LOGGER = logging.getLogger(DOMAIN)

SENSOR_TYPES: tuple[ContactEnergyUsageSensorEntityDescription, ...] = (
    ContactEnergyUsageSensorEntityDescription(
        has_entity_name=True,
        key="value",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        translation_key="value",
        value_fn=lambda data: float(data.value),
        unit_fn=lambda data: str(data.unit),
    ),
    ContactEnergyUsageSensorEntityDescription(
        has_entity_name=True,
        key="dollar_value",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="NZD",
        translation_key="dollar_value",
        value_fn=lambda data: float(data.dollar_value),
        unit_fn=lambda data: str(data.currency),
    ),
    ContactEnergyUsageSensorEntityDescription(
        has_entity_name=True,
        key="offpeak_value",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        translation_key="offpeak_value",
        value_fn=lambda data: float(data.offpeak_value),
        unit_fn=lambda data: str(data.unit),
    ),
    ContactEnergyUsageSensorEntityDescription(
        has_entity_name=True,
        key="offpeak_dollar_value",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="NZD",
        translation_key="offpeak_dollar_value",
        value_fn=lambda data: float(data.offpeak_dollar_value),
        unit_fn=lambda data: str(data.currency),
    ),
    ContactEnergyUsageSensorEntityDescription(
        has_entity_name=True,
        key="uncharged_value",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        translation_key="uncharged_value",
        value_fn=lambda data: float(data.uncharged_value),
        unit_fn=lambda data: str(data.unit),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Contact Energy Sensor Setup."""
    api: ContactEnergyApi = hass.data[DOMAIN][entry.entry_id]
    coordinator = ContactEnergyUsageCoordinator(hass, api)

    # check if API object has been initialised
    if api.account_id is None or api.contract_id is None:
        raise InvalidStateError(
            f"Entry {entry.unique_id} has no account information fields"
        )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            ContactEnergyUsageSensor(
                coordinator, description, api.account_id, api.contract_id
            )
            for description in SENSOR_TYPES
        ]
    )


class ContactEnergyUsageCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data once per cycle."""

    def __init__(self, hass: HomeAssistant, api: ContactEnergyApi) -> None:
        """Initialize my coordinator."""
        self._api = api
        self.device_info = DeviceInfo(
            name="Contact Energy NZ API",
            identifiers={(DOMAIN, api.account_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
        super().__init__(
            hass,
            _LOGGER,
            name="Contact Energy NZ API",
            update_interval=timedelta(hours=UPDATE_INTERVAL_HOURS),
        )

    async def _async_update_data(self) -> UsageDatum:
        """Get the pricing data from the web service."""
        try:
            async with asyncio.timeout(60):
                data = await self._api.get_latest_usage()
        except Exception as err:
            _LOGGER.error("Failed to update data: %s", err)
            raise UpdateFailed(f"Failed to update data: {err}") from err
        return data


class ContactEnergyUsageSensor(
    CoordinatorEntity[ContactEnergyUsageCoordinator], SensorEntity
):
    """Entity object for Contact Energy Usage sensor."""

    def __init__(
        self,
        coordinator: ContactEnergyUsageCoordinator,
        description: ContactEnergyUsageSensorEntityDescription,
        account_id: str,
        contract_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: ContactEnergyUsageSensorEntityDescription = description
        self.entity_id = ENTITY_ID_SENSOR_FORMAT.format(self.entity_description.key)
        self._attr_unique_id = "_".join(
            [
                DOMAIN,
                "sensor",
                account_id,
                contract_id,
                self.entity_description.key,
            ]
        )
        _LOGGER.info("Initialised %s", self._attr_unique_id)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        return (
            {}
            if not self.coordinator.data
            else {
                "unit_of_measure": self.entity_description.unit_fn(
                    self.coordinator.data
                ),
            }
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return (
            0.0
            if not self.coordinator.data
            else float(self.entity_description.value_fn(self.coordinator.data))
        )

    @property
    def last_reset(self) -> datetime:
        """Return the time when the sensor was last reset, if any.

        Since we are collecting monthly stats, it should have reset on the 1st of current month
        The API happens to return this date so we will rely on it.
        """
        return (
            datetime.now().replace(day=1)
            if not self.coordinator.data
            else cast(datetime, self.coordinator.data.date)
        )
