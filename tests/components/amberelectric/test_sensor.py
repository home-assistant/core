"""Test the Amber Electric Sensors."""
from amberelectric.model.interval import SpikeStatus
from homeassistant.components.amberelectric.sensor import (
    AmberEnergyPriceSensor,
    AmberFactory,
    AmberForecastSensor,
    AmberPriceSensor,
    AmberPriceSpikeSensor,
    AmberRenewablesSensor,
)
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import DEVICE_CLASS_MONETARY
from typing import Generator

from tests.components.amberelectric.helpers import (
    FEED_IN_CHANNEL,
    GENERAL_CHANNEL,
    GENERAL_ONLY_SITE_ID,
    GENERAL_AND_CONTROLLED_SITE_ID,
    GENERAL_AND_FEED_IN_SITE_ID,
    CONTROLLED_LOAD_CHANNEL,
    generate_current_interval,
)
from amberelectric.model.channel import Channel
from amberelectric.model.site import Site
from amberelectric.model.channel import ChannelType
import pytest
from unittest.mock import Mock, patch
from dateutil import parser


@pytest.fixture(name="current_price_api")
def mock_api_current_price() -> Generator:
    """Return an authentication error."""
    instance = Mock()

    general_site = Site(
        GENERAL_ONLY_SITE_ID,
        "11111111111",
        [Channel(identifier="E1", type="general")],
    )
    general_and_controlled_load = Site(
        GENERAL_AND_CONTROLLED_SITE_ID,
        "11111111112",
        [
            Channel(identifier="E1", type="general"),
            Channel(identifier="E2", type="controlledLoad"),
        ],
    )
    general_and_feed_in = Site(
        GENERAL_AND_FEED_IN_SITE_ID,
        "11111111113",
        [
            Channel(identifier="E1", type="general"),
            Channel(identifier="E2", type="controlledLoad"),
        ],
    )
    instance.get_sites.return_value = [
        general_site,
        general_and_controlled_load,
        general_and_feed_in,
    ]

    with patch("amberelectric.api.AmberApi.create", return_value=instance):
        yield instance


def test_sensor_factory_only_general_no_update(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the state of the Factory sensors before an update has completed."""
    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    sensors = factory.build_sensors()

    assert len(sensors) == 0


def test_sensor_factory_only_general(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of all the Amber sensors when there is only general channels."""
    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    assert len(sensors) == 5

    assert (
        len(list(filter(lambda sensor: sensor.__class__ == AmberPriceSensor, sensors)))
        == 1
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberEnergyPriceSensor, sensors
                )
            )
        )
        == 1
    )
    assert (
        len(
            list(
                filter(lambda sensor: sensor.__class__ == AmberForecastSensor, sensors)
            )
        )
        == 1
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberRenewablesSensor, sensors
                )
            )
        )
        == 1
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberPriceSpikeSensor, sensors
                )
            )
        )
        == 1
    )


def test_sensor_factory_general_and_controlled(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of all the Amber sensors when there are general and controlled load channels."""
    current_price_api.get_current_price.return_value = (
        GENERAL_CHANNEL + CONTROLLED_LOAD_CHANNEL
    )
    factory = AmberFactory(
        hass, "Home", GENERAL_AND_CONTROLLED_SITE_ID, current_price_api
    )
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    assert len(sensors) == 8

    assert (
        len(list(filter(lambda sensor: sensor.__class__ == AmberPriceSensor, sensors)))
        == 2
    )
    assert (
        len(
            list(
                filter(lambda sensor: sensor.__class__ == AmberForecastSensor, sensors)
            )
        )
        == 2
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberEnergyPriceSensor, sensors
                )
            )
        )
        == 2
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberRenewablesSensor, sensors
                )
            )
        )
        == 1
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberPriceSpikeSensor, sensors
                )
            )
        )
        == 1
    )


def test_sensor_factory_general_and_feed_in(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of all the Amber sensors when there are general and feed in channels."""
    current_price_api.get_current_price.return_value = GENERAL_CHANNEL + FEED_IN_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_AND_FEED_IN_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    assert len(sensors) == 8

    assert (
        len(list(filter(lambda sensor: sensor.__class__ == AmberPriceSensor, sensors)))
        == 2
    )
    assert (
        len(
            list(
                filter(lambda sensor: sensor.__class__ == AmberForecastSensor, sensors)
            )
        )
        == 2
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberEnergyPriceSensor, sensors
                )
            )
        )
        == 2
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberRenewablesSensor, sensors
                )
            )
        )
        == 1
    )
    assert (
        len(
            list(
                filter(
                    lambda sensor: sensor.__class__ == AmberPriceSpikeSensor, sensors
                )
            )
        )
        == 1
    )


def test_amber_general_price_sensor(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of all the Amber sensors when there is only general channels."""
    general_channel = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )
    current_price_api.get_current_price.return_value = [general_channel]
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    amber_price_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberPriceSensor, sensors)
    )
    general_price_sensor = amber_price_sensors[0]
    assert general_price_sensor.name == "Home - General Price"
    assert general_price_sensor.unique_id == "01fg2k6v5tb6x9w0ewppmzd6mj_general_price"
    assert general_price_sensor.icon == "mdi:transmission-tower"
    assert general_price_sensor.unit_of_measurement == "¢/kWh"
    assert general_price_sensor.state == 8

    attributes = general_price_sensor.device_state_attributes
    assert attributes is not None
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == 8
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 1
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "general"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_controlled_load_price_sensor(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of all the Amber sensors when there is only general channels."""
    general = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )
    controlled_load = generate_current_interval(
        ChannelType.CONTROLLED_LOAD, parser.parse("2021-09-21T08:30:00+10:00")
    )
    current_price_api.get_current_price.return_value = [general, controlled_load]
    factory = AmberFactory(
        hass, "Home", GENERAL_AND_CONTROLLED_SITE_ID, current_price_api
    )
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    amber_price_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberPriceSensor, sensors)
    )
    sensor = amber_price_sensors[1]
    assert sensor.name == "Home - Controlled Load Price"
    assert sensor.unique_id == "01fg2mc8rf7gbc4kjxp3yfz162_controlled_load_price"
    assert sensor.icon == "mdi:clock-outline"
    assert sensor.unit_of_measurement == "¢/kWh"
    assert sensor.state == 8

    attributes = sensor.device_state_attributes
    assert attributes is not None
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == 8
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 1
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "controlledLoad"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_price_sensor(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of the general Amber price sensor."""
    general_channel = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )
    current_price_api.get_current_price.return_value = [general_channel]
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    amber_price_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberPriceSensor, sensors)
    )
    general_price_sensor = amber_price_sensors[0]
    assert general_price_sensor.name == "Home - General Price"
    assert general_price_sensor.unique_id == "01fg2k6v5tb6x9w0ewppmzd6mj_general_price"
    assert general_price_sensor.icon == "mdi:transmission-tower"
    assert general_price_sensor.unit_of_measurement == "¢/kWh"
    assert general_price_sensor.state == 8

    attributes = general_price_sensor.device_state_attributes
    assert attributes is not None
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == 8
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 1
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "general"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_forecast_sensor(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of the general Amber forecast sensor."""
    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    amber_price_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberForecastSensor, sensors)
    )
    general_price_sensor = amber_price_sensors[0]
    assert general_price_sensor.name == "Home - General Forecast"
    assert (
        general_price_sensor.unique_id == "01fg2k6v5tb6x9w0ewppmzd6mj_general_forecast"
    )
    assert general_price_sensor.icon == "mdi:transmission-tower"
    assert general_price_sensor.unit_of_measurement == "¢/kWh"
    assert general_price_sensor.state == 9

    attributes = general_price_sensor.device_state_attributes
    assert attributes is not None
    assert attributes["channel_type"] == "general"

    assert len(attributes["forecasts"]) == 1
    first_forecast = attributes["forecasts"][0]
    assert first_forecast["duration"] == 30
    assert first_forecast["date"] == "2021-09-21"
    assert first_forecast["per_kwh"] == 9
    assert first_forecast["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["spot_per_kwh"] == 1
    assert first_forecast["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first_forecast["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first_forecast["renewables"] == 50
    assert first_forecast["spike_status"] == "none"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_energy_price_sensor(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of the general Amber energy price sensor."""
    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    amber_price_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberEnergyPriceSensor, sensors)
    )
    general_price_sensor = amber_price_sensors[0]
    assert general_price_sensor.name == "Home - General Energy Price"
    assert (
        general_price_sensor.unique_id
        == "01fg2k6v5tb6x9w0ewppmzd6mj_general_energy_price"
    )
    assert general_price_sensor.icon == "mdi:transmission-tower"
    assert general_price_sensor.device_class == DEVICE_CLASS_MONETARY
    assert general_price_sensor.unit_of_measurement == "AUD"
    assert general_price_sensor.state == 0.08


def test_amber_general_renewable_sensor(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of the Amber renewables sensor."""
    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    amber_price_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberRenewablesSensor, sensors)
    )
    general_price_sensor = amber_price_sensors[0]
    assert general_price_sensor.name == "Home - Renewables"
    assert general_price_sensor.unique_id == "01fg2k6v5tb6x9w0ewppmzd6mj_renewables"
    assert general_price_sensor.icon == "mdi:solar-power"
    assert general_price_sensor.unit_of_measurement == "%"
    assert general_price_sensor.state == 51
    attributes = general_price_sensor.device_state_attributes
    assert attributes is not None
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_price_spike_sensor_no_spike(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of the Amber price spike sensor when there is no spike."""
    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    amber_price_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberPriceSpikeSensor, sensors)
    )
    general_price_sensor = amber_price_sensors[0]
    assert general_price_sensor.name == "Home - Price Spike"
    assert general_price_sensor.unique_id == "01fg2k6v5tb6x9w0ewppmzd6mj_price_spike"
    assert general_price_sensor.icon == "mdi:power-plug"
    assert general_price_sensor.state is False
    attributes = general_price_sensor.device_state_attributes
    assert attributes is not None
    assert attributes["spike_status"] == "none"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_price_spike_sensor_potential_spike(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of the Amber price spike sensor when there is a potential spike."""
    general_channel = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )

    general_channel.spike_status = SpikeStatus.POTENTIAL
    current_price_api.get_current_price.return_value = [general_channel]

    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    filtered_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberPriceSpikeSensor, sensors)
    )
    sensor = filtered_sensors[0]
    assert sensor.name == "Home - Price Spike"
    assert sensor.unique_id == "01fg2k6v5tb6x9w0ewppmzd6mj_price_spike"
    assert sensor.icon == "mdi:power-plug-outline"
    assert sensor.state is False
    attributes = sensor.device_state_attributes
    assert attributes is not None
    assert attributes["spike_status"] == "potential"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_price_spike_sensor_spike(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Testing the creation of the Amber price spike sensor when there is a potential spike."""
    general_channel = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )

    general_channel.spike_status = SpikeStatus.SPIKE
    current_price_api.get_current_price.return_value = [general_channel]

    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, current_price_api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    filtered_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberPriceSpikeSensor, sensors)
    )
    sensor = filtered_sensors[0]
    assert sensor.name == "Home - Price Spike"
    assert sensor.unique_id == "01fg2k6v5tb6x9w0ewppmzd6mj_price_spike"
    assert sensor.icon == "mdi:power-plug-off"
    assert sensor.state is True
    attributes = sensor.device_state_attributes
    assert attributes is not None
    assert attributes["spike_status"] == "spike"
    assert attributes["attribution"] == "Data provided by Amber Electric"
