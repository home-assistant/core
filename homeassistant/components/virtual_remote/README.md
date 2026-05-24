# Virtual Remote

The Virtual Remote integration creates Home Assistant `remote` entities backed by existing Home Assistant `infrared` entities.

It allows infrared command sets to be organized as reusable remote entities while infrared transmission remains handled by the linked infrared integration.

---

## Features

- Create one or more virtual remote entities
- Associate each virtual remote with any Home Assistant `infrared` entity
- Edit a virtual remote's name or linked infrared entity
- Use standard Home Assistant `remote` services
- Store named infrared commands
- Add, edit, and remove commands through the options flow
- Support multiple command formats
- Reuse one infrared transmitter across multiple virtual remotes

---

## Supported Command Formats

The integration supports the same command formats as the iTach IP2IR remote functionality.

Supported formats include:

- Pronto Hex
- Raw timing lists
- Raw timing objects
- Text timing formats

---

## Configuration

### Adding Virtual Remote

1. Go to **Settings** → **Devices & services** → **Add integration**.
2. Search for **Virtual Remote**.
3. Select the infrared entity to use.
4. Enter a name for the virtual remote.

The initial setup flow creates the first virtual remote. Additional remotes are added from the integration options.

---

## Managing Virtual Remotes

Open the Virtual Remote integration options to:

- Add virtual remote
- Edit virtual remote
- Remove virtual remote
- Manage commands

If a virtual remote points to an infrared entity that no longer exists, the options flow still allows the remote to be edited and associated with a different infrared entity.

---

## Managing Commands

Commands are managed through the integration options flow.

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

- Multiple virtual remotes may share the same infrared entity.
- The integration does not directly communicate with physical hardware.
- Infrared transmission is handled entirely by the linked infrared integration.
