"""Module to help with parsing and generating configuration files."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from contextlib import suppress
import enum
import logging
import os
import pathlib
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlparse

import voluptuous as vol
from webrtc_models import RTCConfiguration, RTCIceServer
import yarl

from . import auth
from .auth import mfa_modules as auth_mfa_modules, providers as auth_providers
from .const import (
    ATTR_ASSUMED_STATE,
    ATTR_FRIENDLY_NAME,
    ATTR_HIDDEN,
    BASE_PLATFORMS,
    CONF_ALLOWLIST_EXTERNAL_DIRS,
    CONF_ALLOWLIST_EXTERNAL_URLS,
    CONF_AUTH_MFA_MODULES,
    CONF_AUTH_PROVIDERS,
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_CUSTOMIZE,
    CONF_CUSTOMIZE_DOMAIN,
    CONF_CUSTOMIZE_GLOB,
    CONF_DEBUG,
    CONF_ELEVATION,
    CONF_EXTERNAL_URL,
    CONF_ID,
    CONF_INTERNAL_URL,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LEGACY_TEMPLATES,
    CONF_LONGITUDE,
    CONF_MEDIA_DIRS,
    CONF_NAME,
    CONF_PACKAGES,
    CONF_RADIUS,
    CONF_TEMPERATURE_UNIT,
    CONF_TIME_ZONE,
    CONF_TYPE,
    CONF_UNIT_SYSTEM,
    CONF_URL,
    CONF_USERNAME,
    EVENT_CORE_CONFIG_UPDATE,
    LEGACY_CONF_WHITELIST_EXTERNAL_DIRS,
    UnitOfLength,
    __version__,
)
from .core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from .generated.currencies import HISTORIC_CURRENCIES
from .helpers import config_validation as cv, issue_registry as ir
from .helpers.entity_values import EntityValues
from .helpers.storage import Store
from .helpers.typing import UNDEFINED, UndefinedType
from .util import dt as dt_util, location
from .util.hass_dict import HassKey
from .util.package import is_docker_env
from .util.unit_system import (
    _CONF_UNIT_SYSTEM_IMPERIAL,
    _CONF_UNIT_SYSTEM_METRIC,
    _CONF_UNIT_SYSTEM_US_CUSTOMARY,
    METRIC_SYSTEM,
    UnitSystem,
    get_unit_system,
)

# Typing imports that create a circular dependency
if TYPE_CHECKING:
    from .components.http import ApiConfig

_LOGGER = logging.getLogger(__name__)

DATA_CUSTOMIZE: HassKey[EntityValues] = HassKey("hass_customize")

CONF_CREDENTIAL: Final = "credential"
CONF_ICE_SERVERS: Final = "ice_servers"
CONF_WEBRTC: Final = "webrtc"

CORE_STORAGE_KEY = "core.config"
CORE_STORAGE_VERSION = 1
CORE_STORAGE_MINOR_VERSION = 4


class ConfigSource(enum.StrEnum):
    """Source of core configuration."""

    DEFAULT = "default"
    DISCOVERED = "discovered"
    STORAGE = "storage"
    YAML = "yaml"


def _no_duplicate_auth_provider(
    configs: Sequence[dict[str, Any]],
) -> Sequence[dict[str, Any]]:
    """No duplicate auth provider config allowed in a list.

    Each type of auth provider can only have one config without optional id.
    Unique id is required if same type of auth provider used multiple times.
    """
    config_keys: set[tuple[str, str | None]] = set()
    for config in configs:
        key = (config[CONF_TYPE], config.get(CONF_ID))
        if key in config_keys:
            raise vol.Invalid(
                f"Duplicate auth provider {config[CONF_TYPE]} found. "
                "Please add unique IDs "
                "if you want to have the same auth provider twice"
            )
        config_keys.add(key)
    return configs


def _no_duplicate_auth_mfa_module(
    configs: Sequence[dict[str, Any]],
) -> Sequence[dict[str, Any]]:
    """No duplicate auth mfa module item allowed in a list.

    Each type of mfa module can only have one config without optional id.
    A global unique id is required if same type of mfa module used multiple
    times.
    Note: this is different than auth provider
    """
    config_keys: set[str] = set()
    for config in configs:
        key = config.get(CONF_ID, config[CONF_TYPE])
        if key in config_keys:
            raise vol.Invalid(
                f"Duplicate mfa module {config[CONF_TYPE]} found. "
                "Please add unique IDs "
                "if you want to have the same mfa module twice"
            )
        config_keys.add(key)
    return configs


def _filter_bad_internal_external_urls(conf: dict) -> dict:
    """Filter internal/external URL with a path."""
    for key in CONF_INTERNAL_URL, CONF_EXTERNAL_URL:
        if key in conf and urlparse(conf[key]).path not in ("", "/"):
            # We warn but do not fix, because if this was incorrectly configured,
            # adjusting this value might impact security.
            _LOGGER.warning(
                "Invalid %s set. It's not allowed to have a path (/bla)", key
            )

    return conf


# Schema for all packages element
_PACKAGES_CONFIG_SCHEMA = vol.Schema({cv.string: vol.Any(dict, list)})

# Schema for individual package definition
_PACKAGE_DEFINITION_SCHEMA = vol.Schema({cv.string: vol.Any(dict, list, None)})

_CUSTOMIZE_DICT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
        vol.Optional(ATTR_HIDDEN): cv.boolean,
        vol.Optional(ATTR_ASSUMED_STATE): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)

_CUSTOMIZE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CUSTOMIZE, default={}): vol.Schema(
            {cv.entity_id: _CUSTOMIZE_DICT_SCHEMA}
        ),
        vol.Optional(CONF_CUSTOMIZE_DOMAIN, default={}): vol.Schema(
            {cv.string: _CUSTOMIZE_DICT_SCHEMA}
        ),
        vol.Optional(CONF_CUSTOMIZE_GLOB, default={}): vol.Schema(
            {cv.string: _CUSTOMIZE_DICT_SCHEMA}
        ),
    }
)


def _raise_issue_if_imperial_unit_system(
    hass: HomeAssistant, config: dict[str, Any]
) -> dict[str, Any]:
    if config.get(CONF_UNIT_SYSTEM) == _CONF_UNIT_SYSTEM_IMPERIAL:
        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            "imperial_unit_system",
            is_fixable=False,
            learn_more_url="homeassistant://config/general",
            severity=ir.IssueSeverity.WARNING,
            translation_key="imperial_unit_system",
        )
        config[CONF_UNIT_SYSTEM] = _CONF_UNIT_SYSTEM_US_CUSTOMARY
    else:
        ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, "imperial_unit_system")

    return config


def _raise_issue_if_historic_currency(hass: HomeAssistant, currency: str) -> None:
    if currency not in HISTORIC_CURRENCIES:
        ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, "historic_currency")
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "historic_currency",
        is_fixable=False,
        learn_more_url="homeassistant://config/general",
        severity=ir.IssueSeverity.WARNING,
        translation_key="historic_currency",
        translation_placeholders={"currency": currency},
    )


def _raise_issue_if_no_country(hass: HomeAssistant, country: str | None) -> None:
    if country is not None:
        ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, "country_not_configured")
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "country_not_configured",
        is_fixable=False,
        learn_more_url="homeassistant://config/general",
        severity=ir.IssueSeverity.WARNING,
        translation_key="country_not_configured",
    )


def _validate_currency(data: Any) -> Any:
    try:
        return cv.currency(data)
    except vol.InInvalid:
        with suppress(vol.InInvalid):
            return cv.historic_currency(data)
        raise


def _validate_stun_or_turn_url(value: Any) -> str:
    """Validate an URL."""
    url_in = str(value)
    url = urlparse(url_in)

    if url.scheme not in ("stun", "stuns", "turn", "turns"):
        raise vol.Invalid("invalid url")
    return url_in


CORE_CONFIG_SCHEMA = vol.All(
    _CUSTOMIZE_CONFIG_SCHEMA.extend(
        {
            CONF_NAME: vol.Coerce(str),
            CONF_LATITUDE: cv.latitude,
            CONF_LONGITUDE: cv.longitude,
            CONF_ELEVATION: vol.Coerce(int),
            CONF_RADIUS: cv.positive_int,
            vol.Remove(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
            CONF_UNIT_SYSTEM: vol.Any(
                _CONF_UNIT_SYSTEM_METRIC,
                _CONF_UNIT_SYSTEM_US_CUSTOMARY,
                _CONF_UNIT_SYSTEM_IMPERIAL,
            ),
            CONF_TIME_ZONE: cv.time_zone,
            vol.Optional(CONF_INTERNAL_URL): cv.url,
            vol.Optional(CONF_EXTERNAL_URL): cv.url,
            vol.Optional(CONF_ALLOWLIST_EXTERNAL_DIRS): vol.All(
                cv.ensure_list, [vol.IsDir()]
            ),
            vol.Optional(LEGACY_CONF_WHITELIST_EXTERNAL_DIRS): vol.All(
                cv.ensure_list, [vol.IsDir()]
            ),
            vol.Optional(CONF_ALLOWLIST_EXTERNAL_URLS): vol.All(
                cv.ensure_list, [cv.url]
            ),
            vol.Optional(CONF_PACKAGES, default={}): _PACKAGES_CONFIG_SCHEMA,
            vol.Optional(CONF_AUTH_PROVIDERS): vol.All(
                cv.ensure_list,
                [
                    auth_providers.AUTH_PROVIDER_SCHEMA.extend(
                        {
                            CONF_TYPE: vol.NotIn(
                                ["insecure_example"],
                                (
                                    "The insecure_example auth provider"
                                    " is for testing only."
                                ),
                            )
                        }
                    )
                ],
                _no_duplicate_auth_provider,
            ),
            vol.Optional(CONF_AUTH_MFA_MODULES): vol.All(
                cv.ensure_list,
                [
                    auth_mfa_modules.MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend(
                        {
                            CONF_TYPE: vol.NotIn(
                                ["insecure_example"],
                                "The insecure_example mfa module is for testing only.",
                            )
                        }
                    )
                ],
                _no_duplicate_auth_mfa_module,
            ),
            vol.Optional(CONF_MEDIA_DIRS): cv.schema_with_slug_keys(vol.IsDir()),
            vol.Remove(CONF_LEGACY_TEMPLATES): cv.boolean,
            vol.Optional(CONF_CURRENCY): _validate_currency,
            vol.Optional(CONF_COUNTRY): cv.country,
            vol.Optional(CONF_LANGUAGE): cv.language,
            vol.Optional(CONF_DEBUG): cv.boolean,
            vol.Optional(CONF_WEBRTC): vol.Schema(
                {
                    vol.Required(CONF_ICE_SERVERS): vol.All(
                        cv.ensure_list,
                        [
                            vol.Schema(
                                {
                                    vol.Required(CONF_URL): vol.All(
                                        cv.ensure_list, [_validate_stun_or_turn_url]
                                    ),
                                    vol.Optional(CONF_USERNAME): cv.string,
                                    vol.Optional(CONF_CREDENTIAL): cv.string,
                                }
                            )
                        ],
                    )
                }
            ),
        }
    ),
    _filter_bad_internal_external_urls,
)


async def async_process_ha_core_config(hass: HomeAssistant, config: dict) -> None:
    """Process the [homeassistant] section from the configuration.

    This method is a coroutine.
    """
    # CORE_CONFIG_SCHEMA is not async safe since it uses vol.IsDir
    # so we need to run it in an executor job.
    config = await hass.async_add_executor_job(CORE_CONFIG_SCHEMA, config)

    # Check if we need to raise an issue for imperial unit system
    config = _raise_issue_if_imperial_unit_system(hass, config)

    # Only load auth during startup.
    if not hasattr(hass, "auth"):
        if (auth_conf := config.get(CONF_AUTH_PROVIDERS)) is None:
            auth_conf = [{"type": "homeassistant"}]

        mfa_conf = config.get(
            CONF_AUTH_MFA_MODULES,
            [{"type": "totp", "id": "totp", "name": "Authenticator app"}],
        )

        setattr(
            hass, "auth", await auth.auth_manager_from_config(hass, auth_conf, mfa_conf)
        )

    await hass.config.async_load()

    hac = hass.config

    if any(
        k in config
        for k in (
            CONF_COUNTRY,
            CONF_CURRENCY,
            CONF_ELEVATION,
            CONF_EXTERNAL_URL,
            CONF_INTERNAL_URL,
            CONF_LANGUAGE,
            CONF_LATITUDE,
            CONF_LONGITUDE,
            CONF_NAME,
            CONF_RADIUS,
            CONF_TIME_ZONE,
            CONF_UNIT_SYSTEM,
        )
    ):
        hac.config_source = ConfigSource.YAML

    for key, attr in (
        (CONF_COUNTRY, "country"),
        (CONF_CURRENCY, "currency"),
        (CONF_ELEVATION, "elevation"),
        (CONF_EXTERNAL_URL, "external_url"),
        (CONF_INTERNAL_URL, "internal_url"),
        (CONF_LANGUAGE, "language"),
        (CONF_LATITUDE, "latitude"),
        (CONF_LONGITUDE, "longitude"),
        (CONF_MEDIA_DIRS, "media_dirs"),
        (CONF_NAME, "location_name"),
        (CONF_RADIUS, "radius"),
    ):
        if key in config:
            setattr(hac, attr, config[key])

    if config.get(CONF_DEBUG):
        hac.debug = True

    if CONF_WEBRTC in config:
        hac.webrtc.ice_servers = [
            RTCIceServer(
                server[CONF_URL],
                server.get(CONF_USERNAME),
                server.get(CONF_CREDENTIAL),
            )
            for server in config[CONF_WEBRTC][CONF_ICE_SERVERS]
        ]

    _raise_issue_if_historic_currency(hass, hass.config.currency)
    _raise_issue_if_no_country(hass, hass.config.country)

    if CONF_TIME_ZONE in config:
        await hac.async_set_time_zone(config[CONF_TIME_ZONE])

    if CONF_MEDIA_DIRS not in config:
        if is_docker_env():
            hac.media_dirs = {"local": "/media"}
        else:
            hac.media_dirs = {"local": hass.config.path("media")}

    # Init whitelist external dir
    hac.allowlist_external_dirs = {hass.config.path("www"), *hac.media_dirs.values()}
    if CONF_ALLOWLIST_EXTERNAL_DIRS in config:
        hac.allowlist_external_dirs.update(set(config[CONF_ALLOWLIST_EXTERNAL_DIRS]))

    elif LEGACY_CONF_WHITELIST_EXTERNAL_DIRS in config:
        _LOGGER.warning(
            "Key %s has been replaced with %s. Please update your config",
            LEGACY_CONF_WHITELIST_EXTERNAL_DIRS,
            CONF_ALLOWLIST_EXTERNAL_DIRS,
        )
        hac.allowlist_external_dirs.update(
            set(config[LEGACY_CONF_WHITELIST_EXTERNAL_DIRS])
        )

    # Init whitelist external URL list – make sure to add / to every URL that doesn't
    # already have it so that we can properly test "path ownership"
    if CONF_ALLOWLIST_EXTERNAL_URLS in config:
        hac.allowlist_external_urls.update(
            url if url.endswith("/") else f"{url}/"
            for url in config[CONF_ALLOWLIST_EXTERNAL_URLS]
        )

    # Customize
    cust_exact = dict(config[CONF_CUSTOMIZE])
    cust_domain = dict(config[CONF_CUSTOMIZE_DOMAIN])
    cust_glob = OrderedDict(config[CONF_CUSTOMIZE_GLOB])

    for name, pkg in config[CONF_PACKAGES].items():
        if (pkg_cust := pkg.get(HOMEASSISTANT_DOMAIN)) is None:
            continue

        try:
            pkg_cust = _CUSTOMIZE_CONFIG_SCHEMA(pkg_cust)
        except vol.Invalid:
            _LOGGER.warning("Package %s contains invalid customize", name)
            continue

        cust_exact.update(pkg_cust[CONF_CUSTOMIZE])
        cust_domain.update(pkg_cust[CONF_CUSTOMIZE_DOMAIN])
        cust_glob.update(pkg_cust[CONF_CUSTOMIZE_GLOB])

    hass.data[DATA_CUSTOMIZE] = EntityValues(cust_exact, cust_domain, cust_glob)

    if CONF_UNIT_SYSTEM in config:
        hac.units = get_unit_system(config[CONF_UNIT_SYSTEM])


class _ComponentSet(set[str]):
    """Set of loaded components.

    This set contains both top level components and platforms.

    Examples:
    `light`, `switch`, `hue`, `mjpeg.camera`, `universal.media_player`,
    `homeassistant.scene`

    The top level components set only contains the top level components.

    The all components set contains all components, including platform
    based components.

    """

    def __init__(
        self, top_level_components: set[str], all_components: set[str]
    ) -> None:
        """Initialize the component set."""
        self._top_level_components = top_level_components
        self._all_components = all_components

    def add(self, value: str) -> None:
        """Add a component to the store."""
        if "." not in value:
            self._top_level_components.add(value)
            self._all_components.add(value)
        else:
            platform, _, domain = value.partition(".")
            if domain in BASE_PLATFORMS:
                self._all_components.add(platform)
        return super().add(value)

    def remove(self, value: str) -> None:
        """Remove a component from the store."""
        if "." in value:
            raise ValueError("_ComponentSet does not support removing sub-components")
        self._top_level_components.remove(value)
        return super().remove(value)

    def discard(self, value: str) -> None:
        """Remove a component from the store."""
        raise NotImplementedError("_ComponentSet does not support discard, use remove")


class Config:
    """Configuration settings for Home Assistant."""

    _store: Config._ConfigStore

    def __init__(self, hass: HomeAssistant, config_dir: str) -> None:
        """Initialize a new config object."""
        # pylint: disable-next=import-outside-toplevel
        from .components.zone import DEFAULT_RADIUS

        self.hass = hass

        self.latitude: float = 0
        self.longitude: float = 0

        self.elevation: int = 0
        """Elevation (always in meters regardless of the unit system)."""

        self.radius: int = DEFAULT_RADIUS
        """Radius of the Home Zone (always in meters regardless of the unit system)."""

        self.debug: bool = False
        self.location_name: str = "Home"
        self.time_zone: str = "UTC"
        self.units: UnitSystem = METRIC_SYSTEM
        self.internal_url: str | None = None
        self.external_url: str | None = None
        self.currency: str = "EUR"
        self.country: str | None = None
        self.language: str = "en"

        self.config_source: ConfigSource = ConfigSource.DEFAULT

        # If True, pip install is skipped for requirements on startup
        self.skip_pip: bool = False

        # List of packages to skip when installing requirements on startup
        self.skip_pip_packages: list[str] = []

        # Set of loaded top level components
        # This set is updated by _ComponentSet
        # and should not be modified directly
        self.top_level_components: set[str] = set()

        # Set of all loaded components including platform
        # based components
        self.all_components: set[str] = set()

        # Set of loaded components
        self.components = _ComponentSet(self.top_level_components, self.all_components)

        # API (HTTP) server configuration
        self.api: ApiConfig | None = None

        # Directory that holds the configuration
        self.config_dir: str = config_dir

        # List of allowed external dirs to access
        self.allowlist_external_dirs: set[str] = set()

        # List of allowed external URLs that integrations may use
        self.allowlist_external_urls: set[str] = set()

        # Dictionary of Media folders that integrations may use
        self.media_dirs: dict[str, str] = {}

        # If Home Assistant is running in recovery mode
        self.recovery_mode: bool = False

        # Use legacy template behavior
        self.legacy_templates: bool = False

        # If Home Assistant is running in safe mode
        self.safe_mode: bool = False

        self.webrtc = RTCConfiguration()

    def async_initialize(self) -> None:
        """Finish initializing a config object.

        This must be called before the config object is used.
        """
        self._store = self._ConfigStore(self.hass)

    def distance(self, lat: float, lon: float) -> float | None:
        """Calculate distance from Home Assistant.

        Async friendly.
        """
        return self.units.length(
            location.distance(self.latitude, self.longitude, lat, lon),
            UnitOfLength.METERS,
        )

    def path(self, *path: str) -> str:
        """Generate path to the file within the configuration directory.

        Async friendly.
        """
        return os.path.join(self.config_dir, *path)

    def is_allowed_external_url(self, url: str) -> bool:
        """Check if an external URL is allowed."""
        parsed_url = f"{yarl.URL(url)!s}/"

        return any(
            allowed
            for allowed in self.allowlist_external_urls
            if parsed_url.startswith(allowed)
        )

    def is_allowed_path(self, path: str) -> bool:
        """Check if the path is valid for access from outside.

        This function does blocking I/O and should not be called from the event loop.
        Use hass.async_add_executor_job to schedule it on the executor.
        """
        assert path is not None

        thepath = pathlib.Path(path)
        try:
            # The file path does not have to exist (it's parent should)
            if thepath.exists():
                thepath = thepath.resolve()
            else:
                thepath = thepath.parent.resolve()
        except (FileNotFoundError, RuntimeError, PermissionError):
            return False

        for allowed_path in self.allowlist_external_dirs:
            try:
                thepath.relative_to(allowed_path)
            except ValueError:
                pass
            else:
                return True

        return False

    def as_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the configuration.

        Async friendly.
        """
        allowlist_external_dirs = list(self.allowlist_external_dirs)
        return {
            "allowlist_external_dirs": allowlist_external_dirs,
            "allowlist_external_urls": list(self.allowlist_external_urls),
            "components": list(self.components),
            "config_dir": self.config_dir,
            "config_source": self.config_source,
            "country": self.country,
            "currency": self.currency,
            "debug": self.debug,
            "elevation": self.elevation,
            "external_url": self.external_url,
            "internal_url": self.internal_url,
            "language": self.language,
            "latitude": self.latitude,
            "location_name": self.location_name,
            "longitude": self.longitude,
            "radius": self.radius,
            "recovery_mode": self.recovery_mode,
            "safe_mode": self.safe_mode,
            "state": self.hass.state.value,
            "time_zone": self.time_zone,
            "unit_system": self.units.as_dict(),
            "version": __version__,
            # legacy, backwards compat
            "whitelist_external_dirs": allowlist_external_dirs,
        }

    async def async_set_time_zone(self, time_zone_str: str) -> None:
        """Help to set the time zone."""
        if time_zone := await dt_util.async_get_time_zone(time_zone_str):
            self.time_zone = time_zone_str
            dt_util.set_default_time_zone(time_zone)
        else:
            raise ValueError(f"Received invalid time zone {time_zone_str}")

    async def _async_update(
        self,
        *,
        country: str | UndefinedType | None = UNDEFINED,
        currency: str | None = None,
        elevation: int | None = None,
        external_url: str | UndefinedType | None = UNDEFINED,
        internal_url: str | UndefinedType | None = UNDEFINED,
        language: str | None = None,
        latitude: float | None = None,
        location_name: str | None = None,
        longitude: float | None = None,
        radius: int | None = None,
        source: ConfigSource,
        time_zone: str | None = None,
        unit_system: str | None = None,
    ) -> None:
        """Update the configuration from a dictionary."""
        self.config_source = source
        if country is not UNDEFINED:
            self.country = country
        if currency is not None:
            self.currency = currency
        if elevation is not None:
            self.elevation = elevation
        if external_url is not UNDEFINED:
            self.external_url = external_url
        if internal_url is not UNDEFINED:
            self.internal_url = internal_url
        if language is not None:
            self.language = language
        if latitude is not None:
            self.latitude = latitude
        if location_name is not None:
            self.location_name = location_name
        if longitude is not None:
            self.longitude = longitude
        if radius is not None:
            self.radius = radius
        if time_zone is not None:
            await self.async_set_time_zone(time_zone)
        if unit_system is not None:
            try:
                self.units = get_unit_system(unit_system)
            except ValueError:
                self.units = METRIC_SYSTEM

    async def async_update(self, **kwargs: Any) -> None:
        """Update the configuration from a dictionary."""
        await self._async_update(source=ConfigSource.STORAGE, **kwargs)
        await self._async_store()
        self.hass.bus.async_fire_internal(EVENT_CORE_CONFIG_UPDATE, kwargs)

        _raise_issue_if_historic_currency(self.hass, self.currency)
        _raise_issue_if_no_country(self.hass, self.country)

    async def async_load(self) -> None:
        """Load [homeassistant] core config."""
        if not (data := await self._store.async_load()):
            return

        # In 2021.9 we fixed validation to disallow a path (because that's never
        # correct) but this data still lives in storage, so we print a warning.
        if data.get("external_url") and urlparse(data["external_url"]).path not in (
            "",
            "/",
        ):
            _LOGGER.warning("Invalid external_url set. It's not allowed to have a path")

        if data.get("internal_url") and urlparse(data["internal_url"]).path not in (
            "",
            "/",
        ):
            _LOGGER.warning("Invalid internal_url set. It's not allowed to have a path")

        await self._async_update(
            source=ConfigSource.STORAGE,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            elevation=data.get("elevation"),
            unit_system=data.get("unit_system_v2"),
            location_name=data.get("location_name"),
            time_zone=data.get("time_zone"),
            external_url=data.get("external_url", UNDEFINED),
            internal_url=data.get("internal_url", UNDEFINED),
            currency=data.get("currency"),
            country=data.get("country"),
            language=data.get("language"),
            radius=data["radius"],
        )

    async def _async_store(self) -> None:
        """Store [homeassistant] core config."""
        data = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            # We don't want any integrations to use the name of the unit system
            # so we are using the private attribute here
            "unit_system_v2": self.units._name,  # noqa: SLF001
            "location_name": self.location_name,
            "time_zone": self.time_zone,
            "external_url": self.external_url,
            "internal_url": self.internal_url,
            "currency": self.currency,
            "country": self.country,
            "language": self.language,
            "radius": self.radius,
        }
        await self._store.async_save(data)

    class _ConfigStore(Store[dict[str, Any]]):
        """Class to help storing Config data."""

        def __init__(self, hass: HomeAssistant) -> None:
            """Initialize storage class."""
            super().__init__(
                hass,
                CORE_STORAGE_VERSION,
                CORE_STORAGE_KEY,
                private=True,
                atomic_writes=True,
                minor_version=CORE_STORAGE_MINOR_VERSION,
            )
            self._original_unit_system: str | None = None  # from old store 1.1

        async def _async_migrate_func(
            self,
            old_major_version: int,
            old_minor_version: int,
            old_data: dict[str, Any],
        ) -> dict[str, Any]:
            """Migrate to the new version."""

            # pylint: disable-next=import-outside-toplevel
            from .components.zone import DEFAULT_RADIUS

            data = old_data
            if old_major_version == 1 and old_minor_version < 2:
                # In 1.2, we remove support for "imperial", replaced by "us_customary"
                # Using a new key to allow rollback
                self._original_unit_system = data.get("unit_system")
                data["unit_system_v2"] = self._original_unit_system
                if data["unit_system_v2"] == _CONF_UNIT_SYSTEM_IMPERIAL:
                    data["unit_system_v2"] = _CONF_UNIT_SYSTEM_US_CUSTOMARY
            if old_major_version == 1 and old_minor_version < 3:
                # In 1.3, we add the key "language", initialize it from the
                # owner account.
                data["language"] = "en"
                try:
                    owner = await self.hass.auth.async_get_owner()
                    if owner is not None:
                        # pylint: disable-next=import-outside-toplevel
                        from .components.frontend import storage as frontend_store

                        _, owner_data = await frontend_store.async_user_store(
                            self.hass, owner.id
                        )

                        if (
                            "language" in owner_data
                            and "language" in owner_data["language"]
                        ):
                            with suppress(vol.InInvalid):
                                data["language"] = cv.language(
                                    owner_data["language"]["language"]
                                )
                # pylint: disable-next=broad-except
                except Exception:
                    _LOGGER.exception("Unexpected error during core config migration")
            if old_major_version == 1 and old_minor_version < 4:
                # In 1.4, we add the key "radius", initialize it with the default.
                data.setdefault("radius", DEFAULT_RADIUS)

            if old_major_version > 1:
                raise NotImplementedError
            return data

        async def async_save(self, data: dict[str, Any]) -> None:
            if self._original_unit_system:
                data["unit_system"] = self._original_unit_system
            return await super().async_save(data)
