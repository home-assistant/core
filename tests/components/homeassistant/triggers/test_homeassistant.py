"""The tests for the Event automation."""

from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.config import DATA_PREVIOUS_VERSION
from homeassistant.const import __version__
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "homeassistant", "event": "start"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        }
    ],
)
@pytest.mark.usefixtures("mock_hass_config")
async def test_if_fires_on_hass_start(
    hass: HomeAssistant,
    hass_config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the firing when Home Assistant starts."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)

    assert await async_setup_component(hass, automation.DOMAIN, hass_config)
    assert automation.is_on(hass, "automation.hello")
    assert len(calls) == 0

    await hass.async_start()
    await hass.async_block_till_done()
    assert automation.is_on(hass, "automation.hello")
    assert len(calls) == 1

    await hass.services.async_call(
        automation.DOMAIN, automation.SERVICE_RELOAD, blocking=True
    )

    assert automation.is_on(hass, "automation.hello")
    assert len(calls) == 1
    assert calls[0].data["id"] == 0

    # Detaching the trigger after it fired must not re-invoke the stale once
    # listener's remove callback.
    assert "Unable to remove unknown job listener" not in caplog.text


async def test_if_not_fires_when_set_up_after_start(hass: HomeAssistant) -> None:
    """Test the start trigger stays silent when armed after Home Assistant started."""
    calls = async_mock_service(hass, "test", "automation")
    assert hass.state is CoreState.running

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "homeassistant", "event": "start"},
                "action": {"service": "test.automation"},
            }
        },
    )
    assert automation.is_on(hass, "automation.hello")
    await hass.async_block_till_done()

    # EVENT_HOMEASSISTANT_STARTED has already fired, so the trigger must not fire.
    assert len(calls) == 0


async def test_if_fires_on_hass_shutdown(hass: HomeAssistant) -> None:
    """Test the firing when Home Assistant shuts down."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "homeassistant", "event": "shutdown"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    )
    assert automation.is_on(hass, "automation.hello")
    assert len(calls) == 0

    await hass.async_start()
    assert automation.is_on(hass, "automation.hello")
    await hass.async_block_till_done()
    assert len(calls) == 0

    with patch.object(hass.loop, "stop"):
        await hass.async_stop()
    assert len(calls) == 1
    assert calls[0].data["id"] == 0


UPDATED_AUTOMATION = {
    automation.DOMAIN: {
        "alias": "hello",
        "trigger": {"platform": "homeassistant", "event": "updated"},
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
async def test_if_fires_on_hass_updated(
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

    # A reload after start must not fire it again
    await hass.services.async_call(
        automation.DOMAIN, automation.SERVICE_RELOAD, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_not_fires_without_version_change(hass: HomeAssistant) -> None:
    """Test the updated trigger stays silent on a normal start."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)

    assert await async_setup_component(hass, automation.DOMAIN, UPDATED_AUTOMATION)
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(calls) == 0
