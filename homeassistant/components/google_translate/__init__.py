"""The google_translate component."""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.tts import CONF_LANG

DOMAIN = "google_translate"

SUPPORT_LANGUAGES = [
    "af",
    "ar",
    "bn",
    "bs",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "eo",
    "es",
    "et",
    "fi",
    "fr",
    "gu",
    "hi",
    "hr",
    "hu",
    "hy",
    "id",
    "is",
    "it",
    "ja",
    "jw",
    "km",
    "kn",
    "ko",
    "la",
    "lv",
    "mk",
    "ml",
    "mr",
    "my",
    "ne",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "si",
    "sk",
    "sq",
    "sr",
    "su",
    "sv",
    "sw",
    "ta",
    "te",
    "th",
    "tl",
    "tr",
    "uk",
    "ur",
    "vi",
    # dialects
    "zh-CN",
    "zh-cn",
    "zh-tw",
    "en-us",
    "en-ca",
    "en-uk",
    "en-gb",
    "en-au",
    "en-gh",
    "en-in",
    "en-ie",
    "en-nz",
    "en-ng",
    "en-ph",
    "en-za",
    "en-tz",
    "fr-ca",
    "fr-fr",
    "pt-br",
    "pt-pt",
    "es-es",
    "es-us",
]

CONF_TLD = "tld"
CONF_SLOW = "slow"

DEFAULT_TLD = "com"
DEFAULT_LANG = "en"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_TLD, default=DEFAULT_TLD): cv.string,
                vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
                vol.Optional(CONF_SLOW, default=False): cv.boolean,
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the google_translate configs."""

    config.setdefault(DOMAIN, {})
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = config.get(DOMAIN)

    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("tts", DOMAIN, {}, config)
    )

    return True
