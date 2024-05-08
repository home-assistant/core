"""Coordinator to fetch data from the Picnic API."""
import asyncio
from contextlib import suppress
import copy
from datetime import timedelta
import logging

from python_picnic_api import PicnicAPI
from python_picnic_api.session import PicnicAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ADDRESS, CART_DATA, LAST_ORDER_DATA, NEXT_DELIVERY_DATA, SLOT_DATA


class PicnicUpdateCoordinator(DataUpdateCoordinator):
    """The coordinator to fetch data from the Picnic API at a set interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        picnic_api_client: PicnicAPI,
        config_entry: ConfigEntry,
    ) -> None:
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
            # Note: TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(10):
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
        if not (cart := self.picnic_api_client.get_cart()):
            raise UpdateFailed("API response doesn't contain expected data.")

        next_delivery, last_order = self._get_order_data()
        slot_data = self._get_slot_data(cart)

        return {
            ADDRESS: self._get_address(),
            CART_DATA: cart,
            SLOT_DATA: slot_data,
            NEXT_DELIVERY_DATA: next_delivery,
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

    def _get_order_data(self) -> tuple[dict, dict]:
        """Get data of the last order from the list of deliveries."""
        # Get the deliveries
        deliveries = self.picnic_api_client.get_deliveries(summary=True)

        # Determine the last order and return an empty dict if there is none
        try:
            # Filter on status CURRENT and select the last on the list which is the first one to be delivered
            # Make a deepcopy because some references are local
            next_deliveries = list(
                filter(lambda d: d["status"] == "CURRENT", deliveries)
            )
            next_delivery = (
                copy.deepcopy(next_deliveries[-1]) if next_deliveries else {}
            )
            last_order = copy.deepcopy(deliveries[0]) if deliveries else {}
        except (KeyError, TypeError):
            # A KeyError or TypeError indicate that the response contains unexpected data
            return {}, {}

        #  Get the next order's position details if there is an undelivered order
        delivery_position = {}
        if next_delivery and not next_delivery.get("delivery_time"):
            # ValueError: If no information yet can mean an empty response
            with suppress(ValueError):
                delivery_position = self.picnic_api_client.get_delivery_position(
                    next_delivery["delivery_id"]
                )

        # Determine the ETA, if available, the one from the delivery position API is more precise
        # but, it's only available shortly before the actual delivery.
        next_delivery["eta"] = delivery_position.get(
            "eta_window", next_delivery.get("eta2", {})
        )
        if "eta2" in next_delivery:
            del next_delivery["eta2"]

        # Determine the total price by adding up the total price of all sub-orders
        total_price = 0
        for order in last_order.get("orders", []):
            total_price += order.get("total_price", 0)
        last_order["total_price"] = total_price

        # Make sure delivery_time is a dict
        last_order.setdefault("delivery_time", {})

        return next_delivery, last_order

    @callback
    def _update_auth_token(self):
        """Set the updated authentication token."""
        updated_token = self.picnic_api_client.session.auth_token
        if self.config_entry.data.get(CONF_ACCESS_TOKEN) != updated_token:
            # Create an updated data dict
            data = {**self.config_entry.data, CONF_ACCESS_TOKEN: updated_token}

            # Update the config entry
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
