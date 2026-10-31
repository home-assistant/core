"""Config flow for the Tile BLE integration."""

from typing import Any, override

import probatio
from pytile import async_login
from pytile.errors import InvalidAuthError, TileError
from pytile.tile import Tile

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_AUTH_KEY, CONF_TILE, DOMAIN, TILE_SERVICE_UUID
from .toa import TileBleAuthenticationError, TileBleDevice, TileBleError

STEP_ACCOUNT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


def _auth_key(tile: Tile) -> str | None:
    """Return the key used to authenticate with the Tile over Bluetooth."""
    # pytile does not expose the key yet.
    return tile._tile_data["result"].get("auth_key")  # noqa: SLF001


class TileBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tile BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._address: str | None = None
        self._tiles: dict[str, tuple[str, str]] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a Tile that Home Assistant can see."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            self._address = address
            return await self.async_step_account()

        current_addresses = self._async_current_ids()
        for service_info in async_discovered_service_info(self.hass, connectable=False):
            if (
                service_info.address not in current_addresses
                and TILE_SERVICE_UUID in service_info.service_uuids
            ):
                self._discovered_devices[service_info.address] = service_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Tiles all look alike, so list the closest ones first.
        devices = sorted(
            self._discovered_devices.values(),
            key=lambda service_info: service_info.rssi,
            reverse=True,
        )
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        {
                            service_info.address: (
                                f"{service_info.name} ({service_info.address},"
                                f" {service_info.rssi} dBm)"
                            )
                            for service_info in devices
                        }
                    )
                }
            ),
        )

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in to the Tile account to get the keys of its Tiles."""
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
                return await self.async_step_tile()

        return self.async_show_form(
            step_id="account", data_schema=STEP_ACCOUNT_SCHEMA, errors=errors
        )

    async def async_step_tile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick which of their Tiles they selected."""
        assert self._address is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            name, auth_key = self._tiles[user_input[CONF_TILE]]
            if not (
                ble_device := async_ble_device_from_address(
                    self.hass, self._address, connectable=True
                )
            ):
                errors["base"] = "cannot_connect"
            else:
                try:
                    await TileBleDevice(ble_device, auth_key).async_authenticate()
                except TileBleAuthenticationError:
                    errors["base"] = "wrong_tile"
                except TileBleError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=name, data={CONF_AUTH_KEY: auth_key}
                    )

        return self.async_show_form(
            step_id="tile",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_TILE): probatio.In(
                        {uuid: name for uuid, (name, _) in self._tiles.items()}
                    )
                }
            ),
            errors=errors,
        )
