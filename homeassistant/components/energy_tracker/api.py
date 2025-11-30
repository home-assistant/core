"""Home Assistant wrapper for Energy Tracker API client."""

from __future__ import annotations

import logging
from datetime import datetime

from energy_tracker_api import (
    AuthenticationError,
    CreateMeterReadingDto,
    EnergyTrackerAPIError,
    EnergyTrackerClient,
    ForbiddenError,
    NetworkError,
    RateLimitError,
    ResourceNotFoundError,
    TimeoutError,
    ValidationError,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


class EnergyTrackerApi:
    """Home Assistant wrapper for the Energy Tracker API client.

    Handles sending meter readings and error translation to Home Assistant exceptions.
    """

    def __init__(self, hass: HomeAssistant, token: str) -> None:
        """Initialize the EnergyTrackerApi wrapper.

        Args:
            hass: The Home Assistant instance.
            token: The Energy Tracker API access token.
        """
        self._hass = hass
        self._token = token
        self._client = EnergyTrackerClient(access_token=token)

    async def send_meter_reading(
        self,
        *,
        source_entity_id: str,
        device_id: str,
        value: float,
        timestamp: datetime,
        allow_rounding: bool = False,
    ) -> None:
        """Send a single meter reading to the Energy Tracker backend.

        Args:
            source_entity_id: Entity ID for logging purposes.
            device_id: The standard device ID in Energy Tracker.
            value: The meter reading value.
            timestamp: Timestamp for the reading.
            allow_rounding: Allow rounding to match meter precision.

        Raises:
            HomeAssistantError: If the API request fails.
        """
        log_prefix = f"[{source_entity_id}]"

        meter_reading = CreateMeterReadingDto(
            value=value,
            timestamp=timestamp,
        )

        try:
            await self._client.meter_readings.create(
                device_id=device_id,
                meter_reading=meter_reading,
                allow_rounding=allow_rounding,
            )
            LOGGER.info("%s Reading sent: %g", log_prefix, value)

        except ValidationError as err:
            # HTTP 400 - Bad Request
            LOGGER.warning("%s %s", log_prefix, err)
            msg = "; ".join(err.api_message) if err.api_message else "Invalid input"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="bad_request",
                translation_placeholders={"error": msg},
            ) from err

        except AuthenticationError as err:
            # HTTP 401 - Unauthorized
            ir.async_create_issue(
                self._hass,
                issue_id=f"auth_error_401_{self._token[:8]}",
                issue_domain=DOMAIN,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="auth_error_invalid_token",
            )
            LOGGER.error("%s %s", log_prefix, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err

        except ForbiddenError as err:
            # HTTP 403 - Forbidden
            ir.async_create_issue(
                self._hass,
                issue_id=f"auth_error_403_{self._token[:8]}",
                issue_domain=DOMAIN,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="auth_error_insufficient_permissions",
            )
            LOGGER.error("%s %s", log_prefix, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err

        except ResourceNotFoundError as err:
            # HTTP 404 - Not Found
            LOGGER.warning("%s %s", log_prefix, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
            ) from err

        except RateLimitError as err:
            # HTTP 429 - Rate Limit
            LOGGER.warning("%s %s", log_prefix, err)

            if err.retry_after:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="rate_limit",
                    translation_placeholders={"retry_after": str(err.retry_after)},
                ) from err
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limit_no_time",
            ) from err

        except TimeoutError as err:
            # Request timeout
            LOGGER.error("%s %s", log_prefix, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout",
            ) from err

        except NetworkError as err:
            # Network/connection errors
            LOGGER.error("%s %s", log_prefix, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="network_error",
            ) from err

        except EnergyTrackerAPIError as err:
            # Other API errors
            LOGGER.error("%s %s", log_prefix, err)
            msg = "; ".join(err.api_message) if err.api_message else str(err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="server_error",
                translation_placeholders={"error": msg},
            ) from err

        except Exception as err:
            # Unexpected errors
            LOGGER.exception("%s Unexpected error: %s", log_prefix, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(err)},
            ) from err
