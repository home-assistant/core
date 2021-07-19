"""Tests for the Modem Caller ID integration."""

from unittest.mock import patch

from homeassistant.components.modem_callerid.const import DEFAULT_DEVICE
from homeassistant.const import CONF_DEVICE

CONF_DATA = {CONF_DEVICE: DEFAULT_DEVICE}

IMPORT_DATA = {"sensor": {"platform": "modem_callerid"}}


def _patch_init_modem(mocked_modem):
    return patch(
        "homeassistant.components.modem_callerid.PhoneModem",
        return_value=mocked_modem,
    )


def _patch_config_flow_modem(mocked_modem):
    return patch(
        "homeassistant.components.modem_callerid.config_flow.PhoneModem",
        return_value=mocked_modem,
    )
