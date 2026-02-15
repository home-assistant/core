# Fix infinite loop in esphome assist_satellite when wake word entity state is missing

## Description
This PR fixes a critical infinite loop in the `handle_pipeline_start` method of the `esphome` component's `assist_satellite.py`.

The issue was caused by a logic error in the `while` loop that searches for matching wake word entities. If a wake word entity existed in the registry (caught by `get_wake_word_entity`) but was not present in the state machine (caught by `hass.states.get` returning `None`), the code would execute a `continue` statement. Crucially, this `continue` skipped the increment of `maybe_pipeline_index`, causing the loop to retry the same index indefinitely and hang the Home Assistant main thread.

This fix refactors the loop to remove the `continue` statement and ensure that `maybe_pipeline_index` is always incremented, preventing the hang. This aligns with the observed behavior where HA would hang after some uptime, likely triggered when an expected wake word entity became unavailable or was in an inconsistent state.

## Type of change
- [x] Bugfix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation Update
- [ ] Maintenance

## Checklist
- [x] I have performed a self-review of my own code
- [x] I have followed the [style guidelines](https://developers.home-assistant.io/docs/style_guide_index)
- [ ] I have updated the documentation (if applicable)
- [ ] I have added tests that prove my fix is effective or that my feature works (if applicable)
