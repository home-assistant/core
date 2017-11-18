import { h, Component } from 'preact';

import { onChange } from './util';

export default class StateTrigger extends Component {
  constructor() {
    super();

    this.onChange = onChange.bind(this);
  }

  /* eslint-disable camelcase */
  render({ trigger }) {
    const { entity_id, to } = trigger;
    const trgFrom = trigger.from;
    const trgFor = trigger.for;
    return (
      <div>
        <paper-input
          label="Entity Id"
          name="entity_id"
          value={entity_id}
          onChange={this.onChange}
        />
        <paper-input
          label="From"
          name="from"
          value={trgFrom}
          onChange={this.onChange}
        />
        <paper-input
          label="To"
          name="to"
          value={to}
          onChange={this.onChange}
        />
        {trgFor && <pre>For: {JSON.stringify(trgFor, null, 2)}</pre>}
      </div>
    );
  }
}
