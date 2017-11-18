import { h, Component } from 'preact';

import JSONTextArea from '../json_textarea';

import { onChange } from './util';

export default class EventTrigger extends Component {
  constructor() {
    super();

    this.onChange = onChange.bind(this);
    this.eventDataChanged = this.eventDataChanged.bind(this);
  }

  /* eslint-disable camelcase */
  eventDataChanged(event_data) {
    this.props.onChange(this.props.index, {
      ...this.props.trigger,
      event_data,
    });
  }

  render({ trigger }) {
    const { event_type, event_data } = trigger;
    return (
      <div>
        <paper-input
          label="Event Type"
          name="event_type"
          value={event_type}
          onChange={this.onChange}
        />
        Event Data
        <JSONTextArea
          value={event_data}
          onChange={this.eventDataChanged}
        />
      </div>
    );
  }
}
