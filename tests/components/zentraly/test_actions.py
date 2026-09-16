"""Tests for action failure categories and translated errors."""

from typing import Any

import pytest
from zentraly import (
    NumberCapability,
    ZentralyApiError,
    ZentralyCommandRejectedError,
    ZentralyConnectionBusyError,
    ZentralyConnectionError,
    ZentralyInvalidResponseError,
    ZentralyValidationError,
)
from zentraly.commands.base import ActionCommandExecutor, ZentralyDeviceCommands

from homeassistant.components.zentraly.actions import translate_action_errors
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.translation import async_get_translations


@pytest.mark.parametrize(
    ("error", "ha_error", "key"),
    [
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
    error: type[ZentralyApiError], ha_error: type[HomeAssistantError], key: str
) -> None:
    """Expose translation metadata instead of model-specific technical text."""

    @translate_action_errors
    async def action() -> None:
        raise error("Technical protocol detail")

    with pytest.raises(ha_error) as exc:
        await action()
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


class SimpleTimerCommands(ZentralyDeviceCommands):
    """Test model with a timer and no power or operation-mode capability."""

    capabilities = frozenset({NumberCapability.TIMER})

    def build_read_timer(self, rid: int, mac: str) -> dict[str, Any]:
        """Build this model's timer query."""
        return {"cmd": "readAttr", "rid": rid, "mac": mac}

    def parse_timer_response(
        self, response: dict[str, Any], expected_rid: int
    ) -> float:
        """Read this model's timer value."""
        return float(response["minutes"])

    async def async_set_timer(
        self, mac: str, value: float, execute: ActionCommandExecutor
    ) -> None:
        """Set a timer with a single model-specific command."""
        await execute(
            lambda rid: {"cmd": "zclCmd", "rid": rid, "mac": mac, "minutes": value}
        )
