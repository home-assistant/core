"""Life360 integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.device_tracker import (
    CONF_SCAN_INTERVAL,
    DOMAIN as DEVICE_TRACKER,
)
from homeassistant.components.device_tracker.const import (
    SCAN_INTERVAL as DEFAULT_SCAN_INTERVAL,
)
from homeassistant.const import (
    CONF_EXCLUDE,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_PREFIX,
    CONF_USERNAME,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_AUTHORIZATION,
    CONF_CIRCLES,
    CONF_DRIVING_SPEED,
    CONF_ERROR_THRESHOLD,
    CONF_MAX_GPS_ACCURACY,
    CONF_MAX_UPDATE_WAIT,
    CONF_MEMBERS,
    CONF_SHOW_AS_STATE,
    CONF_WARNING_THRESHOLD,
    DOMAIN,
    SHOW_DRIVING,
    SHOW_MOVING,
)
from .helpers import get_api

DEFAULT_PREFIX = DOMAIN

CONF_ACCOUNTS = "accounts"

SHOW_AS_STATE_OPTS = [SHOW_DRIVING, SHOW_MOVING]


def _excl_incl_list_to_filter_dict(value):
    return {
        "include": CONF_INCLUDE in value,
        "list": value.get(CONF_EXCLUDE) or value.get(CONF_INCLUDE),
    }


def _prefix(value):
    if not value:
        return ""
    if not value.endswith("_"):
        return f"{value}_"
    return value


def _thresholds(config):
    error_threshold = config.get(CONF_ERROR_THRESHOLD)
    warning_threshold = config.get(CONF_WARNING_THRESHOLD)
    if error_threshold and warning_threshold:
        if error_threshold <= warning_threshold:
            raise vol.Invalid(
                f"{CONF_ERROR_THRESHOLD} must be larger than {CONF_WARNING_THRESHOLD}"
            )
    elif not error_threshold and warning_threshold:
        config[CONF_ERROR_THRESHOLD] = warning_threshold + 1
    elif error_threshold and not warning_threshold:
        # Make them the same which effectively prevents warnings.
        config[CONF_WARNING_THRESHOLD] = error_threshold
    else:
        # Log all errors as errors.
        config[CONF_ERROR_THRESHOLD] = 1
        config[CONF_WARNING_THRESHOLD] = 1
    return config


ACCOUNT_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

_SLUG_LIST = vol.All(
    cv.ensure_list, [cv.slugify], vol.Length(min=1, msg="List cannot be empty")
)

_LOWER_STRING_LIST = vol.All(
    cv.ensure_list,
    [vol.All(cv.string, vol.Lower)],
    vol.Length(min=1, msg="List cannot be empty"),
)

_EXCL_INCL_SLUG_LIST = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_EXCLUDE, "incl_excl"): _SLUG_LIST,
            vol.Exclusive(CONF_INCLUDE, "incl_excl"): _SLUG_LIST,
        }
    ),
    cv.has_at_least_one_key(CONF_EXCLUDE, CONF_INCLUDE),
    _excl_incl_list_to_filter_dict,
)

_EXCL_INCL_LOWER_STRING_LIST = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_EXCLUDE, "incl_excl"): _LOWER_STRING_LIST,
            vol.Exclusive(CONF_INCLUDE, "incl_excl"): _LOWER_STRING_LIST,
        }
    ),
    cv.has_at_least_one_key(CONF_EXCLUDE, CONF_INCLUDE),
    _excl_incl_list_to_filter_dict,
)

_THRESHOLD = vol.All(vol.Coerce(int), vol.Range(min=1))

LIFE360_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_ACCOUNTS): vol.All(
                cv.ensure_list, [ACCOUNT_SCHEMA], vol.Length(min=1)
            ),
            vol.Optional(CONF_CIRCLES): _EXCL_INCL_LOWER_STRING_LIST,
            vol.Optional(CONF_DRIVING_SPEED): vol.Coerce(float),
            vol.Optional(CONF_ERROR_THRESHOLD): _THRESHOLD,
            vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
            vol.Optional(CONF_MAX_UPDATE_WAIT): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
            vol.Optional(CONF_MEMBERS): _EXCL_INCL_SLUG_LIST,
            vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): vol.All(
                vol.Any(None, cv.string), _prefix
            ),
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): cv.time_period,
            vol.Optional(CONF_SHOW_AS_STATE, default=[]): vol.All(
                cv.ensure_list, [vol.In(SHOW_AS_STATE_OPTS)]
            ),
            vol.Optional(CONF_WARNING_THRESHOLD): _THRESHOLD,
        }
    ),
    _thresholds,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: LIFE360_SCHEMA}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up integration."""
    conf = config.get(DOMAIN, LIFE360_SCHEMA({}))
    hass.data[DOMAIN] = {"config": conf, "apis": {}}
    discovery.load_platform(hass, DEVICE_TRACKER, DOMAIN, None, config)

    if CONF_ACCOUNTS not in conf:
        return True

    # Check existing config entries. For any that correspond to an entry in
    # configuration.yaml, and whose password has not changed, nothing needs to
    # be done with that config entry or that account from configuration.yaml.
    # But if the config entry was created by import and the account no longer
    # exists in configuration.yaml, or if the password has changed, then delete
    # that out-of-date config entry.
    already_configured = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        # Find corresponding configuration.yaml entry and its password.
        password = None
        for account in conf[CONF_ACCOUNTS]:
            if account[CONF_USERNAME] == entry.data[CONF_USERNAME]:
                password = account[CONF_PASSWORD]
        if password == entry.data[CONF_PASSWORD]:
            already_configured.append(entry.data[CONF_USERNAME])
            continue
        if (
            not password
            and entry.source == config_entries.SOURCE_IMPORT
            or password
            and password != entry.data[CONF_PASSWORD]
        ):
            hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))

    # Create config entries for accounts listed in configuration.
    for account in conf[CONF_ACCOUNTS]:
        if account[CONF_USERNAME] not in already_configured:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=account,
                )
            )
    return True


async def async_setup_entry(hass, entry):
    """Set up config entry."""
    hass.data[DOMAIN]["apis"][entry.data[CONF_USERNAME]] = get_api(
        entry.data[CONF_AUTHORIZATION]
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload config entry."""
    try:
        hass.data[DOMAIN]["apis"].pop(entry.data[CONF_USERNAME])
        return True
    except KeyError:
        return False
