"""Test Bang & Olufsen device triggers."""

from unittest.mock import AsyncMock

from mozart_api.models import (
    BeoRemoteButton,
    ButtonEvent,
    PairedRemote,
    PairedRemoteResponse,
)
import pytest

from homeassistant.components import automation
from homeassistant.components.bang_olufsen.const import DOMAIN
from homeassistant.components.bang_olufsen.device_trigger import (
    DEFAULT_TRIGGERS,
    REMOTE_TRIGGERS,
)
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_get_device_automations


@pytest.mark.parametrize(
    ("remotes_response", "additional_triggers"),
    [
        # No remote connected
        (PairedRemoteResponse(items=[]), ()),
        # Remote connected
        (
            PairedRemoteResponse(items=[PairedRemote(address="", name="")]),
            REMOTE_TRIGGERS,
        ),
    ],
)
async def test_async_get_triggers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    device_registry: DeviceRegistry,
    remotes_response: PairedRemoteResponse,
    additional_triggers: tuple[str],
) -> None:
    """Test the expected triggers are returned."""

    mock_mozart_client.get_bluetooth_remotes.return_value = remotes_response

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.unique_id
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.unique_id)}
        )
    )
    trigger_types = list(DEFAULT_TRIGGERS)
    trigger_types.extend(additional_triggers)

    # Generate the expected triggers
    expected_triggers = [
        {
            CONF_PLATFORM: CONF_DEVICE,
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
            "metadata": {},
        }
        for trigger_type in trigger_types
    ]

    # Get the registered triggers
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )

    # Ensure the expected triggers are registered
    for expected_trigger in expected_triggers:
        assert expected_trigger in triggers


@pytest.mark.parametrize(
    ("notification", "notification_method", "trigger_type"),
    [
        # Button event trigger
        (
            ButtonEvent(button="PlayPause", state="shortPress"),
            "get_button_notifications",
            "PlayPause_shortPress",
        ),
        # Remote trigger
        (
            BeoRemoteButton(key="Control/Wind", type="KeyPress"),
            "get_beo_remote_button_notifications",
            "Control/Wind_KeyPress",
        ),
    ],
)
async def test_if_fires_trigger(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    device_registry: DeviceRegistry,
    notification: BeoRemoteButton | ButtonEvent,
    notification_method: str,
    trigger_type: str,
) -> None:
    """Test device triggers firing."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.unique_id
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.unique_id)}
        )
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": trigger_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.event.data.device_id }}",
                            "id": "{{ trigger.id }}",
                        },
                    },
                }
            ],
        },
    )

    # Trigger automation
    notification_callback = getattr(mock_mozart_client, notification_method).call_args[
        0
    ][0]

    notification_callback(notification)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == device.id
    assert service_calls[0].data["id"] == 0
