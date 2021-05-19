"""Coordinator to fetch data from the Picnic API."""
import copy
from datetime import timedelta
import logging

import async_timeout
from python_picnic_api import PicnicAPI
from python_picnic_api.session import PicnicAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ADDRESS, CART_DATA, LAST_ORDER_DATA, SLOT_DATA


class PicnicUpdateCoordinator(DataUpdateCoordinator):
    """The coordinator to fetch data from the Picnic API at a set interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        picnic_api_client: PicnicAPI,
        config_entry: ConfigEntry,
    ):
        """Initialize the coordinator with the given Picnic API client."""
        self.picnic_api_client = picnic_api_client
        self.config_entry = config_entry
        self._user_address = None

        logger = logging.getLogger(__name__)
        super().__init__(
            hass,
            logger,
            name="Picnic coordinator",
            update_interval=timedelta(minutes=30),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                data = await self.hass.async_add_executor_job(self.fetch_data)

            # Update the auth token in the config entry if applicable
            self._update_auth_token()

            # Return the fetched data
            return data
        except ValueError as error:
            raise UpdateFailed(f"API response was malformed: {error}") from error
        except PicnicAuthError as error:
            raise ConfigEntryAuthFailed from error

    def fetch_data(self):
        """Fetch the data from the Picnic API and return a flat dict with only needed sensor data."""
        # Fetch from the API and pre-process the data
        cart = self.picnic_api_client.get_cart()
        last_order = self._get_last_order()

        if not cart or not last_order:
            raise UpdateFailed("API response doesn't contain expected data.")

        slot_data = self._get_slot_data(cart)

        return {
            ADDRESS: self._get_address(),
            CART_DATA: cart,
            SLOT_DATA: slot_data,
            LAST_ORDER_DATA: last_order,
        }

    def _get_address(self):
        """Get the address that identifies the Picnic service."""
        if self._user_address is None:
            address = self.picnic_api_client.get_user()["address"]
            self._user_address = f'{address["street"]} {address["house_number"]}{address["house_number_ext"]}'

        return self._user_address

    @staticmethod
    def _get_slot_data(cart: dict) -> dict:
        """Get the selected slot, if it's explicitly selected."""
        selected_slot = cart.get("selected_slot", {})
        available_slots = cart.get("delivery_slots", [])

        if selected_slot.get("state") == "EXPLICIT":
            slot_data = filter(
                lambda slot: slot.get("slot_id") == selected_slot.get("slot_id"),
                available_slots,
            )
            if slot_data:
                return next(slot_data)

        return {}

    def _get_last_order(self) -> dict:
        """Get data of the last order from the list of deliveries."""
        # Get the deliveries
        deliveries = self.picnic_api_client.get_deliveries(summary=True)
        if not deliveries:
            return {}

        # Determine the last order
        last_order = copy.deepcopy(deliveries[0])

        #  Get the position details if the order is not delivered yet
        delivery_position = {}
        if not last_order.get("delivery_time"):
            try:
                delivery_position = self.picnic_api_client.get_delivery_position(
                    last_order["delivery_id"]
                )
            except ValueError:
                # No information yet can mean an empty response
                pass

        # Determine the ETA, if available, the one from the delivery position API is more precise
        # but it's only available shortly before the actual delivery.
        last_order["eta"] = delivery_position.get(
            "eta_window", last_order.get("eta2", {})
        )

        # Determine the total price by adding up the total price of all sub-orders
        total_price = 0
        for order in last_order.get("orders", []):
            total_price += order.get("total_price", 0)

        # Sanitise the object
        last_order["total_price"] = total_price
        last_order.setdefault("delivery_time", {})
        if "eta2" in last_order:
            del last_order["eta2"]

        # Make a copy because some references are local
        return last_order

    @callback
    def _update_auth_token(self):
        """Set the updated authentication token."""
        updated_token = self.picnic_api_client.session.auth_token
        if self.config_entry.data.get(CONF_ACCESS_TOKEN) != updated_token:
            # Create an updated data dict
            data = {**self.config_entry.data, CONF_ACCESS_TOKEN: updated_token}

            # Update the config entry
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
