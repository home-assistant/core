import { h, Component } from 'preact';

import { onChange } from './util';

export default class NumericStateTrigger extends Component {
  constructor() {
    super();

    this.onChange = onChange.bind(this);
  }

  /* eslint-disable camelcase */
  render({ trigger }) {
    const { value_template, entity_id, below, above } = trigger;
    return (
      <div>
        <paper-input
          label="Entity Id"
          name="entity_id"
          value={entity_id}
          onChange={this.onChange}
        />
        <paper-input
          label="Above"
          name="above"
          value={above}
          onChange={this.onChange}
        />
        <paper-input
          label="Below"
          name="below"
          value={below}
          onChange={this.onChange}
        />
        Value template (optional)<br />
        <textarea
          name="value_template"
          value={value_template}
          style={{ width: '100%', height: 100 }}
          onChange={this.onChange}
        />
      </div>
    );
  }
}
