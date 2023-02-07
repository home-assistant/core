"""Support for Southern Company sensors."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging

import pytz
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN as SOUTHERN_COMPANY_DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:currency-usd"
SCAN_INTERVAL = timedelta(minutes=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
PARALLEL_UPDATES = 0


SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="month_cost",
        name="Monthly cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="month_cons",
        name="Monthly net consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Southern Company sensor."""

    southern_company_connection = hass.data[SOUTHERN_COMPANY_DOMAIN][entry.entry_id]

    # entity_registry = async_get_entity_reg(hass)
    # device_registry = async_get_dev_reg(hass)

    coordinator = SouthernCompanyCoordinator(hass, southern_company_connection)
    entities: list[SouthernCompanySensor] = []
    await southern_company_connection.get_jwt()
    for account in await southern_company_connection.get_accounts():
        for sensor in SENSORS:
            entities.append(SouthernCompanySensor(account, coordinator, sensor))

        # migrate
        # old_id = home.info["viewer"]["home"]["meteringPointData"]["consumptionEan"]
        # if old_id is None:
        #     continue

        # # migrate to new device ids
        # old_entity_id = entity_registry.async_get_entity_id(
        #     "sensor", SOUTHERN_COMPANY_DOMAIN, old_id
        # )
        # if old_entity_id is not None:
        #     entity_registry.async_update_entity(
        #         old_entity_id, new_unique_id=home.home_id
        #     )

        # # migrate to new device ids
        # device_entry = device_registry.async_get_device(
        #     {(SOUTHERN_COMPANY_DOMAIN, old_id)}
        # )
        # if device_entry and entry.entry_id in device_entry.config_entries:
        #     device_registry.async_update_device(
        #         device_entry.id,
        #         new_identifiers={(SOUTHERN_COMPANY_DOMAIN, home.home_id)},
        #     )

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
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._account = account

        self._attr_unique_id = f"{self._account.number}_{self.entity_description.key}"
        self._attr_name = f"{entity_description.name}"

        self._device_name = self._account.number


class SouthernCompanyCoordinator(DataUpdateCoordinator[None]):
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

    async def _async_update_data(self) -> None:
        """Update data via API."""
        await self._insert_statistics()

    async def _insert_statistics(self) -> None:
        """Insert Southern Company statistics."""
        for account in await self._southern_company_connection.get_accounts():
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
                    # Needs exception
                    pass

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
                    # Needs exception
                    pass

                from_time = hourly_data[0].time
                if from_time is None:
                    continue
                # This should be handled in the api
                time_zone = pytz.timezone("America/New_York")
                from_time = time_zone.localize(from_time)

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
                time_zone = pytz.timezone("America/New_York")
                from_time = time_zone.localize(from_time)

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
