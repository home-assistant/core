"""Test pi_hole component."""
import logging
from unittest.mock import AsyncMock

from hole.exceptions import HoleError

from homeassistant.components import pi_hole, switch
from homeassistant.components.pi_hole.const import (
    CONF_STATISTICS_ONLY,
    SERVICE_DISABLE,
    SERVICE_DISABLE_ATTR_DURATION,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    CONFIG_DATA_DEFAULTS,
    SWITCH_ENTITY_ID,
    _create_mocked_hole,
    _patch_config_flow_hole,
    _patch_init_hole,
)

from tests.common import MockConfigEntry


async def test_setup_minimal_config(hass: HomeAssistant):
    """Tests component setup with minimal config."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass, pi_hole.DOMAIN, {pi_hole.DOMAIN: [{"host": "pi.hole"}]}
        )

    await hass.async_block_till_done()

    state = hass.states.get("sensor.pi_hole_ads_blocked_today")
    assert state.name == "Pi-Hole Ads Blocked Today"
    assert state.state == "0"

    state = hass.states.get("sensor.pi_hole_ads_percentage_blocked_today")
    assert state.name == "Pi-Hole Ads Percentage Blocked Today"
    assert state.state == "0"

    state = hass.states.get("sensor.pi_hole_dns_queries_cached")
    assert state.name == "Pi-Hole DNS Queries Cached"
    assert state.state == "0"

    state = hass.states.get("sensor.pi_hole_dns_queries_forwarded")
    assert state.name == "Pi-Hole DNS Queries Forwarded"
    assert state.state == "0"

    state = hass.states.get("sensor.pi_hole_dns_queries_today")
    assert state.name == "Pi-Hole DNS Queries Today"
    assert state.state == "0"

    state = hass.states.get("sensor.pi_hole_dns_unique_clients")
    assert state.name == "Pi-Hole DNS Unique Clients"
    assert state.state == "0"

    state = hass.states.get("sensor.pi_hole_dns_unique_domains")
    assert state.name == "Pi-Hole DNS Unique Domains"
    assert state.state == "0"

    state = hass.states.get("sensor.pi_hole_domains_blocked")
    assert state.name == "Pi-Hole Domains Blocked"
    assert state.state == "0"

    state = hass.states.get("sensor.pi_hole_seen_clients")
    assert state.name == "Pi-Hole Seen Clients"
    assert state.state == "0"

    state = hass.states.get("binary_sensor.pi_hole")
    assert state.name == "Pi-Hole"
    assert state.state == "off"


async def test_setup_name_config(hass: HomeAssistant):
    """Tests component setup with a custom name."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass,
            pi_hole.DOMAIN,
            {pi_hole.DOMAIN: [{"host": "pi.hole", "name": "Custom"}]},
        )

    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.custom_ads_blocked_today").name
        == "Custom Ads Blocked Today"
    )


async def test_switch(hass: HomeAssistant, caplog):
    """Test Pi-hole switch."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass,
            pi_hole.DOMAIN,
            {pi_hole.DOMAIN: [{"host": "pi.hole1", "api_key": "1"}]},
        )

        await hass.async_block_till_done()

        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_ON,
            {"entity_id": SWITCH_ENTITY_ID},
            blocking=True,
        )
        mocked_hole.enable.assert_called_once()

        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_OFF,
            {"entity_id": SWITCH_ENTITY_ID},
            blocking=True,
        )
        mocked_hole.disable.assert_called_once_with(True)

        # Failed calls
        type(mocked_hole).enable = AsyncMock(side_effect=HoleError("Error1"))
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_ON,
            {"entity_id": SWITCH_ENTITY_ID},
            blocking=True,
        )
        type(mocked_hole).disable = AsyncMock(side_effect=HoleError("Error2"))
        await hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_OFF,
            {"entity_id": SWITCH_ENTITY_ID},
            blocking=True,
        )
        errors = [x for x in caplog.records if x.levelno == logging.ERROR]
        assert errors[-2].message == "Unable to enable Pi-hole: Error1"
        assert errors[-1].message == "Unable to disable Pi-hole: Error2"


async def test_disable_service_call(hass: HomeAssistant):
    """Test disable service call with no Pi-hole named."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass,
            pi_hole.DOMAIN,
            {
                pi_hole.DOMAIN: [
                    {"host": "pi.hole1", "api_key": "1"},
                    {"host": "pi.hole2", "name": "Custom"},
                ]
            },
        )

        await hass.async_block_till_done()

        await hass.services.async_call(
            pi_hole.DOMAIN,
            SERVICE_DISABLE,
            {ATTR_ENTITY_ID: "all", SERVICE_DISABLE_ATTR_DURATION: "00:00:01"},
            blocking=True,
        )

        await hass.async_block_till_done()

        mocked_hole.disable.assert_called_with(1)


async def test_unload(hass: HomeAssistant):
    """Test unload entities."""
    entry = MockConfigEntry(
        domain=pi_hole.DOMAIN,
        data={**CONFIG_DATA_DEFAULTS, CONF_HOST: "pi.hole"},
    )
    entry.add_to_hass(hass)
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.entry_id in hass.data[pi_hole.DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data[pi_hole.DOMAIN]


async def test_remove_obsolete(hass: HomeAssistant):
    """Test removing obsolete config entry parameters."""
    mocked_hole = _create_mocked_hole()
    entry = MockConfigEntry(
        domain=pi_hole.DOMAIN, data={**CONFIG_DATA_DEFAULTS, CONF_STATISTICS_ONLY: True}
    )
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert CONF_STATISTICS_ONLY not in entry.data
