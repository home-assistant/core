"""Test the Amber Electric Sensors."""
from __future__ import annotations

from unittest.mock import Mock

from amberelectric.model.channel import Channel, ChannelType
from amberelectric.model.interval import SpikeStatus
from amberelectric.model.site import Site
from dateutil import parser

from homeassistant.components.amberelectric.sensor import (
    AmberEnergyPriceSensor,
    AmberFactory,
    AmberForecastSensor,
    AmberPriceSensor,
    AmberPriceSpikeSensor,
    AmberRenewablesSensor,
)
from homeassistant.components.sensor import DEVICE_CLASS_MONETARY
from homeassistant.core import HomeAssistant

from tests.components.amberelectric.helpers import (
    CONTROLLED_LOAD_CHANNEL,
    FEED_IN_CHANNEL,
    GENERAL_AND_CONTROLLED_FEED_IN_SITE_ID,
    GENERAL_AND_CONTROLLED_SITE_ID,
    GENERAL_AND_FEED_IN_SITE_ID,
    GENERAL_CHANNEL,
    GENERAL_ONLY_SITE_ID,
    generate_current_interval,
)


def sites() -> list[Site]:
    """Return some mock sites."""
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
            Channel(identifier="B2", type="feedIn"),
        ],
    )
    general_and_controlled_load_and_feed_in = Site(
        GENERAL_AND_CONTROLLED_FEED_IN_SITE_ID,
        "11111111114",
        [
            Channel(identifier="E1", type="general"),
            Channel(identifier="E2", type="controlledLoad"),
            Channel(identifier="B2", type="feedIn"),
        ],
    )
    return [
        general_site,
        general_and_controlled_load,
        general_and_controlled_load_and_feed_in,
        general_and_feed_in,
    ]


def test_sensor_factory_only_general_no_update(hass: HomeAssistant) -> None:
    """Testing the state of the Factory sensors before an update has completed."""
    api = Mock()
    api.get_sites.return_value = sites()
    api.get_current_price.return_value = GENERAL_CHANNEL

    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
    factory.data_service.async_setup()
    sensors = factory.build_sensors()

    assert len(sensors) == 0


def test_sensor_factory_only_general(hass: HomeAssistant) -> None:
    """Testing the creation of all the Amber sensors when there is only general channels."""
    api = Mock()
    api.get_sites.return_value = sites()
    api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
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


def test_sensor_factory_general_and_controlled(hass: HomeAssistant) -> None:
    """Testing the creation of all the Amber sensors when there are general and controlled load channels."""
    api = Mock()
    api.get_sites.return_value = sites()
    api.get_current_price.return_value = GENERAL_CHANNEL + CONTROLLED_LOAD_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_AND_CONTROLLED_SITE_ID, api)
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


def test_sensor_factory_general_and_feed_in(hass: HomeAssistant) -> None:
    """Testing the creation of all the Amber sensors when there are general and feed in channels."""
    api = Mock()
    api.get_sites.return_value = sites()
    api.get_current_price.return_value = GENERAL_CHANNEL + FEED_IN_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_AND_FEED_IN_SITE_ID, api)
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


def test_amber_general_price_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of all the Amber sensors when there is only general channels."""
    api = Mock()
    api.get_sites.return_value = sites()
    general_channel = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )
    api.get_current_price.return_value = [general_channel]
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
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
    assert general_price_sensor.native_value == 8

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


def test_amber_controlled_load_price_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of all the Amber sensors when there is only general channels."""
    api = Mock()
    api.get_sites.return_value = sites()
    general = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )
    controlled_load = generate_current_interval(
        ChannelType.CONTROLLED_LOAD, parser.parse("2021-09-21T08:30:00+10:00")
    )
    api.attach_mock(Mock(return_value=[general, controlled_load]), "get_current_price")
    factory = AmberFactory(hass, "Home", GENERAL_AND_CONTROLLED_SITE_ID, api)
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
    assert sensor.native_value == 8

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


def test_amber_solar_price_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of all the Amber sensors when there is only general channels."""
    api = Mock()
    api.get_sites.return_value = sites()
    general = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )
    feed_in = generate_current_interval(
        ChannelType.FEED_IN, parser.parse("2021-09-21T08:30:00+10:00")
    )

    api.get_current_price.return_value = [general, feed_in]
    factory = AmberFactory(hass, "Home", GENERAL_AND_FEED_IN_SITE_ID, api)
    factory.data_service.async_setup()
    factory.data_service.update()
    sensors = factory.build_sensors()

    amber_price_sensors = list(
        filter(lambda sensor: sensor.__class__ == AmberPriceSensor, sensors)
    )
    sensor = amber_price_sensors[1]
    assert sensor.name == "Home - Feed In Price"
    assert sensor.unique_id == "01fg2mcd8ktrzr9mnnw84vp50s_feed_in_price"
    assert sensor.icon == "mdi:solar-power"
    assert sensor.unit_of_measurement == "¢/kWh"
    assert sensor.native_value == -8

    attributes = sensor.device_state_attributes
    assert attributes is not None
    assert attributes["duration"] == 30
    assert attributes["date"] == "2021-09-21"
    assert attributes["per_kwh"] == -8
    assert attributes["nem_date"] == "2021-09-21T08:30:00+10:00"
    assert attributes["spot_per_kwh"] == 1
    assert attributes["start_time"] == "2021-09-21T08:00:00+10:00"
    assert attributes["end_time"] == "2021-09-21T08:30:00+10:00"
    assert attributes["renewables"] == 51
    assert attributes["estimate"] is True
    assert attributes["spike_status"] == "none"
    assert attributes["channel_type"] == "feedIn"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_forecast_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the general Amber forecast sensor."""
    api = Mock()
    api.get_sites.return_value = sites()
    api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
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
    assert general_price_sensor.native_value == 9

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


def test_amber_general_energy_price_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the general Amber energy price sensor."""
    api = Mock()
    api.get_sites.return_value = sites()
    api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
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
    assert general_price_sensor.native_value == 0.08


def test_amber_general_renewable_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber renewables sensor."""
    api = Mock()
    api.get_sites.return_value = sites()
    api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
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
    assert general_price_sensor.native_value == 51
    attributes = general_price_sensor.device_state_attributes
    assert attributes is not None
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_price_spike_sensor_no_spike(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber price spike sensor when there is no spike."""
    api = Mock()
    api.get_sites.return_value = sites()
    api.get_current_price.return_value = GENERAL_CHANNEL
    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
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
    assert general_price_sensor.native_value is False
    attributes = general_price_sensor.device_state_attributes
    assert attributes is not None
    assert attributes["spike_status"] == "none"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_price_spike_sensor_potential_spike(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber price spike sensor when there is a potential spike."""
    api = Mock()
    api.get_sites.return_value = sites()
    general_channel = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )

    general_channel.spike_status = SpikeStatus.POTENTIAL
    api.get_current_price.return_value = [general_channel]

    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
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
    assert sensor.native_value is False
    attributes = sensor.device_state_attributes
    assert attributes is not None
    assert attributes["spike_status"] == "potential"
    assert attributes["attribution"] == "Data provided by Amber Electric"


def test_amber_general_price_spike_sensor_spike(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber price spike sensor when there is a potential spike."""
    api = Mock()
    api.get_sites.return_value = sites()
    general_channel = generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    )

    general_channel.spike_status = SpikeStatus.SPIKE
    api.get_current_price.return_value = [general_channel]

    factory = AmberFactory(hass, "Home", GENERAL_ONLY_SITE_ID, api)
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
    assert sensor.native_value is True
    attributes = sensor.device_state_attributes
    assert attributes is not None
    assert attributes["spike_status"] == "spike"
    assert attributes["attribution"] == "Data provided by Amber Electric"
