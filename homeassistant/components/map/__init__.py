"""Support for showing device locations."""

from homeassistant.components import onboarding
from homeassistant.components.lovelace import _create_map_dashboard
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

DOMAIN = "map"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

STORAGE_KEY = DOMAIN
STORAGE_VERSION_MAJOR = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Create a map panel."""

    if DOMAIN in config:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            is_persistent=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "map",
            },
        )

    store: Store[dict[str, bool]] = Store(
        hass,
        STORAGE_VERSION_MAJOR,
        STORAGE_KEY,
    )
    data = await store.async_load()
    if data:
        return True

    if onboarding.async_is_onboarded(hass):
        await _create_map_dashboard(hass)

    await store.async_save({"migrated": True})

    return True
