# Integration Diagnostics

Platform exists as `homeassistant/components/<domain>/diagnostics.py`.

- **Required**: Implement diagnostic data collection
- **Implementation**:
  ```python
  TO_REDACT = [CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE]

  async def async_get_config_entry_diagnostics(
      hass: HomeAssistant, entry: MyConfigEntry
  ) -> dict[str, Any]:
      """Return diagnostics for a config entry."""
      return {
          "entry_data": async_redact_data(entry.data, TO_REDACT),
          "data": entry.runtime_data.data,
      }
  ```
- **Security**: Never expose passwords, tokens, or sensitive coordinates
