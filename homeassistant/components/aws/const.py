"""Constant for AWS component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import AWSData

DOMAIN = "aws"

DATA_AWS: HassKey[AWSData] = HassKey(DOMAIN)

CONF_ACCESS_KEY_ID = "aws_access_key_id"
CONF_CONTEXT = "context"
CONF_CREDENTIAL_NAME = "credential_name"
CONF_CREDENTIALS = "credentials"
CONF_NOTIFY = "notify"
CONF_REGION = "region_name"
CONF_SECRET_ACCESS_KEY = "aws_secret_access_key"
CONF_VALIDATE = "validate"
