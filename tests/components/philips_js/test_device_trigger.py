"""The tests for Philips TV device triggers."""

from datetime import timedelta

from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.philips_js.const import DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, async_get_device_automations


async def test_get_triggers(hass: HomeAssistant, mock_device) -> None:
    """Test we get the expected triggers."""
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "turn_on",
            "device_id": mock_device.id,
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, mock_device.id
    )
    triggers = [trigger for trigger in triggers if trigger["domain"] == DOMAIN]
    assert triggers == unordered(expected_triggers)


async def test_if_fires_on_turn_on_request(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_tv,
    mock_entity,
    mock_device,
) -> None:
    """Test for turn_on and turn_off triggers firing."""

    mock_tv.on = False

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": mock_device.id,
                        "type": "turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.device_id }}",
                            "id": "{{ trigger.id}}",
                        },
                    },
                }
            ]
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": mock_entity},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[0].domain == "media_player"
    assert service_calls[0].service == "turn_on"
    assert service_calls[1].domain == "test"
    assert service_calls[1].service == "automation"
    assert service_calls[1].data["some"] == mock_device.id
    assert service_calls[1].data["id"] == 0


async def test_turn_on_trigger_used_after_dropped_poll(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_tv,
    mock_entity,
    mock_device,
) -> None:
    """Test a dropped poll within grace does not make turn_on use setPowerState."""
    mock_tv.powerstate = "On"

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": mock_device.id,
                        "type": "turn_on",
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )

    async def update() -> bool:
        mock_tv.on = False
        return False

    mock_tv.update.side_effect = update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert mock_tv.on is False

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": mock_entity},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_tv.setPowerState.assert_not_awaited()
    assert [call.domain for call in service_calls] == ["media_player", "test"]
