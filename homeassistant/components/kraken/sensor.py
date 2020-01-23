"""The kraken integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KrakenData
from .const import (
    CONF_TRACKED_ASSET_PAIRS,
    DISPATCH_CONFIG_UPDATED,
    DOMAIN,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add kraken entities from a config_entry."""

    @callback
    async def async_add_sensors(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        for tracked_asset_pair in config_entry.options[CONF_TRACKED_ASSET_PAIRS]:
            sensors = []
            for sensor_type in SENSOR_TYPES:
                # Only add sensor if it is not registered already
                state = hass.states.get(
                    f"sensor.{get_unique_id(tracked_asset_pair, sensor_type)}"
                )
                if state is None:
                    sensors.append(
                        KrakenSensor(
                            hass.data[DOMAIN],
                            tracked_asset_pair,
                            sensor_type,
                        )
                    )
            async_add_entities(sensors, True)

    await async_add_sensors(hass, config_entry)

    async_dispatcher_connect(
        hass,
        DISPATCH_CONFIG_UPDATED,
        async_add_sensors,
    )


class KrakenSensor(CoordinatorEntity):
    """Define a Kraken sensor."""

    def __init__(
        self,
        kraken_data: KrakenData,
        tracked_asset_pair: str,
        sensor_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(kraken_data.coordinator)
        self.tracked_asset_pair_wsname = kraken_data.tradable_asset_pairs[
            tracked_asset_pair
        ]
        self._source_asset = tracked_asset_pair.split("/")[0]
        self._target_asset = tracked_asset_pair.split("/")[1]
        self._sensor_type = sensor_type
        self._unit_of_measurement = self._target_asset
        self._device_name = f"{self._source_asset} {self._target_asset}"
        self._name = get_unique_id(tracked_asset_pair, self._sensor_type)
        self._initialized = False
        self._available = True

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Set unique_id for sensor."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        try:
            state = self._try_get_state()
            self._initialized = True  # Received data at least one time.
            return state
        except TypeError:
            if self._initialized:
                if self._available:
                    _LOGGER.warning(
                        "Asset Pair %s is no longer available",
                        self._device_name,
                    )
                    self._available = False

    def _try_get_state(self) -> str:
        """Try to get the state or return a TypeError."""
        if self._sensor_type == "last_trade_closed":
            return self.coordinator.data[self.tracked_asset_pair_wsname][
                "last_trade_closed"
            ][0]
        if self._sensor_type == "ask":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["ask"][0]
        if self._sensor_type == "ask_volume":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["ask"][1]
        if self._sensor_type == "bid":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["bid"][0]
        if self._sensor_type == "bid_volume":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["bid"][1]
        if self._sensor_type == "volume_today":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["volume"][0]
        if self._sensor_type == "volume_last_24h":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["volume"][1]
        if self._sensor_type == "volume_weighted_average_today":
            return self.coordinator.data[self.tracked_asset_pair_wsname][
                "volume_weighted_average"
            ][0]
        if self._sensor_type == "volume_weighted_average_last_24h":
            return self.coordinator.data[self.tracked_asset_pair_wsname][
                "volume_weighted_average"
            ][1]
        if self._sensor_type == "number_of_trades_today":
            return self.coordinator.data[self.tracked_asset_pair_wsname][
                "number_of_trades"
            ][0]
        if self._sensor_type == "number_of_trades_last_24h":
            return self.coordinator.data[self.tracked_asset_pair_wsname][
                "number_of_trades"
            ][1]
        if self._sensor_type == "low_today":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["low"][0]
        if self._sensor_type == "low_last_24h":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["low"][1]
        if self._sensor_type == "high_today":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["high"][0]
        if self._sensor_type == "high_last_24h":
            return self.coordinator.data[self.tracked_asset_pair_wsname]["high"][1]
        if self._sensor_type == "opening_price_today":
            return self.coordinator.data[self.tracked_asset_pair_wsname][
                "opening_price"
            ]

    @property
    def icon(self):
        """Return the icon."""
        if self._name.split("_")[1][-3:] == "EUR":
            return "mdi:currency-eur"
        if self._name.split("_")[1][-3:] == "USD":
            return "mdi:currency-usd"
        if self._name.split("_")[1][-3:] == "XBT":
            return "mdi:currency-btc"
        return "mdi:currency-usd-circle"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if "number_of" not in self._sensor_type:
            return self._unit_of_measurement

    @property
    def available(self):
        """Could the api be accessed during the last update call."""
        if self._available:
            return self.coordinator.last_update_success
        return self._available

    @property
    def device_info(self) -> dict:
        """Return a device description for device registry."""

        return {
            "identifiers": {(DOMAIN, self._source_asset, self._target_asset)},
            "name": self._device_name,
            "manufacturer": "Kraken.com",
            "entry_type": "service",
        }


def get_unique_id(tracked_asset_pair: str, sensor_type: str) -> str:
    """Get the unique id for a sensor given the asset pair and sensor type."""
    return "_".join(
        [
            tracked_asset_pair.split("/")[0],
            tracked_asset_pair.split("/")[1],
            sensor_type,
        ]
    )
