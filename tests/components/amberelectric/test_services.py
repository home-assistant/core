"""Test the Amber Service object."""

import re

import pytest
import voluptuous as vol

from homeassistant.components.amberelectric.const import DOMAIN, SERVICE_GET_FORECASTS
from homeassistant.components.amberelectric.services import ATTR_CHANNEL_TYPE
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_integration
from .helpers import (
    GENERAL_AND_CONTROLLED_SITE_ID,
    GENERAL_AND_FEED_IN_SITE_ID,
    GENERAL_ONLY_SITE_ID,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_amber_client_forecasts")
async def test_get_general_forecasts(
    hass: HomeAssistant,
    general_channel_config_entry: MockConfigEntry,
) -> None:
    """Test fetching general forecasts."""
    await setup_integration(hass, general_channel_config_entry)
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_CONFIG_ENTRY_ID: GENERAL_ONLY_SITE_ID, ATTR_CHANNEL_TYPE: "general"},
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


@pytest.mark.usefixtures("mock_amber_client_forecasts")
async def test_get_controlled_load_forecasts(
    hass: HomeAssistant,
    general_channel_and_controlled_load_config_entry: MockConfigEntry,
) -> None:
    """Test fetching general forecasts."""
    await setup_integration(hass, general_channel_and_controlled_load_config_entry)
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            ATTR_CONFIG_ENTRY_ID: GENERAL_AND_CONTROLLED_SITE_ID,
            ATTR_CHANNEL_TYPE: "controlled_load",
        },
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


@pytest.mark.usefixtures("mock_amber_client_forecasts")
async def test_get_feed_in_forecasts(
    hass: HomeAssistant,
    general_channel_and_feed_in_config_entry: MockConfigEntry,
) -> None:
    """Test fetching general forecasts."""
    await setup_integration(hass, general_channel_and_feed_in_config_entry)
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            ATTR_CONFIG_ENTRY_ID: GENERAL_AND_FEED_IN_SITE_ID,
            ATTR_CHANNEL_TYPE: "feed_in",
        },
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


@pytest.mark.usefixtures("mock_amber_client_forecasts")
async def test_incorrect_channel_type(
    hass: HomeAssistant,
    general_channel_config_entry: MockConfigEntry,
) -> None:
    """Test error when the channel type is incorrect."""
    await setup_integration(hass, general_channel_config_entry)

    with pytest.raises(
        vol.error.MultipleInvalid,
        match=re.escape(
            "value must be one of ['controlled_load', 'feed_in', 'general'] for dictionary value @ data['channel_type']"
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECASTS,
            {
                ATTR_CONFIG_ENTRY_ID: GENERAL_ONLY_SITE_ID,
                ATTR_CHANNEL_TYPE: "incorrect",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("mock_amber_client_general_forecasts")
async def test_unavailable_channel_type(
    hass: HomeAssistant,
    general_channel_config_entry: MockConfigEntry,
) -> None:
    """Test error when the channel type is not found."""
    await setup_integration(hass, general_channel_config_entry)

    with pytest.raises(
        ServiceValidationError, match="There is no controlled_load channel at this site"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECASTS,
            {
                ATTR_CONFIG_ENTRY_ID: GENERAL_ONLY_SITE_ID,
                ATTR_CHANNEL_TYPE: "controlled_load",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("mock_amber_client_forecasts")
async def test_service_entry_availability(
    hass: HomeAssistant,
    general_channel_config_entry: MockConfigEntry,
) -> None:
    """Test the services without valid entry."""
    general_channel_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(general_channel_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Mock Title is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECASTS,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id,
                ATTR_CHANNEL_TYPE: "general",
            },
            blocking=True,
            return_response=True,
        )

    with pytest.raises(
        ServiceValidationError,
        match='Config entry "bad-config_id" not found in registry',
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECASTS,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id", ATTR_CHANNEL_TYPE: "general"},
            blocking=True,
            return_response=True,
        )
