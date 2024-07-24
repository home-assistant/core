"""Config flow for the Bayesian integration."""

from homeassistant import config_entries

from .const import DOMAIN


class BayesianConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1
