"""Host the definition for all services in the integration."""

import logging

from homeassistant.core import HomeAssistant, ServiceCall

from .constants import (
    ATTR_DOMAIN_NAME,
    ATTR_RECORD_NAME,
    ATTR_RECORD_TYPE,
    ATTR_RECORD_VALUE,
    MIN_TIME_BETWEEN_DOMAIN_UPDATES,
)
from .exceptions import DomainRecordAlreadySet, UpdateThrottled

_LOGGER = logging.getLogger(__name__)


def handle_update_domain_record(call: ServiceCall, hass: HomeAssistant) -> None:
    """Handle the service call to update a domain record."""
    # pylint: disable=import-outside-toplevel
    from . import DATA_DIGITAL_OCEAN

    domain_name = call.data[ATTR_DOMAIN_NAME]
    record_name = call.data[ATTR_RECORD_NAME]
    record_value = call.data[ATTR_RECORD_VALUE]
    record_type = call.data[ATTR_RECORD_TYPE]

    try:
        do_wrapper = hass.data[DATA_DIGITAL_OCEAN]
        updated = do_wrapper.update_domain_record(
            domain_name=domain_name,
            record_name=record_name,
            record_value=record_value,
            record_type=record_type,
        )
        if updated is None:  # pragma: no cover
            # HA's builtin Throttled decorator
            # returns None when the call is throttled
            raise UpdateThrottled(
                "Ignoring service call: You must wait at least"
                f"{MIN_TIME_BETWEEN_DOMAIN_UPDATES} between service calls"
            )
        _LOGGER.debug(
            "Successfully updated record {record_name} ({record_type})"
            "of domain {domain_name} to {record_value}",
            extra={
                "record_name": record_name,
                "record_type": record_type,
                "domain_name": domain_name,
                "record_value": record_value,
            },
        )
    except DomainRecordAlreadySet as e:
        # Avoiding this being tagged as error
        _LOGGER.debug(e)
