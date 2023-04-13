"""Support for retrieving usage data from Contact Energy."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

import async_timeout
from contact_energy_nz import AuthException, ContactEnergyApi, UsageDatum

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .exceptions import CannotUpdate

ENTITY_ID_SENSOR_FORMAT = SENSOR_DOMAIN + ".contact_enegry_nz_{}"


@dataclass
class ContactEnergyUsageMixin:
    """Extra fields to pass."""

    value_fn: Callable[[UsageDatum], float]
    unit_fn: Callable[[UsageDatum], float]


@dataclass
class ContactEnergyUsageSensorEntityDescription(
    SensorEntityDescription, ContactEnergyUsageMixin
):
    """Describes sensor entity."""


_LOGGER = logging.getLogger(DOMAIN)

SENSOR_TYPES: tuple[ContactEnergyUsageSensorEntityDescription, ...] = (
    ContactEnergyUsageSensorEntityDescription(
        key="value",
        name="Total Monthly Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        translation_key="value",
        value_fn=lambda data: data.value,
        unit_fn=lambda data: data.unit,
    ),
    ContactEnergyUsageSensorEntityDescription(
        key="dollar_value",
        name="Total Monthly Cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="NZD",
        translation_key="dollar_value",
        value_fn=lambda data: data.dollar_value,
        unit_fn=lambda data: data.currency,
    ),
    ContactEnergyUsageSensorEntityDescription(
        key="offpeak_value",
        name="Offpeak Monthly Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        translation_key="offpeak_value",
        value_fn=lambda data: data.offpeak_value,
        unit_fn=lambda data: data.unit,
    ),
    ContactEnergyUsageSensorEntityDescription(
        key="offpeak_dollar_value",
        name="Offpeak Monthly Cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="NZD",
        translation_key="offpeak_dollar_value",
        value_fn=lambda data: data.offpeak_dollar_value,
        unit_fn=lambda data: data.currency,
    ),
    ContactEnergyUsageSensorEntityDescription(
        key="uncharged_value",
        name="Monthly Consumption classed as Free",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        translation_key="uncharged_value",
        value_fn=lambda data: data.uncharged_value,
        unit_fn=lambda data: data.unit,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Contact Energy Sensor Setup."""
    api: ContactEnergyApi = hass.data[DOMAIN][entry.entry_id]
    coordinator = ContactEnergyUsageCoordinator(hass, api, entry)
    await api.account_summary()

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

    def __init__(
        self, hass: HomeAssistant, api: ContactEnergyApi, config_entry: ConfigEntry
    ) -> None:
        """Initialize my coordinator."""
        self.retry = 0
        self._api = api
        self._config_entry = config_entry
        self.device_info = DeviceInfo(
            name="Contact Energy NZ API",
            identifiers={(DOMAIN, api.account_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
        super().__init__(
            hass,
            _LOGGER,
            name="Contact Enegry NZ API",
            update_interval=timedelta(hours=1),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the pricing data from the web service."""
        try:
            async with async_timeout.timeout(60):
                data = await self._api.get_latest_usage()
                self.retry = 0
                return data
        except AuthException as ex:
            self._api = await ContactEnergyApi.from_credentials(
                self._config_entry.data[CONF_USERNAME],
                self._config_entry.data[CONF_PASSWORD],
            )
            await self._api.account_summary()
            if self.retry <= 5:
                self.retry += 1
                _LOGGER.info("Updated token, retrying %s", self.retry)
                return await self._async_update_data()
            raise CannotUpdate("Unable to call Contact energy API") from ex


class ContactEnergyUsageSensor(
    CoordinatorEntity[ContactEnergyUsageCoordinator], SensorEntity
):
    """Entity object for Contact Energy Usage sensor."""

    _usage: UsageDatum = None
    retry = 0

    def __init__(
        self,
        coordinator: ContactEnergyUsageCoordinator,
        description: ContactEnergyUsageSensorEntityDescription,
        account_id,
        contract_id,
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._usage = self.coordinator.data
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        return (
            {}
            if not self._usage
            else {
                "unit_of_measure": self.entity_description.unit_fn(self._usage),
            }
        )

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return (
            0.0
            if not self._usage
            else float(self.entity_description.value_fn(self._usage))
        )

    @property
    def last_reset(self) -> datetime:
        """Return the time when the sensor was last reset, if any.

        Since we are collecting monthly stats, it should have reset on the 1st of current month
        The API happens to return this date so we will rely on it.
        """
        return datetime.now().replace(day=1) if not self._usage else self._usage.date
