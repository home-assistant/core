export function onChange(ev) {
  const trigger = { ...this.props.trigger };

  if (ev.target.value) {
    trigger[ev.target.name] = ev.target.value;
  } else {
    delete trigger[ev.target.name];
  }

  this.props.onChange(this.props.index, trigger);
}
