"""Light platform for Avea."""

from contextlib import suppress
import logging
from typing import Any

import avea
from bleak.exc import BleakError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import color as color_util

from . import AveaConfigEntry
from .const import DOMAIN, INTEGRATION_TITLE, UNKNOWN_NAME

_LOGGER = logging.getLogger(__name__)
UPDATE_EXCEPTIONS = (BleakError, OSError, RuntimeError)
BREAKS_IN_HA_VERSION = "2026.12.0"


def _normalize_name(name: str | None) -> str | None:
    """Return a valid Avea name."""
    if not name or name == UNKNOWN_NAME:
        return None
    return name


def _create_deprecated_yaml_issue(hass: HomeAssistant) -> None:
    """Create the deprecated YAML issue for Avea."""
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


def _create_yaml_import_failed_issue(hass: HomeAssistant) -> None:
    """Create a repair issue when the Avea YAML import cannot find bulbs."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_import_issue_no_bulbs",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml_import_issue_no_bulbs",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AveaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Avea light platform."""
    async_add_entities([AveaLight(entry.runtime_data, entry)], update_before_add=True)


def _discover_bulbs_for_import() -> list[dict[str, str]]:
    """Discover and validate Avea bulbs for YAML import."""
    discovered_bulbs: list[dict[str, str]] = []

    for bulb in avea.discover_avea_bulbs():
        address = bulb.addr
        try:
            name = bulb.get_name()
            brightness = bulb.get_brightness()
        except UPDATE_EXCEPTIONS as err:
            _LOGGER.warning(
                "Skipping Avea bulb %s during YAML import due to read failure: %s",
                address,
                err,
            )
            continue
        finally:
            with suppress(*UPDATE_EXCEPTIONS):
                bulb.close()

        if brightness is None:
            _LOGGER.warning(
                "Skipping Avea bulb %s during YAML import due to read failure: brightness is None",
                address,
            )
            continue

        discovered_bulbs.append(
            {
                CONF_ADDRESS: address,
                CONF_NAME: _normalize_name(name)
                or _normalize_name(bulb.name)
                or address,
            }
        )

    return discovered_bulbs


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the Avea YAML platform into config entries."""
    try:
        bulbs = await hass.async_add_executor_job(_discover_bulbs_for_import)
    except UPDATE_EXCEPTIONS as err:
        raise PlatformNotReady("Could not discover Avea bulbs for YAML import") from err

    if not bulbs:
        _create_yaml_import_failed_issue(hass)

    for bulb in bulbs:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=bulb,
        )

        if (
            result.get("type") is FlowResultType.ABORT
            and result.get("reason") != "already_configured"
        ):
            _LOGGER.warning(
                "Skipping Avea YAML import for bulb %s: %s",
                bulb[CONF_ADDRESS],
                result.get("reason"),
            )
            continue

    _create_deprecated_yaml_issue(hass)


class AveaLight(LightEntity):
    """Representation of an Avea."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}

    def __init__(self, light: avea.Bulb, entry: AveaConfigEntry) -> None:
        """Initialize an AveaLight."""
        self._light = light
        self._attr_unique_id = entry.unique_id or entry.data[CONF_ADDRESS]
        self._attr_name = entry.title
        self._attr_brightness = light.brightness

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if not kwargs:
            self._light.set_brightness(4095)
        else:
            if ATTR_BRIGHTNESS in kwargs:
                bright = round((kwargs[ATTR_BRIGHTNESS] / 255) * 4095)
                self._light.set_brightness(bright)
            if ATTR_HS_COLOR in kwargs:
                rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
                self._light.set_rgb(rgb[0], rgb[1], rgb[2])

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._light.set_brightness(0)

    def update(self) -> None:
        """Fetch new state data for this light."""
        if (brightness := self._light.get_brightness()) is not None:
            self._attr_is_on = brightness != 0
            self._attr_brightness = round(255 * (brightness / 4095))
