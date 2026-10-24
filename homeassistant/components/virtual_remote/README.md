# Virtual Remote

The Virtual Remote integration creates Home Assistant `remote` entities backed by existing Home Assistant `infrared` entities.

It allows infrared command sets to be grouped into reusable remote entities while infrared transmission remains handled by the linked infrared integration.

This makes it possible to use one infrared transmitter for multiple devices such as TVs, AV receivers, projectors, or air conditioners.

---

## Requirements

Virtual Remote requires at least one Home Assistant `infrared` entity provided by another integration.

The linked `infrared` entity is responsible for transmitting infrared commands through compatible hardware such as IR blasters or infrared emitters.

Compatible integrations include any integration that exposes Home Assistant `infrared` entities.

Examples include:
- iTach IP2IR
- ESPHome infrared transmitters
- any integration exposing Home Assistant `infrared` entities

---

## Features

- Create one virtual remote entity per config entry
- Associate each virtual remote with any Home Assistant `infrared` entity
- Edit a virtual remote's name or linked infrared entity
- Use standard Home Assistant `remote` services
- Store named infrared commands
- Add, edit, and remove commands through the options flow
- Support multiple infrared command formats
- Reuse one infrared transmitter across multiple virtual remotes

---

## Supported Command Formats

The integration supports the same command formats as the iTach IP2IR remote functionality.

Supported formats include:
- Pronto Hex
- Raw timing lists
- Raw timing objects
- Text-based timing formats

---

## Configuration

### Adding a Virtual Remote

1. Go to **Settings** → **Devices & services** → **Add integration**.
2. Search for **Virtual Remote**.
3. Select the infrared entity to use.
4. Enter a name for the virtual remote.

Each setup flow creates one virtual remote config entry. To create another virtual remote, add the Virtual Remote integration again.

---

## Managing a Virtual Remote

Open a Virtual Remote config entry's options to:
- Edit the virtual remote name or linked infrared entity
- Manage commands

If a virtual remote points to an infrared entity that no longer exists, the options flow still allows the remote to be edited and associated with a different infrared entity.

---

## Managing Commands

Commands are managed through the virtual remote config entry options flow.

Available operations:
- Add command
- Edit command
- Remove command

Command names are normalized to uppercase with underscores.

---

## Remote Services

The integration uses the standard Home Assistant `remote` entity services.

Example:

```yaml
service: remote.send_command
target:
  entity_id: remote.living_room_tv
data:
  command: POWER_ON
```

---

## Availability

A virtual remote is available when its linked infrared entity is available.

---

## Notes

- Multiple virtual remote config entries may share the same infrared entity.
- The integration does not directly communicate with physical hardware.
- Infrared transmission is handled by the linked infrared integration.
