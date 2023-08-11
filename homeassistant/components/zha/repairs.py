"""ZHA repairs for common environmental and device problems."""
from __future__ import annotations

from universal_silabs_flasher.const import ApplicationType
from universal_silabs_flasher.flasher import Flasher

from homeassistant.components.homeassistant_yellow import hardware as yellow_hardware
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .core.const import DOMAIN

DISABLE_MULTIPAN_URL_YELLOW = (
    "https://yellow.home-assistant.io/guides/disable-multiprotocol/"
)
DISABLE_MULTIPAN_URL_SKYCONNECT = (
    "https://skyconnect.home-assistant.io/procedures/disable-multiprotocol/"
)


ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED = "wrong_silabs_firmware_installed"


async def probe_silabs_firmware_type(device: str) -> ApplicationType | None:
    """Probe the running firmware on a Silabs device."""
    flasher = Flasher(device=device)
    await flasher.probe_app_type()

    return flasher.app_type


async def warn_on_wrong_silabs_firmware(hass: HomeAssistant, device: str) -> None:
    """Create a repair issue if the wrong type of SiLabs firmware is detected."""
    app_type = await probe_silabs_firmware_type(device)

    if app_type is None:
        # Failed to probe, we can't tell if the wrong firmware is installed
        return

    if app_type == ApplicationType.EZSP:
        # If connecting fails but we somehow probe EZSP (e.g. stuck in bootloader),
        # reconnect, it should work
        raise ConfigEntryNotReady()

    try:
        yellow_hardware.async_info(hass)
        learn_more_url = DISABLE_MULTIPAN_URL_YELLOW
    except HomeAssistantError:
        learn_more_url = DISABLE_MULTIPAN_URL_SKYCONNECT

    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
        is_fixable=False,
        is_persistent=False,
        learn_more_url=learn_more_url,
        severity=ir.IssueSeverity.CRITICAL,
        translation_key=ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
        translation_placeholders={"firmware_type": app_type.name},
    )


def async_delete_blocking_issues(hass: HomeAssistant) -> None:
    """Delete repair issues that should disappear on a successful startup."""
    ir.async_delete_issue(hass, DOMAIN, ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED)
