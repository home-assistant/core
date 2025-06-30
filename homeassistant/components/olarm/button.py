"""Support for PGMS, link outputs through the Olarm cloud API."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OlarmConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add button a config entry."""

    # get coordinator
    coordinator = config_entry.runtime_data

    # init buttons
    buttons: list[OlarmButton] = []

    # load zones if bypass entities are enabled
    if config_entry.data.get("load_zones_bypass_entities"):
        _create_zone_buttons(
            coordinator,
            config_entry.data["device_id"],
            buttons,
        )

    # cycle through PGMS (pulse, open and close)
    _create_pgm_buttons(coordinator, config_entry.data["device_id"], buttons)

    # cycle through LINK outputs / relays
    _create_link_output_buttons(coordinator, config_entry.data["device_id"], buttons)
    _create_link_relay_buttons(coordinator, config_entry.data["device_id"], buttons)

    # cycle through MAX outputs
    _create_max_output_buttons(coordinator, config_entry.data["device_id"], buttons)

    async_add_entities(buttons)


def _create_zone_buttons(
    coordinator: Any, device_id: str, buttons: list[OlarmButton]
) -> None:
    """Create zone bypass/unbypass buttons."""
    if coordinator.device_profile is not None and coordinator.device_state is not None:
        for zone_index, _ in enumerate(coordinator.device_state.get("zones")):
            buttons.append(
                OlarmButton(
                    coordinator,
                    device_id,
                    "zone_bypass",
                    zone_index,
                    coordinator.device_profile.get("zonesLabels")[zone_index],
                )
            )
            buttons.append(
                OlarmButton(
                    coordinator,
                    device_id,
                    "zone_unbypass",
                    zone_index,
                    coordinator.device_profile.get("zonesLabels")[zone_index],
                )
            )


def _create_pgm_buttons(
    coordinator: Any, device_id: str, buttons: list[OlarmButton]
) -> None:
    """Create PGM buttons."""
    if (
        coordinator.device_profile is not None
        and coordinator.device_profile.get("pgmControl") is not None
    ):
        for pgm_index, pgm_control in enumerate(
            coordinator.device_profile.get("pgmControl")
        ):
            if pgm_control[0] == "1":
                # open / close button
                if pgm_control[1] == "1":
                    buttons.append(
                        OlarmButton(
                            coordinator,
                            device_id,
                            "pgm_open",
                            pgm_index,
                            coordinator.device_profile.get("pgmLabels")[pgm_index],
                        )
                    )
                    buttons.append(
                        OlarmButton(
                            coordinator,
                            device_id,
                            "pgm_close",
                            pgm_index,
                            coordinator.device_profile.get("pgmLabels")[pgm_index],
                        )
                    )
                # pulse button
                if pgm_control[2] == "1":
                    buttons.append(
                        OlarmButton(
                            coordinator,
                            device_id,
                            "pgm_pulse",
                            pgm_index,
                            coordinator.device_profile.get("pgmLabels")[pgm_index],
                        )
                    )

        # cycle through utility keys
        for ukey_index, ukeys_control in enumerate(
            coordinator.device_profile.get("ukeysControl")
        ):
            if ukeys_control == 1:
                buttons.append(
                    OlarmButton(
                        coordinator,
                        device_id,
                        "ukey",
                        ukey_index,
                        coordinator.device_profile.get("ukeysLabels")[ukey_index],
                    )
                )


def _create_link_output_buttons(
    coordinator: Any, device_id: str, buttons: list[OlarmButton]
) -> None:
    """Create LINK output buttons."""
    if (
        coordinator.device_profile_links is not None
        and len(coordinator.device_profile_links) > 0
    ):
        for link_id, link_data in coordinator.device_profile_links.items():
            link_name = link_data.get("name", "Unnamed Link")
            io_outputs = link_data.get("io", [])

            for io_index, io in enumerate(io_outputs):
                # Only create buttons for enabled outputs
                if io.get("enabled") and io.get("type") == "output":
                    # latch need open & close buttons
                    if io.get("outputMode") == "latch":
                        buttons.append(
                            OlarmButton(
                                coordinator,
                                device_id,
                                "link_output_open",
                                io_index,
                                io.get("label"),
                                link_id,
                                link_name,
                            )
                        )
                        buttons.append(
                            OlarmButton(
                                coordinator,
                                device_id,
                                "link_output_close",
                                io_index,
                                io.get("label"),
                                link_id,
                                link_name,
                            )
                        )
                    elif io.get("outputMode") == "pulse":
                        buttons.append(
                            OlarmButton(
                                coordinator,
                                device_id,
                                "link_output_pulse",
                                io_index,
                                io.get("label"),
                                link_id,
                                link_name,
                            )
                        )


def _create_link_relay_buttons(
    coordinator: Any, device_id: str, buttons: list[OlarmButton]
) -> None:
    """Create LINK relay buttons."""
    if (
        coordinator.device_profile_links is not None
        and len(coordinator.device_profile_links) > 0
    ):
        for link_id, link_data in coordinator.device_profile_links.items():
            link_name = link_data.get("name", "Unnamed Link")
            # cycle through LINK relays
            relay_items = link_data.get("relays", [])
            for relay_index, relay in enumerate(relay_items):
                # Only create buttons for enabled relays
                if relay.get("enabled"):
                    # latch need open & close buttons
                    if relay.get("relayMode") == "latch":
                        buttons.append(
                            OlarmButton(
                                coordinator,
                                device_id,
                                "link_relay_unlatch",
                                relay_index,
                                relay.get("label"),
                                link_id,
                                link_name,
                            )
                        )
                        buttons.append(
                            OlarmButton(
                                coordinator,
                                device_id,
                                "link_relay_latch",
                                relay_index,
                                relay.get("label"),
                                link_id,
                                link_name,
                            )
                        )
                    elif relay.get("relayMode") == "pulse":
                        buttons.append(
                            OlarmButton(
                                coordinator,
                                device_id,
                                "link_relay_pulse",
                                relay_index,
                                relay.get("label"),
                                link_id,
                                link_name,
                            )
                        )


def _create_max_output_buttons(
    coordinator: Any, device_id: str, buttons: list[OlarmButton]
) -> None:
    """Create MAX output buttons."""
    if (
        coordinator.device_profile_io is not None
        and coordinator.device_profile_io.get("io") is not None
    ):
        for io_index, io in enumerate(coordinator.device_profile_io.get("io")):
            # Only create buttons for enabled outputs
            if io.get("enabled") and io.get("type") == "output":
                # latch need open & close buttons
                if io.get("outputMode") == "latch":
                    buttons.append(
                        OlarmButton(
                            coordinator,
                            device_id,
                            "max_output_open",
                            io_index,
                            io.get("label"),
                        )
                    )
                    buttons.append(
                        OlarmButton(
                            coordinator,
                            device_id,
                            "max_output_close",
                            io_index,
                            io.get("label"),
                        )
                    )
                elif io.get("outputMode") == "pulse":
                    buttons.append(
                        OlarmButton(
                            coordinator,
                            device_id,
                            "max_output_pulse",
                            io_index,
                            io.get("label"),
                        )
                    )


class OlarmButton(ButtonEntity):
    """Define a Button."""

    _attr_name: str

    def __init__(
        self,
        coordinator: Any,
        device_id: str,
        button_type: str,
        button_index: int,
        button_label: str,
        link_id: str | None = None,
        link_name: str | None = "",
    ) -> None:
        """Init the class."""

        # save reference to coordinator
        self._coordinator = coordinator

        button_type_str_map = {
            "zone_bypass": "Zone Bypass",
            "zone_unbypass": "Zone Unbypass",
            "pgm_open": "PGM Open",
            "pgm_close": "PGM Close",
            "pgm_pulse": "PGM Pulse",
            "ukey": "Utility Key",
            "link_output_open": "LINK Output Open",
            "link_output_close": "LINK Output Close",
            "link_output_pulse": "LINK Output Pulse",
            "link_relay_unlatch": "LINK Relay Unlatch",
            "link_relay_latch": "LINK Relay Latch",
            "link_relay_pulse": "LINK Relay Pulse",
            "max_output_open": "MAX Output Open",
            "max_output_close": "MAX Output Close",
            "max_output_pulse": "MAX Output Pulse",
        }

        # attributes
        self._attr_has_entity_name = True
        self._attr_name = f"{link_name} {button_type_str_map[button_type]} {button_index + 1:02} - {button_label}"
        self._attr_unique_id = f"{device_id}.{button_type}.{button_index}"
        # if link need to include address in unique id
        if link_id is not None:
            self._attr_unique_id = f"{device_id}_{link_id}.{button_type}.{button_index}"

        # Set device info - extract main device ID for LINK devices
        main_device_id = device_id.split("_")[0]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, main_device_id)},
            name=coordinator.device_name,
            manufacturer="Olarm",
        )

        # custom attributes
        self.device_id = device_id
        self.button_type = button_type
        self.button_index = button_index
        self.button_label = button_label
        self.link_id = link_id

        _LOGGER.debug(
            "Button: init %s -> %s -> %s -> %s",
            self._attr_name,
            self.button_type,
            self.button_index,
            self.button_label,
        )

    async def async_press(self) -> None:
        """Handle the button press to send PGM command."""

        # send command via API
        if self.button_type == "zone_bypass":
            await self._coordinator.send_device_zone_cmd(
                self.device_id, "bypass", self.button_index
            )
        elif self.button_type == "zone_unbypass":
            await self._coordinator.send_device_zone_cmd(
                self.device_id, "unbypass", self.button_index
            )
        if self.button_type == "pgm_open":
            await self._coordinator.send_device_pgm_cmd(
                self.device_id, "open", self.button_index
            )
        elif self.button_type == "pgm_close":
            await self._coordinator.send_device_pgm_cmd(
                self.device_id, "close", self.button_index
            )
        elif self.button_type == "pgm_pulse":
            await self._coordinator.send_device_pgm_cmd(
                self.device_id, "pulse", self.button_index
            )
        elif self.button_type == "ukey":
            await self._coordinator.send_device_ukey_cmd(
                self.device_id, self.button_index
            )
        elif self.button_type == "link_output_open":
            await self._coordinator.send_device_link_output_cmd(
                self.device_id, self.link_id, "open", self.button_index
            )
        elif self.button_type == "link_output_close":
            await self._coordinator.send_device_link_output_cmd(
                self.device_id, self.link_id, "close", self.button_index
            )
        elif self.button_type == "link_output_pulse":
            await self._coordinator.send_device_link_output_cmd(
                self.device_id, self.link_id, "pulse", self.button_index
            )
        elif self.button_type == "link_relay_unlatch":
            await self._coordinator.send_device_link_relay_cmd(
                self.device_id, self.link_id, "unlatch", self.button_index
            )
        elif self.button_type == "link_relay_latch":
            await self._coordinator.send_device_link_relay_cmd(
                self.device_id, self.link_id, "latch", self.button_index
            )
        elif self.button_type == "link_relay_pulse":
            await self._coordinator.send_device_link_relay_cmd(
                self.device_id, self.link_id, "pulse", self.button_index
            )
        elif self.button_type == "max_output_open":
            await self._coordinator.send_device_max_output_cmd(
                self.device_id, "open", self.button_index
            )
        elif self.button_type == "max_output_close":
            await self._coordinator.send_device_max_output_cmd(
                self.device_id, "close", self.button_index
            )
        elif self.button_type == "max_output_pulse":
            await self._coordinator.send_device_max_output_cmd(
                self.device_id, "pulse", self.button_index
            )

        # self._attr_icon = "mdi:check-circle"
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """The name of the zone from the Alarm Panel."""
        return self._attr_name
