"""Amber Electric Sensor definitions."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import amberelectric
from amberelectric.api import amber_api
from amberelectric.model.channel import ChannelType
from amberelectric.model.interval import SpikeStatus

from homeassistant.components.sensor import DEVICE_CLASS_MONETARY, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from .const import CONF_API_TOKEN, CONF_SITE_ID, LOGGER
from .coordinator import AmberDataService

ATTRIBUTION = "Data provided by Amber Electric"


def friendly_channel_type(channel_type: str) -> str:
    """Return a human readable version of the channel type."""
    if channel_type == ChannelType.CONTROLLED_LOAD:
        return "Controlled Load"
    if channel_type == ChannelType.FEED_IN:
        return "Feed In"
    return "General"


class AmberPriceSensor(CoordinatorEntity, SensorEntity):
    """Amber Price Sensor."""

    def __init__(
        self,
        platform_name: str,
        site_id: str,
        channel_type: str,
        data_service: AmberDataService,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self._site_id = site_id
        self._channel_type = channel_type
        self._platform_name = platform_name
        self._data_service = data_service

    @property
    def name(self) -> str | None:
        """Return the friendly name of the sensor."""
        return (
            self._platform_name
            + " - "
            + friendly_channel_type(self._channel_type)
            + " "
            + "Price"
        )

    @property
    def unique_id(self) -> str | None:
        """Return a unique id for each sensors."""
        return slugify(
            self._site_id + " " + friendly_channel_type(self._channel_type) + " Price"
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if self._channel_type == ChannelType.FEED_IN:
            return "mdi:solar-power"
        if self._channel_type == ChannelType.CONTROLLED_LOAD:
            return "mdi:clock-outline"
        return "mdi:transmission-tower"

    @property
    def unit_of_measurement(self):
        """Return the sensors unit of measurement."""
        return "¢/kWh"

    @property
    def native_value(self) -> str | None:
        """Return the current price in c/kWh."""
        channel = self._data_service.current_prices.get(self._channel_type)
        if channel:
            if self._channel_type == ChannelType.FEED_IN:
                return round(channel.per_kwh, 0) * -1
            return round(channel.per_kwh, 0)
        return None

    @property
    def device_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information about the price."""
        meta = self._data_service.current_prices.get(self._channel_type)
        data = {}
        if meta is not None:
            data["duration"] = meta.duration
            data["date"] = meta.date.isoformat()
            data["per_kwh"] = round(meta.per_kwh)
            if self._channel_type == ChannelType.FEED_IN:
                data["per_kwh"] = data["per_kwh"] * -1
            data["nem_date"] = meta.nem_time.isoformat()
            data["spot_per_kwh"] = round(meta.spot_per_kwh)
            data["start_time"] = meta.start_time.isoformat()
            data["end_time"] = meta.end_time.isoformat()
            data["renewables"] = round(meta.renewables)
            data["estimate"] = meta.estimate
            data["spike_status"] = meta.spike_status.value
            data["channel_type"] = meta.channel_type.value

            if meta.range is not None:
                data["range_min"] = meta.range.min
                data["range_max"] = meta.range.max

        data[ATTR_ATTRIBUTION] = ATTRIBUTION
        return data


class AmberEnergyPriceSensor(CoordinatorEntity, SensorEntity):
    """Amber Price Sensor that can be used in the Energy Dashboard."""

    def __init__(
        self,
        platform_name: str,
        site_id: str,
        channel_type: str,
        data_service: AmberDataService,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self._site_id = site_id
        self._channel_type = channel_type
        self._platform_name = platform_name
        self._data_service = data_service

    @property
    def name(self) -> str | None:
        """Return the friendly name of the sensor."""
        return (
            self._platform_name
            + " - "
            + friendly_channel_type(self._channel_type)
            + " "
            + "Energy Price"
        )

    @property
    def unique_id(self) -> str | None:
        """Return a unique id for each sensors."""
        return slugify(
            self._site_id
            + " "
            + friendly_channel_type(self._channel_type)
            + " Energy Price"
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if self._channel_type == ChannelType.FEED_IN:
            return "mdi:solar-power"
        if self._channel_type == ChannelType.CONTROLLED_LOAD:
            return "mdi:clock-outline"
        return "mdi:transmission-tower"

    @property
    def device_class(self) -> str | None:
        """Return the sensors device class."""
        return DEVICE_CLASS_MONETARY

    @property
    def native_unit_of_measurement(self):
        """Return the sensors currency."""
        return "AUD"

    @property
    def native_value(self) -> str | None:
        """Return the current price in $/kWh."""
        channel = self._data_service.current_prices.get(self._channel_type)
        if channel:
            if self._channel_type == ChannelType.FEED_IN:
                return round(channel.per_kwh, 0) / 100 * -1
            return round(channel.per_kwh, 0) / 100
        return None


class AmberRenewablesSensor(CoordinatorEntity, SensorEntity):
    """Amber Renewable Percentage Sensor."""

    def __init__(
        self,
        platform_name: str,
        site_id: str,
        data_service: AmberDataService,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self._site_id = site_id
        self._platform_name = platform_name
        self._data_service = data_service

    @property
    def name(self) -> str | None:
        """Return the friendly name of the sensor."""
        return self._platform_name + " - Renewables"

    @property
    def unique_id(self) -> str | None:
        """Return a unique id for each sensors."""
        return slugify(self._site_id + " Renewables")

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:solar-power"

    @property
    def unit_of_measurement(self):
        """Return the sensors unit of measurement."""
        return "%"

    @property
    def native_value(self) -> str | None:
        """Return the percentage of renewable energy currently in the grid."""
        channel = self._data_service.current_prices.get(ChannelType.GENERAL)
        if channel:
            return round(channel.renewables, 0)
        return None

    @property
    def device_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information about the sensor."""
        data = {}
        data[ATTR_ATTRIBUTION] = ATTRIBUTION
        return data


class AmberForecastSensor(CoordinatorEntity, SensorEntity):
    """Amber Forecast Sensor."""

    def __init__(
        self,
        platform_name: str,
        site_id: str,
        channel_type: ChannelType,
        data_service: AmberDataService,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self._site_id = site_id
        self._channel_type = channel_type
        self._platform_name = platform_name
        self._data_service = data_service

    @property
    def name(self) -> str | None:
        """Return the friendly name of the sensor."""
        return (
            self._platform_name
            + " - "
            + friendly_channel_type(self._channel_type)
            + " "
            + "Forecast"
        )

    @property
    def unique_id(self) -> str | None:
        """Return a unique id for each sensors."""
        return slugify(
            self._site_id
            + " "
            + friendly_channel_type(self._channel_type)
            + " Forecast"
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if self._channel_type == ChannelType.FEED_IN:
            return "mdi:solar-power"
        if self._channel_type == ChannelType.CONTROLLED_LOAD:
            return "mdi:clock-outline"
        return "mdi:transmission-tower"

    @property
    def unit_of_measurement(self):
        """Return the sensors unit of measurement."""
        return "¢/kWh"

    @property
    def native_value(self) -> str | None:
        """Return the current price in c/kWh."""
        forecasts = self._data_service.forecasts.get(self._channel_type)
        if forecasts and len(forecasts) > 0:
            if self._channel_type == ChannelType.FEED_IN:
                return round(forecasts[0].per_kwh, 0) * -1
            return round(forecasts[0].per_kwh, 0)
        return None

    @property
    def device_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information about the forecast."""
        forecasts = self._data_service.forecasts.get(self._channel_type)
        data: dict[str, Any] = {}
        data["forecasts"] = []
        data["channel_type"] = self._channel_type.value

        if forecasts is not None:
            for meta in forecasts:
                datum = {}
                datum["duration"] = meta.duration
                datum["date"] = meta.date.isoformat()
                datum["nem_date"] = meta.nem_time.isoformat()
                datum["per_kwh"] = round(meta.per_kwh)
                if self._channel_type == ChannelType.FEED_IN:
                    datum["per_kwh"] = datum["per_kwh"] * -1
                datum["spot_per_kwh"] = round(meta.spot_per_kwh)
                datum["start_time"] = meta.start_time.isoformat()
                datum["end_time"] = meta.end_time.isoformat()
                datum["renewables"] = round(meta.renewables)
                datum["spike_status"] = meta.spike_status.value

                if meta.range is not None:
                    datum["range_min"] = meta.range.min
                    datum["range_max"] = meta.range.max

                data["forecasts"].append(datum)

        data[ATTR_ATTRIBUTION] = ATTRIBUTION
        return data


class AmberPriceSpikeSensor(CoordinatorEntity, SensorEntity):
    """Amber Price Spike Sensor."""

    def __init__(
        self,
        platform_name: str,
        site_id: str,
        data_service: AmberDataService,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self._platform_name = platform_name
        self._site_id = site_id
        self._data_service = data_service

    @property
    def name(self) -> str | None:
        """Return the friendly name of the sensor."""
        return self._platform_name + " - Price Spike"

    @property
    def unique_id(self) -> str | None:
        """Return a unique id for each sensors."""
        return slugify(self._site_id + " Price Spike")

    @property
    def native_value(self) -> bool:
        """Return the current price in c/kWh."""
        channel = self._data_service.current_prices.get(ChannelType.GENERAL)
        if channel is not None:
            return channel.spike_status == SpikeStatus.SPIKE
        return False

    @property
    def icon(self):
        """Return the icon of the sensor."""
        channel = self._data_service.current_prices.get(ChannelType.GENERAL)
        if channel is not None:
            if channel.spike_status == SpikeStatus.SPIKE:
                return "mdi:power-plug-off"
            if channel.spike_status == SpikeStatus.POTENTIAL:
                return "mdi:power-plug-outline"
        return "mdi:power-plug"

    @property
    def device_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information about the sensor."""
        data = {}
        channel = self._data_service.current_prices.get(ChannelType.GENERAL)
        if channel is not None:
            data["spike_status"] = channel.spike_status.value
        data[ATTR_ATTRIBUTION] = ATTRIBUTION
        return data


class AmberFactory:
    """Create all the Amber sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        platform_name: str,
        site_id: str,
        api: amber_api.AmberApi,
    ) -> None:
        """Initialise the factory."""
        self._platform_name = platform_name
        self.data_service = AmberDataService(hass, api, site_id)
        self._site_id = site_id

    def build_sensors(self) -> list[SensorEntity]:
        """Build and return all of the Amber Sensors."""
        sensors: list[SensorEntity] = []

        if (
            self.data_service.site is not None
            and self.data_service.coordinator is not None
        ):
            sensors.append(
                AmberPriceSensor(
                    self._platform_name,
                    self._site_id,
                    ChannelType.GENERAL,
                    self.data_service,
                    self.data_service.coordinator,
                )
            )

            sensors.append(
                AmberEnergyPriceSensor(
                    self._platform_name,
                    self._site_id,
                    ChannelType.GENERAL,
                    self.data_service,
                    self.data_service.coordinator,
                )
            )

            sensors.append(
                AmberForecastSensor(
                    self._platform_name,
                    self._site_id,
                    ChannelType.GENERAL,
                    self.data_service,
                    self.data_service.coordinator,
                )
            )

            if (
                len(
                    list(
                        filter(
                            lambda channel: channel.type == ChannelType.FEED_IN,
                            self.data_service.site.channels,
                        )
                    )
                )
                > 0
            ):
                sensors.append(
                    AmberPriceSensor(
                        self._platform_name,
                        self._site_id,
                        ChannelType.FEED_IN,
                        self.data_service,
                        self.data_service.coordinator,
                    )
                )

                sensors.append(
                    AmberEnergyPriceSensor(
                        self._platform_name,
                        self._site_id,
                        ChannelType.FEED_IN,
                        self.data_service,
                        self.data_service.coordinator,
                    )
                )

                sensors.append(
                    AmberForecastSensor(
                        self._platform_name,
                        self._site_id,
                        ChannelType.FEED_IN,
                        self.data_service,
                        self.data_service.coordinator,
                    )
                )

            if (
                len(
                    list(
                        filter(
                            lambda channel: channel.type == ChannelType.CONTROLLED_LOAD,
                            self.data_service.site.channels,
                        )
                    )
                )
                > 0
            ):
                sensors.append(
                    AmberPriceSensor(
                        self._platform_name,
                        self._site_id,
                        ChannelType.CONTROLLED_LOAD,
                        self.data_service,
                        self.data_service.coordinator,
                    )
                )

                sensors.append(
                    AmberEnergyPriceSensor(
                        self._platform_name,
                        self._site_id,
                        ChannelType.CONTROLLED_LOAD,
                        self.data_service,
                        self.data_service.coordinator,
                    )
                )

                sensors.append(
                    AmberForecastSensor(
                        self._platform_name,
                        self._site_id,
                        ChannelType.CONTROLLED_LOAD,
                        self.data_service,
                        self.data_service.coordinator,
                    )
                )

            sensors.append(
                AmberRenewablesSensor(
                    self._platform_name,
                    self._site_id,
                    self.data_service,
                    self.data_service.coordinator,
                )
            )

            sensors.append(
                AmberPriceSpikeSensor(
                    self._platform_name,
                    self._site_id,
                    self.data_service,
                    self.data_service.coordinator,
                )
            )

            LOGGER.debug("Adding %s sensors", str(len(sensors)))
        else:
            LOGGER.error("No site found!")
        return sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Amber integration."""
    configuration = amberelectric.Configuration(
        access_token=entry.data.get(CONF_API_TOKEN)
    )

    api_instance = amber_api.AmberApi.create(configuration)

    # Do a sites enquiry, and get all the channels...
    LOGGER.debug("Initializing AmberFactory")
    site_id = entry.data.get(CONF_SITE_ID)
    if site_id is not None:
        factory = AmberFactory(hass, entry.title, str(site_id), api_instance)
        LOGGER.debug("AmberFactory initialized. Setting up")
        factory.data_service.async_setup()
        LOGGER.debug("AmberFactory Setup. Trigging manual fetch")

        if (
            factory is not None
            and factory.data_service is not None
            and factory.data_service.coordinator is not None
        ):
            await factory.data_service.coordinator.async_refresh()
            LOGGER.debug("Fetch complete. Adding entities")
            async_add_entities(factory.build_sensors())
            LOGGER.debug("Entry setup complete")
        else:
            LOGGER.error("Data service is not set up!")
    else:
        LOGGER.error("Site ID is not defined!")
