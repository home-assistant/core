"""Tests for the OpenAI integration."""
from unittest.mock import patch

from openai import error
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar, device_registry as dr, intent

from tests.common import MockConfigEntry


async def test_default_prompt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the default prompt works."""
    for i in range(3):
        area_registry.async_create(f"{i}Empty Area")

    device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "1234")},
        name="Test Device",
        manufacturer="Test Manufacturer",
        model="Test Model",
        suggested_area="Test Area",
    )
    for i in range(3):
        device_registry.async_get_or_create(
            config_entry_id="1234",
            connections={("test", f"{i}abcd")},
            name="Test Service",
            manufacturer="Test Manufacturer",
            model="Test Model",
            suggested_area="Test Area",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
    device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "5678")},
        name="Test Device 2",
        manufacturer="Test Manufacturer 2",
        model="Device 2",
        suggested_area="Test Area 2",
    )
    device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "9876")},
        name="Test Device 3",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3A",
        suggested_area="Test Area 2",
    )
    device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "qwer")},
        name="Test Device 4",
        suggested_area="Test Area 2",
    )
    device = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "9876-disabled")},
        name="Test Device 3",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3A",
        suggested_area="Test Area 2",
    )
    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "9876-no-name")},
        manufacturer="Test Manufacturer NoName",
        model="Test Model NoName",
        suggested_area="Test Area 2",
    )
    device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "9876-integer-values")},
        name=1,
        manufacturer=2,
        model=3,
        suggested_area="Test Area 2",
    )
    with patch(
        "openai.ChatCompletion.acreate",
        return_value={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello, how can I help you?",
                    }
                }
            ]
        },
    ) as mock_create:
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_create.mock_calls[0][2]["messages"] == snapshot


async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that the default prompt works."""
    with patch(
        "openai.ChatCompletion.acreate", side_effect=error.ServiceUnavailableError
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_template_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template error handling works."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            "prompt": "talk like a {% if True %}smarthome{% else %}pirate please.",
        },
    )
    with patch(
        "openai.Engine.list",
    ), patch("openai.ChatCompletion.acreate"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test OpenAIAgent."""
    agent = await conversation._get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"


@pytest.mark.parametrize(
    ("service_data", "expected_args"),
    [
        (
            {"prompt": "Picture of a dog"},
            {"prompt": "Picture of a dog", "size": "512x512"},
        ),
        (
            {"prompt": "Picture of a dog", "size": "256"},
            {"prompt": "Picture of a dog", "size": "256x256"},
        ),
        (
            {"prompt": "Picture of a dog", "size": "1024"},
            {"prompt": "Picture of a dog", "size": "1024x1024"},
        ),
    ],
)
async def test_generate_image_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    service_data,
    expected_args,
) -> None:
    """Test generate image service."""
    service_data["config_entry"] = mock_config_entry.entry_id
    expected_args["api_key"] = mock_config_entry.data["api_key"]
    expected_args["n"] = 1

    with patch(
        "openai.Image.acreate", return_value={"data": [{"url": "A"}]}
    ) as mock_create:
        response = await hass.services.async_call(
            "openai_conversation",
            "generate_image",
            service_data,
            blocking=True,
            return_response=True,
        )

    assert response == {"url": "A"}
    assert len(mock_create.mock_calls) == 1
    assert mock_create.mock_calls[0][2] == expected_args


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_image_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test generate image service handles errors."""
    with patch(
        "openai.Image.acreate", side_effect=error.ServiceUnavailableError("Reason")
    ), pytest.raises(HomeAssistantError, match="Error generating image: Reason"):
        await hass.services.async_call(
            "openai_conversation",
            "generate_image",
            {
                "config_entry": mock_config_entry.entry_id,
                "prompt": "Image of an epic fail",
            },
            blocking=True,
            return_response=True,
        )
