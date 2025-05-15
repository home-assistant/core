"""Test the Amber Service object."""

from collections.abc import Generator
from datetime import date
from unittest.mock import Mock, patch

from amberelectric.models.channel import Channel, ChannelType
from amberelectric.models.site import Site
from amberelectric.models.site_status import SiteStatus
import pytest

from homeassistant.components.amberelectric.const import (
    CONF_SITE_ID,
    CONF_SITE_NAME,
    DOMAIN,
    GET_FORECASTS_SERVICE,
)
from homeassistant.components.amberelectric.services import (
    ATTR_CHANNEL_TYPE,
    ATTR_SITE_ID,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_integration
from .helpers import FORECASTS, GENERAL_ONLY_SITE_ID

from tests.common import MockConfigEntry


async def create_amber_config_entry(site_id):
    """Create an Amber config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "TOKEN",
            CONF_SITE_NAME: "home",
            CONF_SITE_ID: site_id,
        },
        entry_id=site_id,
    )


@pytest.fixture
async def amber_config_entry():
    """Generate the default Picnic config entry."""
    return await create_amber_config_entry(GENERAL_ONLY_SITE_ID)


@pytest.fixture(name="current_price_api")
def mock_api_current_price() -> Generator:
    """Return an authentication error."""
    instance = Mock()

    site = Site(
        id=GENERAL_ONLY_SITE_ID,
        nmi="11111111111",
        channels=[
            Channel(identifier="E1", type=ChannelType.GENERAL, tariff="A100"),
            Channel(identifier="E2", type=ChannelType.CONTROLLEDLOAD, tariff="A180"),
            Channel(identifier="B1", type=ChannelType.FEEDIN, tariff="A100"),
        ],
        network="Jemena",
        status=SiteStatus("active"),
        activeFrom=date(2021, 1, 1),
        closedOn=None,
        interval_length=30,
    )

    instance.get_sites = Mock(return_value=[site])
    instance.get_current_prices = Mock(return_value=FORECASTS)

    with patch("amberelectric.AmberApi", return_value=instance):
        yield instance


async def test_get_general_forecasts(
    hass: HomeAssistant, current_price_api, amber_config_entry: MockConfigEntry
) -> None:
    """Test fetching general forecasts."""
    await setup_integration(hass, amber_config_entry)
    result = await hass.services.async_call(
        DOMAIN,
        GET_FORECASTS_SERVICE,
        {ATTR_SITE_ID: GENERAL_ONLY_SITE_ID, ATTR_CHANNEL_TYPE: "general"},
        blocking=True,
        return_response=True,
    )
    assert len(result["forecasts"]) == 3

    first = result["forecasts"][0]
    assert first["duration"] == 30
    assert first["date"] == "2021-09-21"
    assert first["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first["per_kwh"] == 0.09
    assert first["spot_per_kwh"] == 0.01
    assert first["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first["renewables"] == 50
    assert first["spike_status"] == "none"
    assert first["descriptor"] == "very_low"


async def test_get_controlled_load_forecasts(
    hass: HomeAssistant, current_price_api, amber_config_entry: MockConfigEntry
) -> None:
    """Test fetching general forecasts."""
    await setup_integration(hass, amber_config_entry)
    result = await hass.services.async_call(
        DOMAIN,
        GET_FORECASTS_SERVICE,
        {ATTR_SITE_ID: GENERAL_ONLY_SITE_ID, ATTR_CHANNEL_TYPE: "controlled_load"},
        blocking=True,
        return_response=True,
    )
    assert len(result["forecasts"]) == 3

    first = result["forecasts"][0]
    assert first["duration"] == 30
    assert first["date"] == "2021-09-21"
    assert first["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first["per_kwh"] == 0.04
    assert first["spot_per_kwh"] == 0.01
    assert first["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first["renewables"] == 50
    assert first["spike_status"] == "none"
    assert first["descriptor"] == "very_low"


async def test_get_feed_in_forecasts(
    hass: HomeAssistant, current_price_api, amber_config_entry: MockConfigEntry
) -> None:
    """Test fetching general forecasts."""
    await setup_integration(hass, amber_config_entry)
    result = await hass.services.async_call(
        DOMAIN,
        GET_FORECASTS_SERVICE,
        {ATTR_SITE_ID: GENERAL_ONLY_SITE_ID, ATTR_CHANNEL_TYPE: "feed_in"},
        blocking=True,
        return_response=True,
    )
    assert len(result["forecasts"]) == 3

    first = result["forecasts"][0]
    assert first["duration"] == 30
    assert first["date"] == "2021-09-21"
    assert first["nem_date"] == "2021-09-21T09:00:00+10:00"
    assert first["per_kwh"] == -0.01
    assert first["spot_per_kwh"] == 0.01
    assert first["start_time"] == "2021-09-21T08:30:00+10:00"
    assert first["end_time"] == "2021-09-21T09:00:00+10:00"
    assert first["renewables"] == 50
    assert first["spike_status"] == "none"
    assert first["descriptor"] == "very_low"


async def test_incorrect_channel_type(
    hass: HomeAssistant, current_price_api, amber_config_entry: MockConfigEntry
) -> None:
    """Test error when the channel type is not found."""
    await setup_integration(hass, amber_config_entry)

    with pytest.raises(
        ServiceValidationError, match="There is no incorrect channel at this site"
    ):
        await hass.services.async_call(
            DOMAIN,
            GET_FORECASTS_SERVICE,
            {ATTR_SITE_ID: GENERAL_ONLY_SITE_ID, ATTR_CHANNEL_TYPE: "incorrect"},
            blocking=True,
            return_response=True,
        )


async def test_service_entry_availability(
    hass: HomeAssistant, current_price_api, amber_config_entry: MockConfigEntry
) -> None:
    """Test the services without valid entry."""
    amber_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(amber_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Mock Title is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            GET_FORECASTS_SERVICE,
            {ATTR_SITE_ID: mock_config_entry2.entry_id, ATTR_CHANNEL_TYPE: "general"},
            blocking=True,
            return_response=True,
        )

    with pytest.raises(
        ServiceValidationError,
        match='Integration "amberelectric" not found in registry',
    ):
        await hass.services.async_call(
            DOMAIN,
            GET_FORECASTS_SERVICE,
            {ATTR_SITE_ID: "bad-config_id", ATTR_CHANNEL_TYPE: "general"},
            blocking=True,
            return_response=True,
        )
