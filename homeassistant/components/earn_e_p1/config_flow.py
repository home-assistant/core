"""Config flow for the EARN-E P1 Meter integration."""

import logging
from typing import TYPE_CHECKING, Any, override

from earn_e_p1 import EarnEP1Device, PacketType, discover, validate
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_SERIAL, DOMAIN, EARN_E_P1_DATA

_LOGGER = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10
VALIDATION_TIMEOUT = 65

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
    }
)


def _unique_id(device: EarnEP1Device) -> str:
    """Return the meter's equipment ID, or the dongle serial if it sends none.

    Keying on the meter keeps the entry when the dongle is swapped.
    """
    if TYPE_CHECKING:
        assert device.serial is not None
    return device.equipment_id or device.serial


class EarnEP1ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EARN-E P1 Meter."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: EarnEP1Device | None = None

    async def _async_discover(self) -> EarnEP1Device | None:
        """Discover an EARN-E device on the network."""
        data = self.hass.data.get(EARN_E_P1_DATA)
        if data is not None and (listener := data.listener) is not None:
            devices = await listener.discover(timeout=DISCOVERY_TIMEOUT)
        else:
            try:
                devices = await discover(timeout=DISCOVERY_TIMEOUT)
            except OSError:
                return None
        return devices[0] if devices else None

    async def _async_validate_host(self, host: str) -> EarnEP1Device | None:
        """Validate a host and wait for its serial and equipment ID.

        Uses the shared listener if available, otherwise creates a temporary one.
        Returns None on timeout.
        """
        data = self.hass.data.get(EARN_E_P1_DATA)
        if data is not None and (listener := data.listener) is not None:
            return await listener.validate(host, timeout=VALIDATION_TIMEOUT)
        return await validate(host, timeout=VALIDATION_TIMEOUT)

    async def _async_update_entry(
        self, entry: ConfigEntry, host: str, data_updates: dict[str, Any]
    ) -> ConfigFlowResult:
        """Point an existing entry at the device and abort."""
        # Lets a discovery flow record its discovery key on the entry.
        await self.async_set_unique_id(entry.unique_id, raise_on_progress=False)
        return self.async_update_reload_and_abort(
            entry,
            title=f"EARN-E P1 ({host})",
            data_updates=data_updates,
            reason="already_configured",
            reload_even_if_entry_is_unchanged=False,
        )

    async def _async_update_existing(
        self, device: EarnEP1Device
    ) -> ConfigFlowResult | None:
        """Point the entry for this meter or dongle at the device, if one exists."""
        entries = self._async_current_entries(include_ignore=False)
        # Fall back to the dongle for entries not yet moved onto the meter and
        # for meters that were replaced or stopped sending their equipment ID.
        entry = next(
            (entry for entry in entries if entry.unique_id == _unique_id(device)),
            None,
        ) or next(
            (entry for entry in entries if entry.data[CONF_SERIAL] == device.serial),
            None,
        )
        if entry is not None:
            return await self._async_update_entry(
                entry,
                device.host,
                {CONF_HOST: device.host, CONF_SERIAL: device.serial},
            )
        # Entries ignored before keying on the meter are keyed on the dongle.
        await self.async_set_unique_id(device.serial)
        self._abort_if_unique_id_configured()
        await self.async_set_unique_id(_unique_id(device))
        self._abort_if_unique_id_configured()
        return None

    def _async_create(self, device: EarnEP1Device) -> ConfigFlowResult:
        """Create the config entry for a validated device."""
        return self.async_create_entry(
            title=f"EARN-E P1 ({device.host})",
            data={CONF_HOST: device.host, CONF_SERIAL: device.serial},
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery of an EARN-E P1 meter."""
        ip = discovery_info.ip
        formatted_mac = format_mac(discovery_info.macaddress)

        # The dongle serial is its Wi-Fi MAC.
        for entry in self._async_current_entries(include_ignore=False):
            if format_mac(entry.data[CONF_SERIAL]) == formatted_mac:
                return await self._async_update_entry(entry, ip, {CONF_HOST: ip})

        try:
            device = await self._async_validate_host(ip)
        except OSError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error validating DHCP-discovered device")
            return self.async_abort(reason="unknown")

        if device is None:
            return self.async_abort(reason="cannot_connect")

        if result := await self._async_update_existing(device):
            return result

        self._discovered_device = device
        self.context["title_placeholders"] = {"host": ip}
        return await self.async_step_discovery_confirm()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self._async_validate_and_create(user_input)

        # Attempt auto-discovery before showing manual form
        device = await self._async_discover()
        if device:
            self._discovered_device = device
            return await self.async_step_discovery_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )

    async def _async_validate_and_create(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Validate manual IP entry and create config entry."""
        errors: dict[str, str] = {}
        host = user_input[CONF_HOST]

        try:
            device = await self._async_validate_host(host)
        except OSError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error validating device")
            errors["base"] = "unknown"
        else:
            if device is not None:
                if result := await self._async_update_existing(device):
                    return result
                return self._async_create(device)
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered device."""
        if TYPE_CHECKING:
            assert self._discovered_device is not None
        device = self._discovered_device

        if user_input is not None:
            # The equipment ID only arrives with the telegram, which the short
            # discovery window usually misses.
            if (
                device.serial is None
                or PacketType.TELEGRAM not in device.seen_packet_types
            ):
                try:
                    validated = await self._async_validate_host(device.host)
                except OSError:
                    validated = None
                except Exception:
                    _LOGGER.exception("Unexpected error validating device")
                    return self.async_abort(reason="unknown")

                if validated is None:
                    return self.async_abort(reason="cannot_connect")
                device = validated

            if result := await self._async_update_existing(device):
                return result
            return self._async_create(device)

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": device.host},
        )
