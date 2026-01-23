---
title: "Built-in intents"
toc_max_heading_level: 2
---

import intents from '!!yaml-loader!../intents/intents.yaml';

The following intents are **supported**:

<ul>
<li>
<>
{
  Object.entries(intents)
  .filter(([intent, info]) => info["supported"])
  .map(([intent, info]) => intent)
  .join(", ")
}
</>
</li>
</ul>

The following intents are **deprecated**:

 * HassOpenCover, HassCloseCover, HassToggle, HassHumidifierSetpoint, HassHumidifierMode, HassShoppingListLastItems

**Slots**

For *HassTurnOn* and *HassTurnOff*, the *slots* are optional. 

Possible slot combinations are:


| Slot combination        | Example                          |
| ----------------------- | ---------------------------------|
| name only               | table light                      |
| area only               | kitchen                          |
| area and name           | living room reading light        |
| area and domain         | kitchen lights                   |
| area and device class   | bathroom humidity                |
| device class and domain | carbon dioxide sensors           |


## Supported intents

<>
{
  Object.entries(intents)
  .filter(([intent, info]) => info["supported"])
  .map(
    ([intent, info]) =>
      <>
        <h3>{intent}</h3>
        <p>{info.description}</p>
        {info.slots &&
          (<b>Slots</b>) && (
          <ul>
            {Object.entries(info.slots).map(([slot, slotInfo]) => (
              <li>
                <b>{slot}</b> - {slotInfo.description + (slotInfo.required ? " (required)" : "")}
              </li>
            ))}
          </ul>
        )}
        <p><small>
          <a href={`https://www.home-assistant.io/integrations/${info.domain}`}>Provided by the <code>{info.domain}</code> integration.</a>
        </small></p>
      </>
  )
}
</>

## Deprecated intents

These are old intents that are not supported by template matching sentences and are planned to be removed or replaced.


### HassOpenCover

_Deprecated; use `HassTurnOn` instead._

Open a cover.

| Slot name | Type | Required | Description
| --------- | ---- | -------- | -----------
| name | string | Yes | Name of the cover entity to open.

### HassCloseCover

_Deprecated; use `HassTurnOff` instead._

Close a cover.

| Slot name | Type | Required | Description
| --------- | ---- | -------- | -----------
| name | string | Yes | Name of the cover entity to close.

### HassToggle

Toggle the state of an entity.

| Slot name | Type | Required | Description
| --------- | ---- | -------- | -----------
| name | string | Yes | Name of the entity to toggle.

### HassHumidifierSetpoint

Set target humidity.

| Slot name | Type | Required | Description
| --------- | ---- | -------- | -----------
| name | string | Yes | Name of the entity to control.
| humidity | integer, 0-100 | Yes | Target humidity to set.

### HassHumidifierMode

Set humidifier mode if supported by the humidifier.

| Slot name | Type | Required | Description
| --------- | ---- | -------- | -----------
| name | string | Yes | Name of the entity to control.
| mode | string | Yes | The mode to switch to.

### HassShoppingListLastItems

List the last 5 items on the shopping list.

_This intent has no slots._



[This page is automatically generated based on the Intents repository.](https://github.com/home-assistant/intents/blob/main/intents.yaml)
