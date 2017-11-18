import { h, Component } from 'preact';


export default class JSONTextArea extends Component {
  constructor(props) {
    super(props);
    this.state.isValid = true;
    this.state.value = JSON.stringify(props.value || {}, null, 2);
    this.onChange = this.onChange.bind(this);
  }

  onChange(ev) {
    const value = ev.target.value;
    let parsed;
    let isValid;

    try {
      parsed = JSON.parse(value);
      isValid = true;
    } catch (err) {
      // Invalid JSON
      isValid = false;
    }

    this.setState({
      value,
      isValid,
    });
    if (isValid) {
      this.props.onChange(parsed);
    }
  }

  componentWillReceiveProps({ value }) {
    this.setState({
      value: JSON.stringify(value, null, 2),
      isValid: true,
    });
  }

  render(props, { value, isValid }) {
    const style = {
      minWidth: 300,
      width: '100%',
    };
    if (!isValid) {
      style.border = '1px solid red';
    }
    return (
      <iron-autogrow-textarea
        value={value}
        style={style}
        onValue-Changed={this.onChange}
      />
    );
  }
}
