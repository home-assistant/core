"""Tests for the Modem Caller ID integration."""

from unittest.mock import patch

from phone_modem import DEFAULT_PORT

from homeassistant.const import CONF_DEVICE

CONF_DATA = {CONF_DEVICE: DEFAULT_PORT}

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
