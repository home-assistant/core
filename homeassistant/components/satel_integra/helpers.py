"""Helpers for Satel Integra commands."""

from collections.abc import Awaitable

from satel_integra import (
    SatelCommandRejectedError,
    SatelNoResponseError,
    SatelResultCode,
)

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN


async def async_validate_command(command: Awaitable[object]) -> None:
    """Run a command and translate failures reported by the alarm panel."""
    try:
        await command
    except SatelCommandRejectedError as err:
        if err.result.code is SatelResultCode.USER_CODE_NOT_FOUND:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="command_invalid_access_code",
            ) from err
        if err.result.code is SatelResultCode.NO_ACCESS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="command_no_access",
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_rejected",
            translation_placeholders={"result_code": f"0x{int(err.result.code):02X}"},
        ) from err
    except SatelNoResponseError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_outcome_unknown",
        ) from err
