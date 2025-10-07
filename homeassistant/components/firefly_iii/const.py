"""Constants for the Firefly III integration."""

DOMAIN = "firefly_iii"

MANUFACTURER = "Firefly III"
NAME = "Firefly III"

ACCOUNT_ROLE_MAPPING = {
    "defaultAsset": "default_asset",
    "sharedAsset": "shared_asset",
    "savingAsset": "saving_asset",
    "ccAsset": "cc_asset",
    "cashWalletAsset": "cash_wallet_asset",
}

ACCOUNT_TYPE_ICONS = {
    "expense": "mdi:cash-minus",
    "asset": "mdi:account-cash",
    "revenue": "mdi:cash-plus",
    "liability": "mdi:hand-coin",
}
