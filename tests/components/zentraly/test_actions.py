"""Tests for action failure categories and translated errors."""

from unittest.mock import MagicMock

import pytest
from zentraly import (
    ZentralyApiError,
    ZentralyCommandRejectedError,
    ZentralyConnectionBusyError,
    ZentralyConnectionError,
    ZentralyInvalidResponseError,
    ZentralyValidationError,
)

from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.translation import async_get_translations

from .conftest import ENTITY_ID


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("error", "ha_error", "key"),
    [
        pytest.param(ZentralyApiError, HomeAssistantError, "action_failed", id="api"),
        pytest.param(
            ZentralyConnectionBusyError,
            HomeAssistantError,
            "connection_busy",
            id="saturation",
        ),
        pytest.param(
            ZentralyConnectionError,
            HomeAssistantError,
            "cannot_connect",
            id="connection",
        ),
        pytest.param(
            ZentralyInvalidResponseError,
            HomeAssistantError,
            "invalid_response",
            id="response",
        ),
        pytest.param(
            ZentralyCommandRejectedError,
            HomeAssistantError,
            "command_rejected",
            id="rejected",
        ),
        pytest.param(
            ZentralyValidationError,
            ServiceValidationError,
            "invalid_action",
            id="validation",
        ),
    ],
)
async def test_error_translation(
    hass: HomeAssistant,
    mock_climate_api: MagicMock,
    error: type[ZentralyApiError],
    ha_error: type[HomeAssistantError],
    key: str,
) -> None:
    """Expose translation metadata instead of model-specific technical text."""

    mock_climate_api.async_set_target_temperature.side_effect = error(
        "Technical protocol detail"
    )
    with pytest.raises(ha_error) as exc:
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22},
            blocking=True,
        )
    assert exc.value.translation_domain == "zentraly"
    assert exc.value.translation_key == key
    assert isinstance(exc.value.__cause__, error)


async def test_exception_translations(hass: HomeAssistant) -> None:
    """Exception messages and placeholders are available in generated translations."""
    translations = await async_get_translations(hass, "en", "exceptions", {"zentraly"})
    assert translations["component.zentraly.exceptions.invalid_action.message"] == (
        "The requested value or operation is not supported by this device."
    )
    assert (
        translations[
            "component.zentraly.exceptions.setup_cannot_connect.message"
        ].format(device_id="ZTTIN0100000001")
        == "Unable to connect to Zentraly device ZTTIN0100000001."
    )
