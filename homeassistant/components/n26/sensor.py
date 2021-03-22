"""Support for N26 bank account sensors."""
from homeassistant.components.sensor import SensorEntity

from . import DEFAULT_SCAN_INTERVAL, DOMAIN, timestamp_ms_to_date
from .const import DATA

SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL

ATTR_IBAN = "account"
ATTR_USABLE_BALANCE = "usable_balance"
ATTR_BANK_BALANCE = "bank_balance"

ATTR_ACC_OWNER_TITLE = "owner_title"
ATTR_ACC_OWNER_FIRST_NAME = "owner_first_name"
ATTR_ACC_OWNER_LAST_NAME = "owner_last_name"
ATTR_ACC_OWNER_GENDER = "owner_gender"
ATTR_ACC_OWNER_BIRTH_DATE = "owner_birth_date"
ATTR_ACC_OWNER_EMAIL = "owner_email"
ATTR_ACC_OWNER_PHONE_NUMBER = "owner_phone_number"

ICON_ACCOUNT = "mdi:currency-eur"
ICON_CARD = "mdi:credit-card"
ICON_SPACE = "mdi:crop-square"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the N26 sensor platform."""
    if discovery_info is None:
        return

    api_list = hass.data[DOMAIN][DATA]

    sensor_entities = []
    for api_data in api_list:
        sensor_entities.append(N26Account(api_data))

        for card in api_data.cards:
            sensor_entities.append(N26Card(api_data, card))

        for space in api_data.spaces["spaces"]:
            sensor_entities.append(N26Space(api_data, space))

    add_entities(sensor_entities)


class N26Account(SensorEntity):
    """Sensor for a N26 balance account.

    A balance account contains an amount of money (=balance). The amount may
    also be negative.
    """

    def __init__(self, api_data) -> None:
        """Initialize a N26 balance account."""
        self._data = api_data
        self._iban = self._data.balance["iban"]

    def update(self) -> None:
        """Get the current balance and currency for the account."""
        self._data.update_account()

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._iban[-4:]

    @property
    def name(self) -> str:
        """Friendly name of the sensor."""
        return f"n26_{self._iban[-4:]}"

    @property
    def state(self) -> float:
        """Return the balance of the account as state."""
        if self._data.balance is None:
            return None

        return self._data.balance.get("availableBalance")

    @property
    def unit_of_measurement(self) -> str:
        """Use the currency as unit of measurement."""
        if self._data.balance is None:
            return None

        return self._data.balance.get("currency")

    @property
    def extra_state_attributes(self) -> dict:
        """Additional attributes of the sensor."""
        attributes = {
            ATTR_IBAN: self._data.balance.get("iban"),
            ATTR_BANK_BALANCE: self._data.balance.get("bankBalance"),
            ATTR_USABLE_BALANCE: self._data.balance.get("usableBalance"),
            ATTR_ACC_OWNER_TITLE: self._data.account_info.get("title"),
            ATTR_ACC_OWNER_FIRST_NAME: self._data.account_info.get("kycFirstName"),
            ATTR_ACC_OWNER_LAST_NAME: self._data.account_info.get("kycLastName"),
            ATTR_ACC_OWNER_GENDER: self._data.account_info.get("gender"),
            ATTR_ACC_OWNER_BIRTH_DATE: timestamp_ms_to_date(
                self._data.account_info.get("birthDate")
            ),
            ATTR_ACC_OWNER_EMAIL: self._data.account_info.get("email"),
            ATTR_ACC_OWNER_PHONE_NUMBER: self._data.account_info.get(
                "mobilePhoneNumber"
            ),
        }

        for limit in self._data.limits:
            limit_attr_name = f"limit_{limit['limit'].lower()}"
            attributes[limit_attr_name] = limit["amount"]

        return attributes

    @property
    def icon(self) -> str:
        """Set the icon for the sensor."""
        return ICON_ACCOUNT


class N26Card(SensorEntity):
    """Sensor for a N26 card."""

    def __init__(self, api_data, card) -> None:
        """Initialize a N26 card."""
        self._data = api_data
        self._account_name = api_data.balance["iban"][-4:]
        self._card = card

    def update(self) -> None:
        """Get the current balance and currency for the account."""
        self._data.update_cards()
        self._card = self._data.card(self._card["id"], self._card)

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._card["id"]

    @property
    def name(self) -> str:
        """Friendly name of the sensor."""
        return f"{self._account_name.lower()}_card_{self._card['id']}"

    @property
    def state(self) -> float:
        """Return the balance of the account as state."""
        return self._card["status"]

    @property
    def extra_state_attributes(self) -> dict:
        """Additional attributes of the sensor."""
        attributes = {
            "apple_pay_eligible": self._card.get("applePayEligible"),
            "card_activated": timestamp_ms_to_date(self._card.get("cardActivated")),
            "card_product": self._card.get("cardProduct"),
            "card_product_type": self._card.get("cardProductType"),
            "card_settings_id": self._card.get("cardSettingsId"),
            "card_Type": self._card.get("cardType"),
            "design": self._card.get("design"),
            "exceet_actual_delivery_date": self._card.get("exceetActualDeliveryDate"),
            "exceet_card_status": self._card.get("exceetCardStatus"),
            "exceet_expected_delivery_date": self._card.get(
                "exceetExpectedDeliveryDate"
            ),
            "exceet_express_card_delivery": self._card.get("exceetExpressCardDelivery"),
            "exceet_express_card_delivery_email_sent": self._card.get(
                "exceetExpressCardDeliveryEmailSent"
            ),
            "exceet_express_card_delivery_tracking_id": self._card.get(
                "exceetExpressCardDeliveryTrackingId"
            ),
            "expiration_date": timestamp_ms_to_date(self._card.get("expirationDate")),
            "google_pay_eligible": self._card.get("googlePayEligible"),
            "masked_pan": self._card.get("maskedPan"),
            "membership": self._card.get("membership"),
            "mpts_card": self._card.get("mptsCard"),
            "pan": self._card.get("pan"),
            "pin_defined": timestamp_ms_to_date(self._card.get("pinDefined")),
            "username_on_card": self._card.get("usernameOnCard"),
        }
        return attributes

    @property
    def icon(self) -> str:
        """Set the icon for the sensor."""
        return ICON_CARD


class N26Space(SensorEntity):
    """Sensor for a N26 space."""

    def __init__(self, api_data, space) -> None:
        """Initialize a N26 space."""
        self._data = api_data
        self._space = space

    def update(self) -> None:
        """Get the current balance and currency for the account."""
        self._data.update_spaces()
        self._space = self._data.space(self._space["id"], self._space)

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"space_{self._data.balance['iban'][-4:]}_{self._space['name'].lower()}"

    @property
    def name(self) -> str:
        """Friendly name of the sensor."""
        return self._space["name"]

    @property
    def state(self) -> float:
        """Return the balance of the account as state."""
        return self._space["balance"]["availableBalance"]

    @property
    def unit_of_measurement(self) -> str:
        """Use the currency as unit of measurement."""
        return self._space["balance"]["currency"]

    @property
    def extra_state_attributes(self) -> dict:
        """Additional attributes of the sensor."""
        goal_value = ""
        if "goal" in self._space:
            goal_value = self._space.get("goal").get("amount")

        attributes = {
            "name": self._space.get("name"),
            "goal": goal_value,
            "background_image_url": self._space.get("backgroundImageUrl"),
            "image_url": self._space.get("imageUrl"),
            "is_card_attached": self._space.get("isCardAttached"),
            "is_hidden_from_balance": self._space.get("isHiddenFromBalance"),
            "is_locked": self._space.get("isLocked"),
            "is_primary": self._space.get("isPrimary"),
        }
        return attributes

    @property
    def icon(self) -> str:
        """Set the icon for the sensor."""
        return ICON_SPACE
