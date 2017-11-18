import { h, Component } from 'preact';

import CallService from './call_service';

function getType(action) {
  if ('service' in action) {
    return 'Call Service';
  }
  return null;
}

const TYPES = {
  'Call Service': CallService,
  Delay: null,
  'Templated Delay': null,
  Condition: null,
  'Fire Event': null,
};

const OPTIONS = Object.keys(TYPES).sort();

export default class Action extends Component {
  constructor() {
    super();

    this.typeChanged = this.typeChanged.bind(this);
    this.onDelete = this.onDelete.bind(this);
  }

  typeChanged(ev) {
    const newType = ev.target.selectedItem.innerHTML;
    const oldType = getType(this.props.action);

    if (oldType !== newType) {
      this.props.onChange(this.props.index, {
        platform: newType,
      });
    }
  }

  onDelete() {
    // eslint-disable-next-line
    if (confirm('Sure you want to delete?')) {
      this.props.onChange(this.props.index, null);
    }
  }

  render({ index, action, onChange }) {
    const type = getType(action);
    const Comp = TYPES[type];
    const selected = OPTIONS.indexOf(type);
    let content;

    if (Comp) {
      content = (
        <div>
          <paper-dropdown-menu-light label="Action Type" no-animations>
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
            action={action}
            onChange={onChange}
          />
        </div>
      );
    } else {
      content = (
        <div>
          Unsupported action
          <pre>{JSON.stringify(action, null, 2)}</pre>
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
