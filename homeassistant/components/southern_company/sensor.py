"""Support for Southern Company sensors."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging

import southern_company_api

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .config_flow import InvalidAuth
from .const import DOMAIN as SOUTHERN_COMPANY_DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:currency-usd"


SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="dollars_to_date",
        name="Monthly cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="total_kwh_used",
        name="Monthly net consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="average_daily_cost",
        name="Average daily cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="average_daily_usage",
        name="Average daily usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="projected_usage_high",
        name="Higher projected monthly usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="projected_usage_low",
        name="Lower projected monthly usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="projected_bill_amount_low",
        name="Lower projected monthly cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="projected_bill_amount_high",
        name="Higher projected monthly cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Southern Company sensor."""

    southern_company_connection = hass.data[SOUTHERN_COMPANY_DOMAIN][entry.entry_id]

    coordinator = SouthernCompanyCoordinator(hass, southern_company_connection)
    entities: list[SouthernCompanySensor] = []
    await southern_company_connection.get_jwt()
    for account in await southern_company_connection.get_accounts():
        device = DeviceInfo(
            identifiers={((SOUTHERN_COMPANY_DOMAIN), account.number)},
            name=f"Account {account.number}",
            manufacturer="Southern Company",
        )
        for sensor in SENSORS:
            entities.append(SouthernCompanySensor(account, coordinator, sensor, device))

    async_add_entities(entities, True)


class SouthernCompanySensor(
    SensorEntity, CoordinatorEntity["SouthernCompanyCoordinator"]
):
    """Representation of a Southern company sensor."""

    def __init__(
        self,
        account: southern_company_api.Account,
        coordinator: SouthernCompanyCoordinator,
        entity_description: SensorEntityDescription,
        device: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._account = account

        self._attr_unique_id = f"{self._account.number}_{self.entity_description.key}"
        self._attr_name = f"{entity_description.name}"
        self._attr_device_info = device
        self._sensor_data = None

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self._sensor_data

    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._sensor_data = getattr(
                self.coordinator.data[self._account.number], self.entity_description.key
            )
            self.async_write_ha_state()


class SouthernCompanyCoordinator(DataUpdateCoordinator):
    """Handle Southern company data and insert statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        southern_company_connection: southern_company_api.SouthernCompanyAPI,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            name="Southern Company",
            update_interval=timedelta(minutes=60),
        )
        self._southern_company_connection = southern_company_connection

    async def _async_update_data(
        self,
    ) -> dict[str, southern_company_api.account.MonthlyUsage]:
        """Update data via API."""
        if self._southern_company_connection.jwt is not None:
            account_month_data: dict[
                str, southern_company_api.account.MonthlyUsage
            ] = {}
            for account in self._southern_company_connection.accounts:
                account_month_data[account.number] = await account.get_month_data(
                    self._southern_company_connection.jwt
                )
            await self._insert_statistics()
            return account_month_data
        raise InvalidAuth("No jwt token")

    async def _insert_statistics(self) -> None:
        """Insert Southern Company statistics."""
        for account in self._southern_company_connection.accounts:
            cost_statistic_id = (
                f"{SOUTHERN_COMPANY_DOMAIN}:energy_" f"cost_" f"{account.number}"
            )
            usage_statistic_id = (
                f"{SOUTHERN_COMPANY_DOMAIN}:energy_" f"usage_" f"{account.number}"
            )

            last_stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, usage_statistic_id, True, {}
            )
            if not last_stats:
                # First time we insert 1 year of data (if available)
                if self._southern_company_connection.jwt is not None:
                    hourly_data = await account.get_hourly_data(
                        datetime.datetime.now() - timedelta(days=365),
                        datetime.datetime.now(),
                        self._southern_company_connection.jwt,
                    )
                else:
                    raise InvalidAuth("No jwt token")

                _cost_sum = 0.0
                _usage_sum = 0.0
                last_stats_time = None
            else:
                # hourly_consumption/production_data contains the last 30 days
                # of consumption/production data.
                # We update the statistics with the last 30 days
                # of data to handle corrections in the data.
                if self._southern_company_connection.jwt is not None:
                    hourly_data = await account.get_hourly_data(
                        datetime.datetime.now() - timedelta(days=31),
                        datetime.datetime.now(),
                        self._southern_company_connection.jwt,
                    )
                else:
                    raise InvalidAuth("No jwt token")

                from_time = hourly_data[0].time
                if from_time is None:
                    continue
                start = from_time - timedelta(hours=1)
                cost_stat = await get_instance(self.hass).async_add_executor_job(
                    statistics_during_period,
                    self.hass,
                    start,
                    None,
                    [cost_statistic_id],
                    "hour",
                    None,
                    {"sum"},
                )
                _cost_sum = cost_stat[cost_statistic_id][0]["sum"]
                last_stats_time = cost_stat[cost_statistic_id][0]["start"]
                usage_stat = await get_instance(self.hass).async_add_executor_job(
                    statistics_during_period,
                    self.hass,
                    start,
                    None,
                    [usage_statistic_id],
                    "hour",
                    None,
                    {"sum"},
                )
                _usage_sum = usage_stat[usage_statistic_id][0]["sum"]

            cost_statistics = []
            usage_statistics = []

            for data in hourly_data:
                if data.cost is None or data.usage is None:
                    continue
                from_time = data.time
                if from_time is None or (
                    last_stats_time is not None and from_time <= last_stats_time
                ):
                    continue

                _cost_sum += data.cost
                _usage_sum += data.cost

                cost_statistics.append(
                    StatisticData(
                        start=from_time,
                        state=data.cost,
                        sum=_cost_sum,
                    )
                )
                usage_statistics.append(
                    StatisticData(
                        start=from_time,
                        state=data.usage,
                        sum=_usage_sum,
                    )
                )

            cost_metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"{account.name} cost",
                source=SOUTHERN_COMPANY_DOMAIN,
                statistic_id=cost_statistic_id,
                unit_of_measurement=None,
            )
            usage_metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"{account.name} usage",
                source=SOUTHERN_COMPANY_DOMAIN,
                statistic_id=usage_statistic_id,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            )

            async_add_external_statistics(self.hass, cost_metadata, cost_statistics)
            async_add_external_statistics(self.hass, usage_metadata, usage_statistics)
