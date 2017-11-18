import { h, Component } from 'preact';

import JSONTextArea from '../json_textarea';

export default class CallServiceAction extends Component {
  constructor() {
    super();

    this.onChange = this.onChange.bind(this);
    this.serviceDataChanged = this.serviceDataChanged.bind(this);
  }

  onChange(ev) {
    this.props.onChange(this.props.index, {
      ...this.props.action,
      [ev.target.name]: ev.target.value
    });
  }

  /* eslint-disable camelcase */
  serviceDataChanged(data) {
    this.props.onChange(this.props.index, {
      ...this.props.action,
      data,
    });
  }

  render({ action }) {
    const { alias, service, data } = action;
    return (
      <div>
        <paper-input
          label="Alias"
          name="alias"
          value={alias}
          onChange={this.onChange}
        />
        <paper-input
          label="Service"
          name="service"
          value={service}
          onChange={this.onChange}
        />
        Service Data<br />
        <JSONTextArea
          value={data}
          onChange={this.serviceDataChanged}
        />
      </div>
    );
  }
}
