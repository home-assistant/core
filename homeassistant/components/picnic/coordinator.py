"""Coordinator to fetch data from the Picnic API."""

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from python_picnic_api2 import PicnicAPI
from python_picnic_api2.models import Cart, DeliverySummary, Slot
from python_picnic_api2.session import PicnicAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ADDRESS,
    CART_DATA,
    DEFAULT_UPDATE_INTERVAL,
    DELIVERY_UPDATE_INTERVAL,
    DELIVERY_WINDOW_LAG_TIME,
    DELIVERY_WINDOW_LEAD_TIME,
    LAST_ORDER_DATA,
    NEXT_DELIVERY_DATA,
    SLOT_DATA,
)

type PicnicConfigEntry = ConfigEntry[PicnicUpdateCoordinator]


@dataclass
class NextDeliveryData:
    """The next (current, undelivered) delivery, with its live ETA."""

    delivery: DeliverySummary | None = None
    eta_start: str | None = None
    eta_end: str | None = None
    estimated_arrival: int | None = None


@dataclass
class LastOrderData:
    """The most recent delivery, with its total price."""

    delivery: DeliverySummary | None = None
    total_price: int = 0
    delivery_time_start: str | None = None


class PicnicUpdateCoordinator(DataUpdateCoordinator):
    """The coordinator to fetch data from the Picnic API at a set interval."""

    config_entry: PicnicConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        picnic_api_client: PicnicAPI,
        config_entry: PicnicConfigEntry,
    ) -> None:
        """Initialize the coordinator with the given Picnic API client."""
        self.picnic_api_client = picnic_api_client
        self._user_address = None

        logger = logging.getLogger(__name__)
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name="Picnic coordinator",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        # Recompute up front so failed refreshes also relax the cadence
        if self.data:
            self.update_interval = self._get_update_interval(
                self.data.get(NEXT_DELIVERY_DATA)
            )

        try:
            async with asyncio.timeout(10):
                data = await self.hass.async_add_executor_job(self.fetch_data)

            # Update the auth token in the config entry if applicable
            self._update_auth_token()
        except ValueError as error:
            raise UpdateFailed(f"API response was malformed: {error}") from error
        except PicnicAuthError as error:
            raise ConfigEntryAuthFailed from error
        except TimeoutError as error:
            raise UpdateFailed(
                "Timeout while connecting to the Picnic API", retry_after=120
            ) from error

        self.update_interval = self._get_update_interval(data.get(NEXT_DELIVERY_DATA))

        # Return the fetched data
        return data

    @staticmethod
    def _get_update_interval(next_delivery: NextDeliveryData | None) -> timedelta:
        """Poll faster around the delivery so the live ETA is picked up in time."""
        if next_delivery is None or next_delivery.delivery is None:
            return DEFAULT_UPDATE_INTERVAL

        slot = next_delivery.delivery.slot

        start = end = None
        if next_delivery.eta_start and next_delivery.eta_end:
            start = dt_util.parse_datetime(next_delivery.eta_start)
            end = dt_util.parse_datetime(next_delivery.eta_end)
        if (start is None or end is None) and slot:
            start = dt_util.parse_datetime(str(slot.window_start))
            end = dt_util.parse_datetime(str(slot.window_end))

        if start is None or end is None:
            return DEFAULT_UPDATE_INTERVAL

        now = dt_util.utcnow()
        window_start = start - DELIVERY_WINDOW_LEAD_TIME

        if window_start <= now <= end + DELIVERY_WINDOW_LAG_TIME:
            return DELIVERY_UPDATE_INTERVAL

        if now < window_start:
            return max(
                DELIVERY_UPDATE_INTERVAL,
                min(DEFAULT_UPDATE_INTERVAL, window_start - now),
            )

        return DEFAULT_UPDATE_INTERVAL

    def fetch_data(self):
        """Fetch data from the Picnic API.

        Return a flat dict with only needed sensor data.
        """
        # Fetch from the API and pre-process the data
        if not (cart := self.picnic_api_client.get_cart()):
            raise UpdateFailed("API response doesn't contain expected data.")

        next_delivery, last_order = self._get_order_data()

        return {
            ADDRESS: self._get_address(),
            CART_DATA: cart,
            SLOT_DATA: self._get_slot_data(cart),
            NEXT_DELIVERY_DATA: next_delivery,
            LAST_ORDER_DATA: last_order,
        }

    def _get_address(self):
        """Get the address that identifies the Picnic service."""
        if self._user_address is None:
            address = self.picnic_api_client.get_user().address
            self._user_address = (
                f"{address.street} "
                f"{address.house_number}{address.house_number_ext or ''}"
            )

        return self._user_address

    @staticmethod
    def _get_slot_data(cart: Cart) -> Slot | None:
        """Get the selected slot, if it's explicitly selected."""
        selected_slot = cart.selected_slot

        if selected_slot and selected_slot.state == "EXPLICIT":
            for slot in cart.delivery_slots:
                if slot.slot_id == selected_slot.slot_id:
                    return slot

        return None

    @staticmethod
    def _delivery_time(delivery: DeliverySummary) -> dict | None:
        """Return the raw delivery-time window; not a field the library models."""
        return delivery.raw.get("delivery_time") if delivery.raw else None

    def _get_order_data(self) -> tuple[NextDeliveryData, LastOrderData]:
        """Get data of the last order from the list of deliveries."""
        # Get the deliveries
        deliveries = self.picnic_api_client.get_deliveries(summary=True)

        # Determine the last order and return empty data if there is none
        try:
            # Filter on status CURRENT and select the last
            # on the list which is the first one to be delivered
            next_deliveries = [d for d in deliveries if d.status == "CURRENT"]
            next_delivery = next_deliveries[-1] if next_deliveries else None
            last_order = deliveries[0] if deliveries else None
        except AttributeError, TypeError:
            # An AttributeError or TypeError indicate that the
            # response contains unexpected data
            return NextDeliveryData(), LastOrderData()

        if last_order is None:
            return NextDeliveryData(), LastOrderData()

        #  Get the next order's position details if there is an undelivered order
        delivery_position = {}
        if next_delivery and not self._delivery_time(next_delivery):
            # ValueError: If no information yet can mean an empty response
            with suppress(ValueError):
                delivery_position = self.picnic_api_client.get_delivery_position(
                    next_delivery.delivery_id
                )

        # Determine the ETA, if available, the one from the
        # delivery position API is more precise
        # but, it's only available shortly before the actual delivery.
        eta_window = delivery_position.get("eta_window") or {}
        eta2 = next_delivery.eta2 if next_delivery else None
        next_delivery_data = NextDeliveryData(
            delivery=next_delivery,
            eta_start=eta_window.get("start") or (eta2.start if eta2 else None),
            eta_end=eta_window.get("end") or (eta2.end if eta2 else None),
            # The position response's eta (unix timestamp in milliseconds) feeds
            # the estimated arrival sensor; the API only serves it shortly before
            # the delivery, so that sensor is unknown outside that window
            estimated_arrival=delivery_position.get("eta"),
        )

        # Determine the total price by adding up the total price of all sub-orders
        total_price = sum(order.total_price or 0 for order in last_order.orders)
        delivery_time = self._delivery_time(last_order)
        last_order_data = LastOrderData(
            delivery=last_order,
            total_price=total_price,
            delivery_time_start=delivery_time.get("start") if delivery_time else None,
        )

        return next_delivery_data, last_order_data

    @callback
    def _update_auth_token(self):
        """Set the updated authentication token."""
        updated_token = self.picnic_api_client.session.auth_token
        if self.config_entry.data.get(CONF_ACCESS_TOKEN) != updated_token:
            # Create an updated data dict
            data = {**self.config_entry.data, CONF_ACCESS_TOKEN: updated_token}

            # Update the config entry
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
