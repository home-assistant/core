import { h, Component } from 'preact';

import EventTrigger from './event';
import StateTrigger from './state';
import NumericStateTrigger from './numeric_state';

const TYPES = {
  event: EventTrigger,
  state: StateTrigger,
  homeassistant: null,
  mqtt: null,
  numeric_state: NumericStateTrigger,
  sun: null,
  template: null,
  time: null,
  zone: null,
};

const OPTIONS = Object.keys(TYPES).sort();

export default class TriggerRow extends Component {
  constructor() {
    super();

    this.typeChanged = this.typeChanged.bind(this);
    this.onDelete = this.onDelete.bind(this);
  }

  typeChanged(ev) {
    const type = ev.target.selectedItem.innerHTML;

    if (type !== this.props.trigger.platform) {
      this.props.onChange(this.props.index, {
        platform: type,
      });
    }
  }

  onDelete() {
    // eslint-disable-next-line
    if (confirm('Sure you want to delete?')) {
      this.props.onChange(this.props.index, null);
    }
  }

  render({ index, trigger, onChange }) {
    const Comp = TYPES[trigger.platform];
    const selected = OPTIONS.indexOf(trigger.platform);

    let content;

    if (Comp) {
      content = (
        <div>
          <paper-dropdown-menu-light label="Trigger Type" no-animations>
            <paper-listbox
              slot="dropdown-content"
              selected={selected}
              oniron-select={this.typeChanged}
            >
              {OPTIONS.map(opt => <paper-item>{opt}</paper-item>)}
            </paper-listbox>
          </paper-dropdown-menu-light>
          <Comp
            index={index}
            trigger={trigger}
            onChange={onChange}
          />
        </div>
      );
    } else {
      content = (
        <div>
          Unsupported platform: {trigger.platform}
          <pre>{JSON.stringify(trigger, null, 2)}</pre>
        </div>
      );
    }

    return (
      <paper-card>
        <div class='card-menu'>
          <paper-menu-button
            no-animations
            horizontal-align="right"
            horizontal-offset="-5"
            vertical-offset="-5"
          >
            <paper-icon-button
              icon="mdi:dots-vertical"
              slot="dropdown-trigger"
            />
            <paper-listbox slot="dropdown-content">
              <paper-item disabled>Duplicate</paper-item>
              <paper-item onTap={this.onDelete}>Delete</paper-item>
            </paper-listbox>
          </paper-menu-button>
        </div>
        <div class='card-content'>{content}</div>
      </paper-card>
    );
  }
}
