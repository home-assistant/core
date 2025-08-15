"""Test the Amber Electric Sensors."""

import pytest

from homeassistant.core import HomeAssistant

from . import MockConfigEntry, setup_integration


@pytest.mark.usefixtures("mock_amber_client_general_channel")
async def test_general_price_sensor(
    hass: HomeAssistant, general_channel_config_entry: MockConfigEntry
) -> None:
    """Test the General Price sensor."""
    await setup_integration(hass, general_channel_config_entry)
    assert len(hass.states.async_all()) == 6
    price = hass.states.get("sensor.mock_title_general_price")
    assert price
    assert price.state == "0.09"
    attributes = price.attributes
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == 0.09
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


@pytest.mark.usefixtures("mock_amber_client_general_channel_with_range")
async def test_general_price_sensor_with_range(
    hass: HomeAssistant, general_channel_config_entry: MockConfigEntry
) -> None:
    """Test the General Price sensor with a range."""
    await setup_integration(hass, general_channel_config_entry)
    assert len(hass.states.async_all()) == 6
    price = hass.states.get("sensor.mock_title_general_price")
    assert price
    attributes = price.attributes
    assert attributes.get("range_min") == 0.07
    assert attributes.get("range_max") == 0.09


@pytest.mark.usefixtures("mock_amber_client_general_and_controlled_load")
async def test_general_and_controlled_load_price_sensor(
    hass: HomeAssistant,
    general_channel_and_controlled_load_config_entry: MockConfigEntry,
) -> None:
    """Test the Controlled Price sensor."""
    await setup_integration(hass, general_channel_and_controlled_load_config_entry)
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_controlled_load_price")
    assert price
    assert price.state == "0.04"
    attributes = price.attributes
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == 0.04
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 0.01
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "controlledLoad"
    assert attributes["attribution"] == "Data provided by Amber Electric"


@pytest.mark.usefixtures("mock_amber_client_general_and_feed_in")
async def test_general_and_feed_in_price_sensor(
    hass: HomeAssistant, general_channel_and_feed_in_config_entry: MockConfigEntry
) -> None:
    """Test the Feed In sensor."""
    await setup_integration(hass, general_channel_and_feed_in_config_entry)
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_feed_in_price")
    assert price
    assert price.state == "-0.01"
    attributes = price.attributes
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == -0.01
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 0.01
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "feedIn"
    assert attributes["attribution"] == "Data provided by Amber Electric"


@pytest.mark.usefixtures("mock_amber_client_general_channel")
async def test_general_forecast_sensor(
    hass: HomeAssistant, general_channel_config_entry: MockConfigEntry
) -> None:
    """Test the General Forecast sensor."""
    await setup_integration(hass, general_channel_config_entry)
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


@pytest.mark.usefixtures("mock_amber_client_general_channel_with_range")
async def test_general_forecast_sensor_with_range(
    hass: HomeAssistant, general_channel_config_entry: MockConfigEntry
) -> None:
    """Test the General Forecast sensor with a range."""
    await setup_integration(hass, general_channel_config_entry)
    assert len(hass.states.async_all()) == 6
    price = hass.states.get("sensor.mock_title_general_forecast")
    assert price
    attributes = price.attributes
    first_forecast = attributes["forecasts"][0]
    assert first_forecast.get("range_min") == 0.07
    assert first_forecast.get("range_max") == 0.09


@pytest.mark.usefixtures("mock_amber_client_general_and_controlled_load")
async def test_controlled_load_forecast_sensor(
    hass: HomeAssistant,
    general_channel_and_controlled_load_config_entry: MockConfigEntry,
) -> None:
    """Test the Controlled Load Forecast sensor."""
    await setup_integration(hass, general_channel_and_controlled_load_config_entry)
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_controlled_load_forecast")
    assert price
    assert price.state == "0.04"
    attributes = price.attributes
    assert attributes["channel_type"] == "controlledLoad"
    assert attributes["attribution"] == "Data provided by Amber Electric"

    first_forecast = attributes["forecasts"][0]
    assert first_forecast["duration"] == 30
    assert first_forecast["date"] == "2021-09-21"
    assert first_forecast["per_kwh"] == 0.04
    assert first_forecast["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["spot_per_kwh"] == 0.01
    assert first_forecast["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first_forecast["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["renewables"] == 50
    assert first_forecast["spike_status"] == "none"
    assert first_forecast["descriptor"] == "very_low"


@pytest.mark.usefixtures("mock_amber_client_general_and_feed_in")
async def test_feed_in_forecast_sensor(
    hass: HomeAssistant, general_channel_and_feed_in_config_entry: MockConfigEntry
) -> None:
    """Test the Feed In Forecast sensor."""
    await setup_integration(hass, general_channel_and_feed_in_config_entry)
    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_feed_in_forecast")
    assert price
    assert price.state == "-0.01"
    attributes = price.attributes
    assert attributes["channel_type"] == "feedIn"
    assert attributes["attribution"] == "Data provided by Amber Electric"

    first_forecast = attributes["forecasts"][0]
    assert first_forecast["duration"] == 30
    assert first_forecast["date"] == "2021-09-21"
    assert first_forecast["per_kwh"] == -0.01
    assert first_forecast["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["spot_per_kwh"] == 0.01
    assert first_forecast["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first_forecast["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["renewables"] == 50
    assert first_forecast["spike_status"] == "none"
    assert first_forecast["descriptor"] == "very_low"


@pytest.mark.usefixtures("mock_amber_client_general_channel")
async def test_renewable_sensor(
    hass: HomeAssistant, general_channel_config_entry: MockConfigEntry
) -> None:
    """Testing the creation of the Amber renewables sensor."""
    await setup_integration(hass, general_channel_config_entry)

    assert len(hass.states.async_all()) == 6
    sensor = hass.states.get("sensor.mock_title_renewables")
    assert sensor
    assert sensor.state == "51"


@pytest.mark.usefixtures("mock_amber_client_general_channel")
async def test_general_price_descriptor_descriptor_sensor(
    hass: HomeAssistant, general_channel_config_entry: MockConfigEntry
) -> None:
    """Test the General Price Descriptor sensor."""
    await setup_integration(hass, general_channel_config_entry)
    assert len(hass.states.async_all()) == 6
    price = hass.states.get("sensor.mock_title_general_price_descriptor")
    assert price
    assert price.state == "extremely_low"


@pytest.mark.usefixtures("mock_amber_client_general_and_controlled_load")
async def test_general_and_controlled_load_price_descriptor_sensor(
    hass: HomeAssistant,
    general_channel_and_controlled_load_config_entry: MockConfigEntry,
) -> None:
    """Test the Controlled Price Descriptor sensor."""
    await setup_integration(hass, general_channel_and_controlled_load_config_entry)

    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_controlled_load_price_descriptor")
    assert price
    assert price.state == "extremely_low"


@pytest.mark.usefixtures("mock_amber_client_general_and_feed_in")
async def test_general_and_feed_in_price_descriptor_sensor(
    hass: HomeAssistant, general_channel_and_feed_in_config_entry: MockConfigEntry
) -> None:
    """Test the Feed In Price Descriptor sensor."""
    await setup_integration(hass, general_channel_and_feed_in_config_entry)

    assert len(hass.states.async_all()) == 9
    price = hass.states.get("sensor.mock_title_feed_in_price_descriptor")
    assert price
    assert price.state == "extremely_low"
