"""Tests for the Home Assistant triggers."""

from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.config import DATA_PREVIOUS_VERSION
from homeassistant.const import __version__
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service

UPDATED_AUTOMATION = {
    automation.DOMAIN: {
        "alias": "hello",
        "trigger": {"trigger": "homeassistant.updated"},
        "action": {
            "service": "test.automation",
            "data_template": {
                "description": "{{ trigger.description }}",
                "from_version": "{{ trigger.from_version }}",
                "to_version": "{{ trigger.to_version }}",
            },
        },
    }
}


@pytest.mark.parametrize("hass_config", [UPDATED_AUTOMATION])
@pytest.mark.parametrize(
    "previous_version",
    [
        pytest.param("2026.9.4", id="update"),
        pytest.param("2099.1.0", id="downgrade"),
    ],
)
@pytest.mark.usefixtures("mock_hass_config")
async def test_updated_fires_once(
    hass: HomeAssistant, hass_config: ConfigType, previous_version: str
) -> None:
    """Test the updated trigger fires once after a version change."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)
    hass.data[DATA_PREVIOUS_VERSION] = previous_version

    assert await async_setup_component(hass, automation.DOMAIN, hass_config)
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        "description": "Home Assistant updated",
        "from_version": previous_version,
        "to_version": __version__,
    }

    # Armed again after start, so it must stay silent
    await hass.services.async_call(
        automation.DOMAIN, automation.SERVICE_RELOAD, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_updated_not_fired_without_version_change(hass: HomeAssistant) -> None:
    """Test the updated trigger stays silent on a normal start."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)

    assert await async_setup_component(hass, automation.DOMAIN, UPDATED_AUTOMATION)
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(calls) == 0


@pytest.mark.parametrize("event", ["start", "shutdown"])
async def test_legacy_trigger_still_works(hass: HomeAssistant, event: str) -> None:
    """Test the legacy homeassistant trigger is not taken over by the new one."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "homeassistant", "event": event},
                "action": {
                    "service": "test.automation",
                    "data_template": {"event": "{{ trigger.event }}"},
                },
            }
        },
    )
    await hass.async_start()
    await hass.async_block_till_done()
    with patch.object(hass.loop, "stop"):
        await hass.async_stop()

    assert len(calls) == 1
    assert calls[0].data == {"event": event}
