"""Test the Amber Electric Sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import Mock, patch

from amberelectric.models.current_interval import CurrentInterval
from amberelectric.models.interval import Interval
from amberelectric.models.range import Range
import pytest

from homeassistant.components.amberelectric.const import (
    CONF_SITE_ID,
    CONF_SITE_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .helpers import (
    CONTROLLED_LOAD_CHANNEL,
    FEED_IN_CHANNEL,
    GENERAL_AND_CONTROLLED_SITE_ID,
    GENERAL_AND_FEED_IN_SITE_ID,
    GENERAL_CHANNEL,
    GENERAL_ONLY_SITE_ID,
)

from tests.common import MockConfigEntry

MOCK_API_TOKEN = "psk_0000000000000000"


@pytest.fixture
async def setup_general(hass: HomeAssistant) -> AsyncGenerator[Mock]:
    """Set up general channel."""
    MockConfigEntry(
        domain="amberelectric",
        data={
            CONF_SITE_NAME: "mock_title",
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_SITE_ID: GENERAL_ONLY_SITE_ID,
        },
    ).add_to_hass(hass)

    instance = Mock()
    with patch(
        "amberelectric.AmberApi",
        return_value=instance,
    ) as mock_update:
        instance.get_current_prices = Mock(return_value=GENERAL_CHANNEL)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_general_and_controlled_load(
    hass: HomeAssistant,
) -> AsyncGenerator[Mock]:
    """Set up general channel and controller load channel."""
    MockConfigEntry(
        domain="amberelectric",
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_SITE_ID: GENERAL_AND_CONTROLLED_SITE_ID,
        },
    ).add_to_hass(hass)

    instance = Mock()
    with patch(
        "amberelectric.AmberApi",
        return_value=instance,
    ) as mock_update:
        instance.get_current_prices = Mock(
            return_value=GENERAL_CHANNEL + CONTROLLED_LOAD_CHANNEL
        )
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_general_and_feed_in(hass: HomeAssistant) -> AsyncGenerator[Mock]:
    """Set up general channel and feed in channel."""
    MockConfigEntry(
        domain="amberelectric",
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_SITE_ID: GENERAL_AND_FEED_IN_SITE_ID,
        },
    ).add_to_hass(hass)

    instance = Mock()
    with patch(
        "amberelectric.AmberApi",
        return_value=instance,
    ) as mock_update:
        instance.get_current_prices = Mock(
            return_value=GENERAL_CHANNEL + FEED_IN_CHANNEL
        )
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


async def test_general_price_sensor(hass: HomeAssistant, setup_general: Mock) -> None:
    """Test the General Price sensor."""
    assert len(hass.states.async_all()) == 6
    price = hass.states.get("sensor.mock_title_general_price")
    assert price
    assert price.state == "0.08"
    attributes = price.attributes
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == 0.08
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 0.01
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "general"
    assert attributes["attribution"] == "Data provided by Amber Electric"
    assert attributes.get("range_min") is None
    assert attributes.get("range_max") is None

    with_range: list[CurrentInterval] = GENERAL_CHANNEL
    with_range[0].actual_instance.range = Range(min=7.8, max=12.4)

    setup_general.get_current_price.return_value = with_range
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    price = hass.states.get("sensor.mock_title_general_price")
    assert price
    attributes = price.attributes
    assert attributes.get("range_min") == 0.08
    assert attributes.get("range_max") == 0.12


@pytest.mark.usefixtures("setup_general_and_controlled_load")
async def test_general_and_controlled_load_price_sensor(hass: HomeAssistant) -> None:
    """Test the Controlled Price sensor."""
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_controlled_load_price")
    assert price
    assert price.state == "0.08"
    attributes = price.attributes
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == 0.08
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 0.01
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "controlledLoad"
    assert attributes["attribution"] == "Data provided by Amber Electric"


@pytest.mark.usefixtures("setup_general_and_feed_in")
async def test_general_and_feed_in_price_sensor(hass: HomeAssistant) -> None:
    """Test the Feed In sensor."""
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_feed_in_price")
    assert price
    assert price.state == "-0.08"
    attributes = price.attributes
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == -0.08
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 0.01
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "feedIn"
    assert attributes["attribution"] == "Data provided by Amber Electric"


async def test_general_forecast_sensor(
    hass: HomeAssistant, setup_general: Mock
) -> None:
    """Test the General Forecast sensor."""
    assert len(hass.states.async_all()) == 6
    price = hass.states.get("sensor.mock_title_general_forecast")
    assert price
    assert price.state == "0.09"
    attributes = price.attributes
    assert attributes["channel_type"] == "general"
    assert attributes["attribution"] == "Data provided by Amber Electric"

    first_forecast = attributes["forecasts"][0]
    assert first_forecast["duration"] == 30
    assert first_forecast["date"] == "2021-09-21"
    assert first_forecast["per_kwh"] == 0.09
    assert first_forecast["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["spot_per_kwh"] == 0.01
    assert first_forecast["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first_forecast["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["renewables"] == 50
    assert first_forecast["spike_status"] == "none"
    assert first_forecast["descriptor"] == "very_low"

    assert first_forecast.get("range_min") is None
    assert first_forecast.get("range_max") is None

    with_range: list[Interval] = GENERAL_CHANNEL
    with_range[1].actual_instance.range = Range(min=7.8, max=12.4)

    setup_general.get_current_price.return_value = with_range
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    price = hass.states.get("sensor.mock_title_general_forecast")
    assert price
    attributes = price.attributes
    first_forecast = attributes["forecasts"][0]
    assert first_forecast.get("range_min") == 0.08
    assert first_forecast.get("range_max") == 0.12


@pytest.mark.usefixtures("setup_general_and_controlled_load")
async def test_controlled_load_forecast_sensor(hass: HomeAssistant) -> None:
    """Test the Controlled Load Forecast sensor."""
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_controlled_load_forecast")
    assert price
    assert price.state == "0.09"
    attributes = price.attributes
    assert attributes["channel_type"] == "controlledLoad"
    assert attributes["attribution"] == "Data provided by Amber Electric"

    first_forecast = attributes["forecasts"][0]
    assert first_forecast["duration"] == 30
    assert first_forecast["date"] == "2021-09-21"
    assert first_forecast["per_kwh"] == 0.09
    assert first_forecast["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["spot_per_kwh"] == 0.01
    assert first_forecast["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first_forecast["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["renewables"] == 50
    assert first_forecast["spike_status"] == "none"
    assert first_forecast["descriptor"] == "very_low"


@pytest.mark.usefixtures("setup_general_and_feed_in")
async def test_feed_in_forecast_sensor(hass: HomeAssistant) -> None:
    """Test the Feed In Forecast sensor."""
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_feed_in_forecast")
    assert price
    assert price.state == "-0.09"
    attributes = price.attributes
    assert attributes["channel_type"] == "feedIn"
    assert attributes["attribution"] == "Data provided by Amber Electric"

    first_forecast = attributes["forecasts"][0]
    assert first_forecast["duration"] == 30
    assert first_forecast["date"] == "2021-09-21"
    assert first_forecast["per_kwh"] == -0.09
    assert first_forecast["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["spot_per_kwh"] == 0.01
    assert first_forecast["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first_forecast["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["renewables"] == 50
    assert first_forecast["spike_status"] == "none"
    assert first_forecast["descriptor"] == "very_low"


@pytest.mark.usefixtures("setup_general")
def test_renewable_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber renewables sensor."""
    assert len(hass.states.async_all()) == 6
    sensor = hass.states.get("sensor.mock_title_renewables")
    assert sensor
    assert sensor.state == "51"


@pytest.mark.usefixtures("setup_general")
def test_general_price_descriptor_descriptor_sensor(hass: HomeAssistant) -> None:
    """Test the General Price Descriptor sensor."""
    assert len(hass.states.async_all()) == 6
    price = hass.states.get("sensor.mock_title_general_price_descriptor")
    assert price
    assert price.state == "extremely_low"


@pytest.mark.usefixtures("setup_general_and_controlled_load")
def test_general_and_controlled_load_price_descriptor_sensor(
    hass: HomeAssistant,
) -> None:
    """Test the Controlled Price Descriptor sensor."""
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_controlled_load_price_descriptor")
    assert price
    assert price.state == "extremely_low"


@pytest.mark.usefixtures("setup_general_and_feed_in")
def test_general_and_feed_in_price_descriptor_sensor(hass: HomeAssistant) -> None:
    """Test the Feed In Price Descriptor sensor."""
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_feed_in_price_descriptor")
    assert price
    assert price.state == "extremely_low"
