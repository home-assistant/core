"""The kraken integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import KrakenData
from .const import (
    CONF_TRACKED_ASSET_PAIRS,
    DISPATCH_CONFIG_UPDATED,
    DOMAIN,
    KrakenResponse,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KrakenSensorEntityDescription(SensorEntityDescription):
    """Describes Kraken sensor entity."""

    value_fn: Callable[[DataUpdateCoordinator[KrakenResponse], str], float | int]


SENSOR_TYPES: tuple[KrakenSensorEntityDescription, ...] = (
    KrakenSensorEntityDescription(
        key="ask",
        translation_key="ask",
        value_fn=lambda x, y: x.data[y]["ask"][0],
    ),
    KrakenSensorEntityDescription(
        key="ask_volume",
        translation_key="ask_volume",
        value_fn=lambda x, y: x.data[y]["ask"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="bid",
        translation_key="bid",
        value_fn=lambda x, y: x.data[y]["bid"][0],
    ),
    KrakenSensorEntityDescription(
        key="bid_volume",
        translation_key="bid_volume",
        value_fn=lambda x, y: x.data[y]["bid"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="volume_today",
        translation_key="volume_today",
        value_fn=lambda x, y: x.data[y]["volume"][0],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="volume_last_24h",
        translation_key="volume_last_24h",
        value_fn=lambda x, y: x.data[y]["volume"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="volume_weighted_average_today",
        translation_key="volume_weighted_average_today",
        value_fn=lambda x, y: x.data[y]["volume_weighted_average"][0],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="volume_weighted_average_last_24h",
        translation_key="volume_weighted_average_last_24h",
        value_fn=lambda x, y: x.data[y]["volume_weighted_average"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="number_of_trades_today",
        translation_key="number_of_trades_today",
        value_fn=lambda x, y: x.data[y]["number_of_trades"][0],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="number_of_trades_last_24h",
        translation_key="number_of_trades_last_24h",
        value_fn=lambda x, y: x.data[y]["number_of_trades"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="last_trade_closed",
        translation_key="last_trade_closed",
        value_fn=lambda x, y: x.data[y]["last_trade_closed"][0],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="low_today",
        translation_key="low_today",
        value_fn=lambda x, y: x.data[y]["low"][0],
    ),
    KrakenSensorEntityDescription(
        key="low_last_24h",
        translation_key="low_last_24h",
        value_fn=lambda x, y: x.data[y]["low"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="high_today",
        translation_key="high_today",
        value_fn=lambda x, y: x.data[y]["high"][0],
    ),
    KrakenSensorEntityDescription(
        key="high_last_24h",
        translation_key="high_last_24h",
        value_fn=lambda x, y: x.data[y]["high"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="opening_price_today",
        translation_key="opening_price_today",
        value_fn=lambda x, y: x.data[y]["opening_price"],
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add kraken entities from a config_entry."""

    def _async_add_kraken_sensors(tracked_asset_pairs: list[str]) -> None:
        entities = []
        for tracked_asset_pair in tracked_asset_pairs:
            entities.extend(
                [
                    KrakenSensor(
                        hass.data[DOMAIN],
                        tracked_asset_pair,
                        description,
                    )
                    for description in SENSOR_TYPES
                ]
            )
        async_add_entities(entities, True)

    _async_add_kraken_sensors(config_entry.options[CONF_TRACKED_ASSET_PAIRS])

    @callback
    def async_update_sensors(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Add or remove sensors for configured tracked asset pairs."""
        dev_reg = dr.async_get(hass)

        existing_devices = {
            device.name: device.id
            for device in dr.async_entries_for_config_entry(
                dev_reg, config_entry.entry_id
            )
        }

        asset_pairs_to_add = []
        for tracked_asset_pair in config_entry.options[CONF_TRACKED_ASSET_PAIRS]:
            # Only create new devices
            if (
                device_name := create_device_name(tracked_asset_pair)
            ) in existing_devices:
                existing_devices.pop(device_name)
            else:
                asset_pairs_to_add.append(tracked_asset_pair)
        _async_add_kraken_sensors(asset_pairs_to_add)

        # Remove devices for asset pairs which are no longer tracked
        for device_id in existing_devices.values():
            dev_reg.async_remove_device(device_id)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            DISPATCH_CONFIG_UPDATED,
            async_update_sensors,
        )
    )


class KrakenSensor(
    CoordinatorEntity[DataUpdateCoordinator[KrakenResponse | None]], SensorEntity
):
    """Define a Kraken sensor."""

    entity_description: KrakenSensorEntityDescription

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        kraken_data: KrakenData,
        tracked_asset_pair: str,
        description: KrakenSensorEntityDescription,
    ) -> None:
        """Initialize."""
        assert kraken_data.coordinator is not None
        super().__init__(kraken_data.coordinator)
        self.entity_description = description
        self.tracked_asset_pair_wsname = kraken_data.tradable_asset_pairs[
            tracked_asset_pair
        ]
        self._target_asset = tracked_asset_pair.split("/")[1]
        if "number_of" not in description.key:
            self._attr_native_unit_of_measurement = self._target_asset
        self._device_name = create_device_name(tracked_asset_pair)
        self._attr_unique_id = "_".join(
            [
                tracked_asset_pair.split("/")[0],
                tracked_asset_pair.split("/")[1],
                description.key,
            ]
        ).lower()
        self._received_data_at_least_once = False
        self._available = True

        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.kraken.com/",
            entry_type=dr.DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, "_".join(self._device_name.split(" ")))},
            manufacturer="Kraken.com",
            name=self._device_name,
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._update_internal_state()

    def _handle_coordinator_update(self) -> None:
        self._update_internal_state()
        super()._handle_coordinator_update()

    def _update_internal_state(self) -> None:
        if not self.coordinator.data:
            return
        try:
            self._attr_native_value = self.entity_description.value_fn(
                self.coordinator,  # type: ignore[arg-type]
                self.tracked_asset_pair_wsname,
            )
            self._received_data_at_least_once = True
        except KeyError:
            if self._received_data_at_least_once:
                if self._available:
                    _LOGGER.warning(
                        "Asset Pair %s is no longer available",
                        self._device_name,
                    )
                    self._available = False

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self._target_asset == "EUR":
            return "mdi:currency-eur"
        if self._target_asset == "GBP":
            return "mdi:currency-gbp"
        if self._target_asset == "USD":
            return "mdi:currency-usd"
        if self._target_asset == "JPY":
            return "mdi:currency-jpy"
        if self._target_asset == "XBT":
            return "mdi:currency-btc"
        return "mdi:cash"

    @property
    def available(self) -> bool:
        """Could the api be accessed during the last update call."""
        return self._available and self.coordinator.last_update_success


def create_device_name(tracked_asset_pair: str) -> str:
    """Create the device name for a given tracked asset pair."""
    return f"{tracked_asset_pair.split('/')[0]} {tracked_asset_pair.split('/')[1]}"
