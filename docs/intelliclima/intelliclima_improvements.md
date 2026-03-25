# Recent improvements

- Handling of None values:

    The IntelliClima API may return `None` for certain optional fields, for example `filter_from`.
    The integration now checks for `None` before using such fields when creating devices and entities, preventing runtime errors if a value is missing.

- Multi-house support

    After logging in with your IntelliClima username and password, all houses linked to your account are discovered automatically and all devices in those houses are added, instead of only the first house.

- Notes

  - No configuration changes are required
  - Fully backward compatible