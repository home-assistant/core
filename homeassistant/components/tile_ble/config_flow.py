"""Config flow for the Tile BLE integration."""

from typing import Any, override

import probatio
from pytile import async_login
from pytile.errors import InvalidAuthError, TileError
from pytile.tile import Tile
from tile_ble import (
    TILE_SERVICE_UUID,
    TileBleAuthenticationError,
    TileBleDevice,
    TileBleError,
    address_matches_tile_id,
    async_read_tile_id,
)

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_AUTH_KEY, DOMAIN

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class CannotConnect(HomeAssistantError):
    """Error to indicate the Tile cannot be connected to."""


class UnknownTile(HomeAssistantError):
    """Error to indicate the Tile is not in the Tile account."""


def _auth_key(tile: Tile) -> str | None:
    """Return the key used to authenticate with the Tile over Bluetooth."""
    # pytile does not expose the key yet.
    return tile._tile_data["result"].get("auth_key")  # noqa: SLF001


class TileBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tile BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._tiles: dict[str, tuple[str, str]] = {}
        self._devices: dict[str, str | None] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in to the Tile account to get the names and keys of its Tiles."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = await async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    session=async_get_clientsession(self.hass),
                )
                tiles = await client.async_get_tiles()
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except TileError:
                errors["base"] = "cannot_connect"
            else:
                self._tiles = {
                    tile.uuid: (tile.name, auth_key)
                    for tile in tiles.values()
                    if (auth_key := _auth_key(tile))
                }
                if not self._tiles:
                    return self.async_abort(reason="no_tiles")
                return await self.async_step_device()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one of their Tiles that Home Assistant can see."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            try:
                name, auth_key = await self._async_validate(address)
            except UnknownTile:
                errors["base"] = "unknown_tile"
            except TileBleAuthenticationError:
                errors["base"] = "wrong_tile"
            except CannotConnect, TileBleError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=name, data={CONF_AUTH_KEY: auth_key}
                )

        current_addresses = self._async_current_ids()
        devices = [
            (service_info, self._match_tile(service_info.address))
            for service_info in async_discovered_service_info(
                self.hass, connectable=False
            )
            if service_info.address not in current_addresses
            and TILE_SERVICE_UUID in service_info.service_uuids
        ]
        if not devices:
            return self.async_abort(reason="no_devices_found")

        # Tiles matched to the account first; the rest are only known by address.
        devices.sort(key=lambda device: (device[1] is None, -device[0].rssi))
        self._devices = {
            service_info.address: tile_id for service_info, tile_id in devices
        }
        return self.async_show_form(
            step_id="device",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        {
                            service_info.address: self._device_label(
                                service_info, tile_id
                            )
                            for service_info, tile_id in devices
                        }
                    )
                }
            ),
            errors=errors,
        )

    def _device_label(
        self, service_info: BluetoothServiceInfoBleak, tile_id: str | None
    ) -> str:
        """Return how a Tile is shown in the device list."""
        if tile_id:
            return f"{self._tiles[tile_id][0]} ({service_info.address})"
        return f"{service_info.address} ({service_info.rssi} dBm)"

    def _match_tile(self, address: str) -> str | None:
        """Return the ID of the account's Tile that uses this address."""
        return next(
            (
                tile_id
                for tile_id in self._tiles
                if address_matches_tile_id(address, tile_id)
            ),
            None,
        )

    async def _async_validate(self, address: str) -> tuple[str, str]:
        """Identify the Tile at this address and check that its key works."""
        if not (
            ble_device := async_ble_device_from_address(
                self.hass, address, connectable=True
            )
        ):
            raise CannotConnect
        tile_id = self._devices[address] or await async_read_tile_id(ble_device)
        if tile_id not in self._tiles:
            raise UnknownTile
        name, auth_key = self._tiles[tile_id]
        await TileBleDevice(ble_device, auth_key).async_authenticate()
        return name, auth_key
