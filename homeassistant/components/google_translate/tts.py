"""Support for the Google speech service."""
from io import BytesIO
import logging

from gtts import gTTS, gTTSError
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, Provider

_LOGGER = logging.getLogger(__name__)

SUPPORT_LANGUAGES = [
    "af",
    "ar",
    "bg",
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
    "iw",
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

DEFAULT_LANG = "en"

SUPPORT_OPTIONS = ["tld"]

SUPPORT_TLD = [
    "com",
    "ad",
    "ae",
    "com.af",
    "com.ag",
    "com.ai",
    "al",
    "am",
    "co.ao",
    "com.ar",
    "as",
    "at",
    "com.au",
    "az",
    "ba",
    "com.bd",
    "be",
    "bf",
    "bg",
    "com.bh",
    "bi",
    "bj",
    "com.bn",
    "com.bo",
    "com.br",
    "bs",
    "bt",
    "co.bw",
    "by",
    "com.bz",
    "ca",
    "cd",
    "cf",
    "cg",
    "ch",
    "ci",
    "co.ck",
    "cl",
    "cm",
    "cn",
    "com.co",
    "co.cr",
    "com.cu",
    "cv",
    "com.cy",
    "cz",
    "de",
    "dj",
    "dk",
    "dm",
    "com.do",
    "dz",
    "com.ec",
    "ee",
    "com.eg",
    "es",
    "com.et",
    "fi",
    "com.fj",
    "fm",
    "fr",
    "ga",
    "ge",
    "gg",
    "com.gh",
    "com.gi",
    "gl",
    "gm",
    "gr",
    "com.gt",
    "gy",
    "com.hk",
    "hn",
    "hr",
    "ht",
    "hu",
    "co.id",
    "ie",
    "co.il",
    "im",
    "co.in",
    "iq",
    "is",
    "it",
    "je",
    "com.jm",
    "jo",
    "co.jp",
    "co.ke",
    "com.kh",
    "ki",
    "kg",
    "co.kr",
    "com.kw",
    "kz",
    "la",
    "com.lb",
    "li",
    "lk",
    "co.ls",
    "lt",
    "lu",
    "lv",
    "com.ly",
    "co.ma",
    "md",
    "me",
    "mg",
    "mk",
    "ml",
    "com.mm",
    "mn",
    "ms",
    "com.mt",
    "mu",
    "mv",
    "mw",
    "com.mx",
    "com.my",
    "co.mz",
    "com.na",
    "com.ng",
    "com.ni",
    "ne",
    "nl",
    "no",
    "com.np",
    "nr",
    "nu",
    "co.nz",
    "com.om",
    "com.pa",
    "com.pe",
    "com.pg",
    "com.ph",
    "com.pk",
    "pl",
    "pn",
    "com.pr",
    "ps",
    "pt",
    "com.py",
    "com.qa",
    "ro",
    "ru",
    "rw",
    "com.sa",
    "com.sb",
    "sc",
    "se",
    "com.sg",
    "sh",
    "si",
    "sk",
    "com.sl",
    "sn",
    "so",
    "sm",
    "sr",
    "st",
    "com.sv",
    "td",
    "tg",
    "co.th",
    "com.tj",
    "tl",
    "tm",
    "tn",
    "to",
    "com.tr",
    "tt",
    "com.tw",
    "co.tz",
    "com.ua",
    "co.ug",
    "co.uk",
    "com.uy",
    "co.uz",
    "com.vc",
    "co.ve",
    "vg",
    "co.vi",
    "com.vn",
    "vu",
    "ws",
    "rs",
    "co.za",
    "co.zm",
    "co.zw",
    "cat",
]

DEFAULT_TLD = "com"

MAP_LANG_TLD = {
    "en-us": {"lang": "en", "tld": "com"},
    "en-gb": {"lang": "en", "tld": "co.uk"},
    "en-uk": {"lang": "en", "tld": "co.uk"},
    "en-au": {"lang": "en", "tld": "com.au"},
    "en-ca": {"lang": "en", "tld": "ca"},
    "en-in": {"lang": "en", "tld": "co.in"},
    "en-ie": {"lang": "en", "tld": "ie"},
    "en-za": {"lang": "en", "tld": "co.za"},
    "fr-ca": {"lang": "fr", "tld": "ca"},
    "fr-fr": {"lang": "fr", "tld": "fr"},
    "pt-br": {"lang": "pt", "tld": "com.br"},
    "pt-pt": {"lang": "pt", "tld": "pt"},
    "es-es": {"lang": "es", "tld": "es"},
    "es-us": {"lang": "es", "tld": "com"},
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional("tld", default=DEFAULT_TLD): vol.In(SUPPORT_TLD),
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Google speech component."""
    return GoogleProvider(hass, config[CONF_LANG], config["tld"])


class GoogleProvider(Provider):
    """The Google speech API provider."""

    def __init__(self, hass, lang, tld):
        """Init Google TTS service."""
        self.hass = hass
        if lang in MAP_LANG_TLD:
            self._lang = MAP_LANG_TLD[lang]["lang"]
            self._tld = MAP_LANG_TLD[lang]["tld"]
        else:
            self._lang = lang
            self._tld = tld
        self.name = "Google"

    @property
    def default_language(self):
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self):
        """Return a list of supported options."""
        return SUPPORT_OPTIONS

    def get_tts_audio(self, message, language, options=None):
        """Load TTS from google."""
        tld = self._tld
        if language in MAP_LANG_TLD:
            tld = MAP_LANG_TLD[language]["tld"]
            language = MAP_LANG_TLD[language]["lang"]
        if options is not None and "tld" in options.keys():
            tld = options["tld"]
        tts = gTTS(text=message, lang=language, tld=tld)
        mp3_data = BytesIO()

        try:
            tts.write_to_fp(mp3_data)
        except gTTSError as exc:
            _LOGGER.exception("Error during processing of TTS request %s", exc)
            return None, None

        return "mp3", mp3_data.getvalue()
