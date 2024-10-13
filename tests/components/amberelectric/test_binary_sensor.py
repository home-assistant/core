"""Test the Amber Electric Sensors."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import Mock, patch

from amberelectric.model.channel import ChannelType
from amberelectric.model.current_interval import CurrentInterval
from amberelectric.model.interval import SpikeStatus
from amberelectric.model.tariff_information import TariffInformation
from dateutil import parser
import pytest

from homeassistant.components.amberelectric.const import (
    CONF_SITE_ID,
    CONF_SITE_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .helpers import GENERAL_CHANNEL, GENERAL_ONLY_SITE_ID, generate_current_interval

from tests.common import MockConfigEntry

MOCK_API_TOKEN = "psk_0000000000000000"


@pytest.fixture
async def setup_no_spike(hass: HomeAssistant) -> AsyncGenerator[Mock]:
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
        "amberelectric.api.AmberApi.create",
        return_value=instance,
    ) as mock_update:
        instance.get_current_price = Mock(return_value=GENERAL_CHANNEL)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_potential_spike(hass: HomeAssistant) -> AsyncGenerator[Mock]:
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
        "amberelectric.api.AmberApi.create",
        return_value=instance,
    ) as mock_update:
        general_channel: list[CurrentInterval] = [
            generate_current_interval(
                ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
            ),
        ]
        general_channel[0].spike_status = SpikeStatus.POTENTIAL
        instance.get_current_price = Mock(return_value=general_channel)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_spike(hass: HomeAssistant) -> AsyncGenerator[Mock]:
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
        "amberelectric.api.AmberApi.create",
        return_value=instance,
    ) as mock_update:
        general_channel: list[CurrentInterval] = [
            generate_current_interval(
                ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
            ),
        ]
        general_channel[0].spike_status = SpikeStatus.SPIKE
        instance.get_current_price = Mock(return_value=general_channel)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.mark.usefixtures("setup_no_spike")
def test_no_spike_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber renewables sensor."""
    assert len(hass.states.async_all()) == 6
    sensor = hass.states.get("binary_sensor.mock_title_price_spike")
    assert sensor
    assert sensor.state == "off"
    assert sensor.attributes["icon"] == "mdi:power-plug"
    assert sensor.attributes["spike_status"] == "none"


@pytest.mark.usefixtures("setup_potential_spike")
def test_potential_spike_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber renewables sensor."""
    assert len(hass.states.async_all()) == 6
    sensor = hass.states.get("binary_sensor.mock_title_price_spike")
    assert sensor
    assert sensor.state == "off"
    assert sensor.attributes["icon"] == "mdi:power-plug-outline"
    assert sensor.attributes["spike_status"] == "potential"


@pytest.mark.usefixtures("setup_spike")
def test_spike_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber renewables sensor."""
    assert len(hass.states.async_all()) == 6
    sensor = hass.states.get("binary_sensor.mock_title_price_spike")
    assert sensor
    assert sensor.state == "on"
    assert sensor.attributes["icon"] == "mdi:power-plug-off"
    assert sensor.attributes["spike_status"] == "spike"


@pytest.fixture
async def setup_inactive_demand_window(hass: HomeAssistant) -> AsyncGenerator[Mock]:
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
        "amberelectric.api.AmberApi.create",
        return_value=instance,
    ) as mock_update:
        general_channel: list[CurrentInterval] = [
            generate_current_interval(
                ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
            ),
        ]
        general_channel[0].tariff_information = TariffInformation(demandWindow=False)
        instance.get_current_price = Mock(return_value=general_channel)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_active_demand_window(hass: HomeAssistant) -> AsyncGenerator[Mock]:
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
        "amberelectric.api.AmberApi.create",
        return_value=instance,
    ) as mock_update:
        general_channel: list[CurrentInterval] = [
            generate_current_interval(
                ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
            ),
        ]
        general_channel[0].tariff_information = TariffInformation(demandWindow=True)
        instance.get_current_price = Mock(return_value=general_channel)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.mark.usefixtures("setup_inactive_demand_window")
def test_inactive_demand_window_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber demand_window sensor."""
    assert len(hass.states.async_all()) == 6
    sensor = hass.states.get("binary_sensor.mock_title_demand_window")
    assert sensor
    assert sensor.state == "off"


@pytest.mark.usefixtures("setup_active_demand_window")
def test_active_demand_window_sensor(hass: HomeAssistant) -> None:
    """Testing the creation of the Amber demand_window sensor."""
    assert len(hass.states.async_all()) == 6
    sensor = hass.states.get("binary_sensor.mock_title_demand_window")
    assert sensor
    assert sensor.state == "on"
