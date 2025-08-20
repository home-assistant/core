"""Amber Electric Service class."""

from amberelectric.models.channel import ChannelType
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util.json import JsonValueType

from .const import (
    ATTR_CHANNEL_TYPE,
    CONTROLLED_LOAD_CHANNEL,
    DOMAIN,
    FEED_IN_CHANNEL,
    GENERAL_CHANNEL,
    SERVICE_GET_FORECASTS,
)
from .coordinator import AmberConfigEntry
from .helpers import format_cents_to_dollars, normalize_descriptor

GET_FORECASTS_SCHEMA = vol.Schema(
    {
        ATTR_CONFIG_ENTRY_ID: ConfigEntrySelector({"integration": DOMAIN}),
        ATTR_CHANNEL_TYPE: vol.In(
            [GENERAL_CHANNEL, CONTROLLED_LOAD_CHANNEL, FEED_IN_CHANNEL]
        ),
    }
)


def async_get_entry(hass: HomeAssistant, config_entry_id: str) -> AmberConfigEntry:
    """Get the Amber config entry."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": config_entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return entry


def get_forecasts(channel_type: str, data: dict) -> list[JsonValueType]:
    """Return an array of forecasts."""
    results: list[JsonValueType] = []

    if channel_type not in data["forecasts"]:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="channel_not_found",
            translation_placeholders={"channel_type": channel_type},
        )

    intervals = data["forecasts"][channel_type]

    for interval in intervals:
        datum = {}
        datum["duration"] = interval.duration
        datum["date"] = interval.var_date.isoformat()
        datum["nem_date"] = interval.nem_time.isoformat()
        datum["per_kwh"] = format_cents_to_dollars(interval.per_kwh)
        if interval.channel_type == ChannelType.FEEDIN:
            datum["per_kwh"] = datum["per_kwh"] * -1
        datum["spot_per_kwh"] = format_cents_to_dollars(interval.spot_per_kwh)
        datum["start_time"] = interval.start_time.isoformat()
        datum["end_time"] = interval.end_time.isoformat()
        datum["renewables"] = round(interval.renewables)
        datum["spike_status"] = interval.spike_status.value
        datum["descriptor"] = normalize_descriptor(interval.descriptor)

        if interval.range is not None:
            datum["range_min"] = format_cents_to_dollars(interval.range.min)
            datum["range_max"] = format_cents_to_dollars(interval.range.max)

        if interval.advanced_price is not None:
            multiplier = -1 if interval.channel_type == ChannelType.FEEDIN else 1
            datum["advanced_price_low"] = multiplier * format_cents_to_dollars(
                interval.advanced_price.low
            )
            datum["advanced_price_predicted"] = multiplier * format_cents_to_dollars(
                interval.advanced_price.predicted
            )
            datum["advanced_price_high"] = multiplier * format_cents_to_dollars(
                interval.advanced_price.high
            )

        results.append(datum)

    return results


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Amber integration."""

    async def handle_get_forecasts(call: ServiceCall) -> ServiceResponse:
        channel_type = call.data[ATTR_CHANNEL_TYPE]
        entry = async_get_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        coordinator = entry.runtime_data
        forecasts = get_forecasts(channel_type, coordinator.data)
        return {"forecasts": forecasts}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_FORECASTS,
        handle_get_forecasts,
        GET_FORECASTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
