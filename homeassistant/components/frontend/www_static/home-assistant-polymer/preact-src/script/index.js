import { h, Component } from 'preact';

import ScriptAction from './script_action';

export default class Script extends Component {
  constructor() {
    super();

    this.addAction = this.addAction.bind(this);
    this.actionChanged = this.actionChanged.bind(this);
  }

  addAction() {
    const script = this.props.script.concat({
      service: '',
    });

    this.props.onChange(script);
  }

  actionChanged(index, newValue) {
    const script = this.props.script.concat();

    if (newValue === null) {
      script.splice(index, 1);
    } else {
      script[index] = newValue;
    }

    this.props.onChange(script);
  }

  render({ script }) {
    return (
      <div class="script">
        {script.map((act, idx) => (
          <ScriptAction
            index={idx}
            action={act}
            onChange={this.actionChanged}
          />))}
        <paper-card>
          <div class='card-actions add-card'>
            <paper-button onTap={this.addAction}>Add action</paper-button>
          </div>
        </paper-card>
      </div>
    );
  }
}
