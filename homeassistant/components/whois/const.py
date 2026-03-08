"""Constants for the Whois integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "whois"
PLATFORMS = [Platform.SENSOR]

LOGGER = logging.getLogger(__package__)

SCAN_INTERVAL = timedelta(hours=24)

ATTR_EXPIRES = "expires"
ATTR_NAME_SERVERS = "name_servers"
ATTR_REGISTRAR = "registrar"
ATTR_UPDATED = "updated"

# Mapping of ICANN status codes to Home Assistant status types.
# From https://www.icann.org/resources/pages/epp-status-codes-2014-06-16-en
STATUS_TYPES = {
    "addPeriod": "add_period",
    "autoRenewPeriod": "auto_renew_period",
    "inactive": "inactive",
    "active": "active",
    "pendingCreate": "pending_create",
    "pendingRenew": "pending_renew",
    "pendingRestore": "pending_restore",
    "pendingTransfer": "pending_transfer",
    "pendingUpdate": "pending_update",
    "redemptionPeriod": "redemption_period",
    "renewPeriod": "renew_period",
    "serverDeleteProhibited": "server_delete_prohibited",
    "serverHold": "server_hold",
    "serverRenewProhibited": "server_renew_prohibited",
    "serverTransferProhibited": "server_transfer_prohibited",
    "serverUpdateProhibited": "server_update_prohibited",
    "transferPeriod": "transfer_period",
    "clientDeleteProhibited": "client_delete_prohibited",
    "clientHold": "client_hold",
    "clientRenewProhibited": "client_renew_prohibited",
    "clientTransferProhibited": "client_transfer_prohibited",
    "clientUpdateProhibited": "client_update_prohibited",
    "ok": "ok",
}
