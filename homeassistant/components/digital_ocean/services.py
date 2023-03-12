"""Host the definition for all services in the integration."""

import logging

from homeassistant.core import HomeAssistant, ServiceCall

from .constants import (
    MIN_TIME_BETWEEN_DOMAIN_UPDATES,
    SERVICE_PARAM_DOMAIN_NAME,
    SERVICE_PARAM_RECORD_NAME,
    SERVICE_PARAM_RECORD_TYPE,
    SERVICE_PARAM_RECORD_VALUE,
)
from .exceptions import DomainRecordAlreadySet, UpdateThrottled

_LOGGER = logging.getLogger(__name__)


def handle_update_domain_record(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the service call to update a domain record."""
    from . import DATA_DIGITAL_OCEAN  # pylint: disable=import-outside-toplevel

    domain_name = call.data[SERVICE_PARAM_DOMAIN_NAME]
    record_name = call.data[SERVICE_PARAM_RECORD_NAME]
    record_value = call.data[SERVICE_PARAM_RECORD_VALUE]
    record_type = call.data[SERVICE_PARAM_RECORD_TYPE]

    # TO-DO: Add validation

    try:
        do_wrapper = hass.data[DATA_DIGITAL_OCEAN]
        updated = do_wrapper.update_domain_record(
            domain_name=domain_name,
            record_name=record_name,
            record_value=record_value,
            record_type=record_type,
        )
        if updated is None:
            # HA's builtin Throttled function returns None when the call is skipped
            raise UpdateThrottled(
                "Ignoring service call: You must wait at least"
                f"{MIN_TIME_BETWEEN_DOMAIN_UPDATES} between service calls"
            )
        _LOGGER.debug(
            f"Successfully updated record {record_name} ({record_type})"
            f"of domain {domain_name} to {record_value}",
        )
    except DomainRecordAlreadySet as e:
        # Avoiding this being tagged as error
        _LOGGER.debug(e)
