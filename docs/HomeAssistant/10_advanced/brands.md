---
title: "Brands"
---

A commercial brand may have several integrations which provide support for different offerings under that brand. Also, a brand may offer devices which comply with an IoT standard, for example Zigbee or Z-Wave.
As an example of the first case, there are multiple integrations providing support for different Google products, e.g. Google Calendar by the `google` integration and Google Sheets by the `google_sheets` integration.
As an example of the second case, Innovelli offers Zigbee and Z-Wave devices and doesn't need its own integration.


To make these integrations easier to find by the user, they should be collected in a file within the `homeassistant/brands`folder.

Examples:
```json
{
  "domain": "google",
  "name": "Google",
  "integrations": ["google", "google_sheets"]
}
```

```json
{
  "domain": "innovelli",
  "name": "Innovelli",
  "iot_standards": ["zigbee", "zwave"]
}
```

Or a minimal example that you can copy into your project:

```json
{
  "domain": "your_brand_domain",
  "name": "Your Brand",
  "integrations": [],
  "iot_standards": []
}
```

## Domain

The domain is a short name consisting of characters and underscores. This domain has to be unique and cannot be changed. Example of the domain for the Google brand: `google`. The domain key has to match the file name of the brand file it is in. If there's an integration with the same
domain, it has to be listed in the brand's `integrations`.

## Name

The name of the brand.

## Integrations

A list of integration domains implementing offerings of the brand.

## IoT standards

A list of IoT standards which are supported by devices of the brand. Possible values are `homekit`, `zigbee` and `zwave`. Note that a certain device may not support any of the listed IoT standards.
