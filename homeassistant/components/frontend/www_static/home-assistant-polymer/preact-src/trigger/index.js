import { h, Component } from 'preact';

import TriggerRow from './trigger_row';

export default class Trigger extends Component {
  constructor() {
    super();

    this.addTrigger = this.addTrigger.bind(this);
    this.triggerChanged = this.triggerChanged.bind(this);
  }

  addTrigger() {
    const trigger = this.props.trigger.concat({
      platform: 'event',
    });

    this.props.onChange(trigger);
  }

  triggerChanged(index, newValue) {
    const trigger = this.props.trigger.concat();

    if (newValue === null) {
      trigger.splice(index, 1);
    } else {
      trigger[index] = newValue;
    }

    this.props.onChange(trigger);
  }

  render({ trigger }) {
    return (
      <div class="triggers">
        {trigger.map((trg, idx) => (
          <TriggerRow
            index={idx}
            trigger={trg}
            onChange={this.triggerChanged}
          />))}
        <paper-card>
          <div class='card-actions add-card'>
            <paper-button onTap={this.addTrigger}>Add trigger</paper-button>
          </div>
        </paper-card>
      </div>
    );
  }
}
