# Add Samsung Infrared integration

## Proposed change

This PR adds a new integration for controlling Samsung TVs via infrared transmitters, leveraging the existing Infrared integration platform. The integration provides a media player entity with comprehensive TV control functionality.

**Note:** This is the initial implementation focusing on the media player platform. Additional platforms (like buttons for individual TV functions) may be added in future PRs based on community feedback.

## Type of change

- [ ] Dependency upgrade
- [ ] Bugfix (non-breaking change which fixes an issue)
- [x] New integration (thank you!)
- [ ] New feature (which adds functionality to an existing integration)
- [ ] Breaking change (fix/feature causing existing functionality to break)
- [ ] Code quality improvements to existing code or addition of tests

## Features

### Platforms

- **Media Player**: Comprehensive TV control with power, volume, channel, and playback features
  - Turn on/off
  - Volume up/down/mute
  - Channel up/down
  - Play/pause/stop

### Key Implementation Details

- Uses `infrared-protocols` library (version 5.1.0) for Samsung TV IR codes
- Follows Home Assistant quality scale requirements (Bronze level)
- Implements config flow for easy setup
- Uses standard translation patterns
- Entities follow standard naming conventions with proper entity name support
- Comprehensive test coverage including snapshots and command verification
- Leverages shared test infrastructure from Infrared integration

### Design Decisions

- Initial release focuses on media player platform for core TV functionality
- Media player provides all essential TV operations through standard Home Assistant interfaces
- Entity availability follows the underlying infrared entity state
- Uses Samsung32 protocol with address 0x07 from infrared-protocols library
- Future enhancements may include additional platforms based on user feedback

## Example configuration

```yaml
# Configuration via UI (Config Flow)
# Navigate to Settings > Devices & Services > Add Integration > Samsung Infrared
# Select your infrared transmitter entity and device type
```

## Additional information

- Depends on: Infrared integration (must be set up first)
- Quality Scale: Bronze
- IOT Class: Assumed State (IR commands are one-way)
- Integration Type: Device
- Protocol: Samsung32 (address 0x07)
- Library: infrared-protocols 5.1.0

### Translation Keys

This integration uses standard Home Assistant translation patterns with minimal custom strings for better internationalization support and consistency across all languages.

### Comparison with LG Infrared

The Samsung Infrared integration follows similar patterns to the LG Infrared integration:
- Clean media player implementation for TV control
- Uses shared test infrastructure from #170296
- Updated to latest infrared-protocols library (5.1.0)
- Focuses on essential TV functionality in initial release

## Related PRs

- Requires infrared-protocols 5.1.0 bump (separate PR)
- Uses shared test infrastructure from #170296

## Commit History

This PR includes a single, clean commit:
1. Add Samsung Infrared integration (media player only)

The commit includes full implementation with tests and maintains passing checks throughout.

## Checklist

- [x] The code change is tested and works locally.
- [x] Local tests pass (18 tests, 2 snapshots)
- [x] There is no commented out code in this PR.
- [x] I have followed the [development checklist][dev-checklist]
- [x] I have followed the [perfect PR recommendations][perfect-pr]
- [x] The code has been formatted using Ruff (`ruff format homeassistant tests`)
- [x] Tests have been added to verify that the new code works.

If user exposed functionality or configuration variables are added/changed:

- [x] Documentation added/updated for [www.home-assistant.io][docs-repository] *(Will be added post-merge)*

If the code communicates with devices, web services, or third-party tools:

- [x] The [manifest file][manifest-docs] has all fields filled out correctly.
- [x] New or updated dependencies have been added to `requirements_all.txt`. *(Uses existing infrared-protocols dependency)*
- [x] Untested files have been added to `.coveragerc`. *(N/A - full test coverage)*

[dev-checklist]: https://developers.home-assistant.io/docs/development_checklist
[perfect-pr]: https://developers.home-assistant.io/docs/review-process#perfect-pr
[docs-repository]: https://github.com/home-assistant/home-assistant.io
[manifest-docs]: https://developers.home-assistant.io/docs/creating_integration_manifest/

## Testing

All tests pass:
- 18 tests total
- 2 snapshots validated
- Test coverage includes:
  - Config flow (user flow, already configured, no emitters, entity name)
  - Media player entity (10 actions with correct IR codes)
  - Entity availability tracking
  - Device and entity registry validation
  - Snapshot validation for all entities

### Test Infrastructure

This integration leverages the shared test infrastructure introduced in #170296:
- Uses global `init_infrared` fixture for Infrared component setup
- Uses global `mock_infrared_entity` fixture for mock IR entity
- Imports `MockInfraredEntity` from `tests.components.infrared.common`
- Imports `ENTITY_ID` constant from `tests.components.infrared`

This approach ensures consistency with other infrared-based integrations and reduces test code duplication.

## Screenshots

N/A - This is a backend integration without UI elements (uses standard config flow and entity cards).

---

## Notes for Reviewers

- This PR depends on infrared-protocols 5.1.0 (separate PR for version bump)
- The integration follows Bronze quality scale requirements
- Translation strings use standard patterns for better i18n support
- Test structure matches LG Infrared integration patterns
- All IR commands are validated in tests with expected code values
- Entity availability properly tracks the underlying infrared entity state
- Initial release focuses on media player; additional platforms may follow based on feedback

### File Structure
```
homeassistant/components/samsung_infrared/
├── __init__.py          # Integration setup
├── config_flow.py       # UI configuration flow
├── const.py             # Constants
├── entity.py            # Base entity class
├── manifest.json        # Integration metadata
├── media_player.py      # Media player entity
├── quality_scale.yaml   # Quality scale definition
└── strings.json         # Translations

tests/components/samsung_infrared/
├── __init__.py
├── conftest.py          # Test fixtures
├── snapshots/           # Syrupy snapshots (2 snapshots)
├── test_config_flow.py  # Config flow tests
├── test_entity.py       # Entity availability tests
├── test_init.py         # Integration setup tests
└── test_media_player.py # Media player tests
```
