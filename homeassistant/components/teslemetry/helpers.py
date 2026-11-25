"""Teslemetry helper functions."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, cast

from aiohttp import ClientError
from tesla_fleet_api.exceptions import InsufficientCredits, TeslaFleetError
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth
from tesla_fleet_api.tesla.powerwall import (
    PowerwallAuthenticationError,
    PowerwallClient,
    PowerwallCommandError,
    PowerwallError,
    PowerwallNotSupportedError,
)
from tesla_fleet_api.teslemetry import EnergySite, Vehicle
from tesla_fleet_api.teslemetry.energysite import TeslemetryEnergySite
from teslemetry_stream.const import CreditsEvent

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BLE_PARENT_KEY,
    BLE_PARENT_LOCK_KEY,
    CREDITS_URL,
    DOMAIN,
    ISSUE_GATEWAY_NOT_FOUND,
    ISSUE_INSUFFICIENT_CREDITS,
    LOGGER,
    VEHICLE_KEY_FILE,
)

if TYPE_CHECKING:
    from .models import TeslemetryConfigEntry

# A credits event clears the repair only with this much headroom, so an account
# that is still nearly exhausted keeps it.
CREDITS_BALANCE_THRESHOLD = 25
CREDITS_QUOTA_FRACTION_THRESHOLD = 0.95

GATEWAY_OUT_OF_RANGE = 11


class PowerwallKeyRejectedError(Exception):
    """Signal that the gateway refused a v1r-signed read with our RSA key."""


def gateway_issue_id(entry_id: str, site_id: int) -> str:
    """Return the repair issue id for a site whose local gateway was not found."""
    return f"{ISSUE_GATEWAY_NOT_FOUND}_{entry_id}_{site_id}"


def cloud_energy_site(api: EnergySite | EnergySiteRouter) -> TeslemetryEnergySite:
    """Return the cloud energy-site API behind a site's resolved api.

    Pairing and gateway discovery always go through the Teslemetry cloud; a
    paired site's api is an EnergySiteRouter, so unwrap its cloud secondary
    rather than routing to the local Powerwall primary.
    """
    return cast(
        TeslemetryEnergySite,
        api.secondary if isinstance(api, EnergySiteRouter) else api,
    )


def create_powerwall_client(
    hass: HomeAssistant, host: str, password: str, key_pem: bytes
) -> PowerwallClient:
    """Return a local Powerwall gateway client on the shared HTTP session."""
    return PowerwallClient(
        host=host,
        gateway_password=password,
        rsa_private_key_pem=key_pem,
        session=async_get_clientsession(hass),
    )


async def async_verify_local_gateway(
    hass: HomeAssistant, host: str, password: str, key_pem: bytes
) -> None:
    """Prove the LAN connection and the RSA key against the gateway."""
    async with create_powerwall_client(hass, host, password, key_pem) as client:
        await client.connect()
        try:
            # connect() passed the password, so a failure here is key rejection.
            await client.get_status()
        except PowerwallAuthenticationError as err:
            raise PowerwallKeyRejectedError from err


async def async_get_ble_parent(hass: HomeAssistant) -> TeslaBluetooth:
    """Return a shared TeslaBluetooth parent with the private key loaded."""
    lock: asyncio.Lock = hass.data.setdefault(BLE_PARENT_LOCK_KEY, asyncio.Lock())
    async with lock:
        existing: TeslaBluetooth | None = hass.data.get(BLE_PARENT_KEY)
        if existing is not None:
            return existing
        parent = TeslaBluetooth()
        await parent.get_private_key(hass.config.path(VEHICLE_KEY_FILE))
        hass.data[BLE_PARENT_KEY] = parent
        return parent


def flatten(
    data: dict[str, Any],
    parent: str | None = None,
    *,
    skip_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Flatten the data structure."""
    result = {}
    for key, value in data.items():
        skip = skip_keys and key in skip_keys
        if parent:
            key = f"{parent}_{key}"
        if isinstance(value, dict) and not skip:
            result.update(flatten(value, key, skip_keys=skip_keys))
        else:
            result[key] = value
    return result


def insufficient_credits_issue_id(entry: TeslemetryConfigEntry) -> str:
    """Return the insufficient credits issue id of a config entry."""
    return f"{ISSUE_INSUFFICIENT_CREDITS}_{entry.entry_id}"


async def handle_command(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    command: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    """Handle a command."""
    try:
        result = await command
    except InsufficientCredits as e:
        ir.async_create_issue(
            hass,
            DOMAIN,
            insufficient_credits_issue_id(entry),
            config_entry_id=entry.entry_id,
            is_fixable=False,
            # Setup does not check credits, so nothing would raise it again
            # after a restart while the account is still short.
            is_persistent=True,
            learn_more_url=CREDITS_URL,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_INSUFFICIENT_CREDITS,
            translation_placeholders={
                "account": entry.title,
                "credits_url": CREDITS_URL,
            },
        )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=ISSUE_INSUFFICIENT_CREDITS,
        ) from e
    except TeslaFleetError as e:
        message = e.message
        if isinstance(e.data, dict):
            # An error equal to the class key is the machine code that selected it
            if (error := e.data.get("error")) == e.key:
                error = None
            message = e.data.get("error_description") or error or message
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_exception",
            translation_placeholders={"message": message},
        ) from e
    except (ClientError, TimeoutError) as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_connection_error",
        ) from e
    LOGGER.debug("Command result: %s", result)
    return result


async def handle_energy_site_command(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    command: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    """Handle a command that a paired energy site may send to its local Powerwall gateway."""
    try:
        return await handle_command(hass, entry, command)
    except PowerwallNotSupportedError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="local_command_not_supported",
        ) from e
    except PowerwallCommandError as e:
        # pylint: disable-next=home-assistant-log-and-raise
        LOGGER.error("Local Powerwall gateway command failed: %s", e)
        if e.code == GATEWAY_OUT_OF_RANGE:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="local_command_out_of_range",
            ) from e
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="local_command_failed",
        ) from e
    except PowerwallError as e:
        # pylint: disable-next=home-assistant-log-and-raise
        LOGGER.error("Local Powerwall gateway command failed: %s", e)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="local_command_failed",
        ) from e


async def handle_vehicle_command(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    command: Awaitable[dict[str, Any]],
) -> Any:
    """Handle a vehicle command."""
    result = await handle_command(hass, entry, command)
    if (response := result.get("response")) is None:
        if error := result.get("error"):
            # No response with error
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={"error": error},
            )
        # No response without error (unexpected)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_no_response"
        )
    if (result := response.get("result")) is not True:
        if reason := response.get("reason"):
            if reason in ("already_set", "is_charging", "not_charging", "requested"):
                # Reason is acceptable
                return result
            # Result of false with reason
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_reason",
                translation_placeholders={"reason": reason},
            )
        # Result of false without reason (unexpected)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_no_result"
        )
    # Response with result of true
    return result


async def async_set_charge_on_solar(
    send: Callable[[Awaitable[dict[str, Any]]], Awaitable[Any]],
    api: Vehicle,
    *,
    enabled: bool,
    lower_charge_limit: int,
    charge_limit_soc: int | None,
) -> int:
    """Send a charge-on-solar command, omitting the upper bound if it isn't known yet.

    Returns the lower limit actually sent, clamped to the upper bound if it is known.
    """
    if charge_limit_soc is not None:
        lower_charge_limit = min(lower_charge_limit, charge_limit_soc)
    await send(
        api.charge_on_solar(
            enabled=enabled,
            lower_charge_limit=lower_charge_limit,
            upper_charge_limit=charge_limit_soc,
        )
    )
    return lower_charge_limit


@callback
def async_handle_credits(
    hass: HomeAssistant, entry: TeslemetryConfigEntry, credits: CreditsEvent
) -> None:
    """Delete the insufficient credits issue once credits are available."""
    # The quota is empty for an account without one.
    fraction = credits.quota.get("fraction")
    if credits.balance > CREDITS_BALANCE_THRESHOLD or (
        fraction is not None and fraction < CREDITS_QUOTA_FRACTION_THRESHOLD
    ):
        ir.async_delete_issue(hass, DOMAIN, insufficient_credits_issue_id(entry))


@callback
def async_remove_stale_vehicle_entities(
    hass: HomeAssistant,
    config_entry_id: str,
    domain: str,
    vins: set[str],
    valid_unique_ids: set[str],
) -> None:
    """Remove registry entries for vehicle entities that are no longer created."""
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, config_entry_id):
        if (
            entity.domain == domain
            and entity.unique_id not in valid_unique_ids
            and any(entity.unique_id.startswith(f"{vin}-") for vin in vins)
        ):
            entity_registry.async_remove(entity.entity_id)


@callback
def async_update_device_sw_version(
    hass: HomeAssistant, identifier: str, config_entry_id: str, sw_version: str
) -> None:
    """Update the software version in the device registry."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get_device_by_identifier(
        (DOMAIN, identifier), config_entry_id
    ):
        if device.sw_version != sw_version:
            dev_reg.async_update_device(device.id, sw_version=sw_version)
