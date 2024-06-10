"""Register an iFrame front end panel."""

import voluptuous as vol

from homeassistant.components import lovelace
from homeassistant.components.lovelace import dashboard
from homeassistant.const import CONF_ICON, CONF_URL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

DOMAIN = "panel_iframe"

CONF_TITLE = "title"

CONF_RELATIVE_URL_ERROR_MSG = "Invalid relative URL. Absolute path required."
CONF_RELATIVE_URL_REGEX = r"\A/"
CONF_REQUIRE_ADMIN = "require_admin"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.Schema(
                {
                    vol.Optional(CONF_TITLE): cv.string,
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(CONF_REQUIRE_ADMIN, default=False): cv.boolean,
                    vol.Required(CONF_URL): vol.Any(
                        vol.Match(
                            CONF_RELATIVE_URL_REGEX, msg=CONF_RELATIVE_URL_ERROR_MSG
                        ),
                        vol.Url(),
                    ),
                }
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

STORAGE_KEY = DOMAIN
STORAGE_VERSION_MAJOR = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the iFrame frontend panels."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2024.10.0",
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "iframe Panel",
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

    dashboards_collection: dashboard.DashboardsCollection = hass.data[lovelace.DOMAIN][
        "dashboards_collection"
    ]

    for url_path, info in config[DOMAIN].items():
        dashboard_create_data = {
            lovelace.CONF_ALLOW_SINGLE_WORD: True,
            lovelace.CONF_URL_PATH: url_path,
        }
        for key in (CONF_ICON, CONF_REQUIRE_ADMIN, CONF_TITLE):
            if key in info:
                dashboard_create_data[key] = info[key]

        await dashboards_collection.async_create_item(dashboard_create_data)

        dashboard_store: dashboard.LovelaceStorage = hass.data[lovelace.DOMAIN][
            "dashboards"
        ][url_path]
        await dashboard_store.async_save(
            {"strategy": {"type": "iframe", "url": info[CONF_URL]}}
        )

    await store.async_save({"migrated": True})

    return True
