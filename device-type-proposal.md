# Device types: giving devices meaning

## The problem

Home Assistant knows what an entity is but not what a device is. It can tell you
that `sensor.kitchen_1` is a temperature sensor, yet it has no idea that the
device owning it is a fridge, or that the reading belongs to the freezer rather
than the fridge compartment. A device today is little more than a name, a
manufacturer and a bag of entities.

This is the gap the 2025H1 roadmap called [putting devices in
context](https://www.home-assistant.io/blog/2025/05/09/roadmap-2025h1/#putting-devices-in-context).
It costs us in three places:

1. Voice answers "what is the temperature in the kitchen" with the freezer
   reading, and cannot answer "how cold is the freezer" at all.
2. Dashboards cannot lay out a fridge, because nothing says which entity is the
   door, the compartment temperature or the fast freeze switch.
3. Automations and blueprints have to be written against specific entity IDs,
   so a blueprint written for one brand of appliance does not work for another.

## The proposal

Introduce two concepts.

A **device type** says what a device is, for example `appliance.refrigerator` or
`appliance.espresso_machine`. An integration declares it once when it registers
the device.

A **trait** says what job an entity does for that device, for example
`freezer_compartment_temperature`, `door` or `fast_freeze`. A device type
definition lists the traits it is composed of, and marks each as required or
optional.

Integrations map their own entities onto the traits of the type they declared.
They never invent a type or a trait of their own.

### The vocabulary is central and closed

Consumers can only act on device meaning if it is a fixed contract. If every
integration could coin its own vocabulary, Voice and dashboards would be back to
pattern matching on names. So the vocabulary lives in core, one definition per
device type, and integrations implement what is already defined. Adding a new
appliance category is a core contribution, and it is additive: a new type is a
new file, never an edit to a shared one.

### Required traits are a promise, not a gate

Marking a trait required is how a device type makes a guarantee to consumers: if
a device claims to be a refrigerator, something reports the fridge temperature.

Enforcing that at build time is not possible, because most integrations create
their entities dynamically from whatever the device reports. So a device that
declares a type without providing every required trait should surface as a
repair issue, never as a setup failure. The integration stays usable, and the
gap is visible to whoever can fix it.

### Two audiences, two kinds of text

A trait carries a description written for language models, and a name written
for people.

The description can be long and explanatory, because that is what makes a model
answer well. It stays untranslated. Every LLM facing string in Home Assistant is
English already, and the model is told which language the user speaks and
answers in it, so translating it would add cost for no benefit.

The name is what Voice speaks and the frontend shows, so it is translated. It
can carry optional aliases, both for the device type and for individual traits,
so that Assist matches "coffee machine" for an espresso machine, or "super
freeze" for the trait we call `fast_freeze`. Aliases are where regional and
vendor wording belongs, which keeps the vocabulary itself neutral.

### Traits are resolved, not stored

An entity does not gain a new stored attribute. The mapping lives with the
integration and the trait is resolved from it on demand, with the user able to
override a single entity when an integration gets it wrong. Keeping traits out
of the entity registry means adopting or correcting a mapping is just a data
change.

## What this unlocks

Voice can exclude entities that are semantically wrong for a question, the
freezer problem from the roadmap, and answer questions about a compartment
directly.

Dashboards gain a fridge card, or an espresso machine card, that works for every
brand, because the card can ask for traits instead of guessing at entity IDs.

Blueprints can bind to traits, so one blueprint covers every appliance of a
type, and the device page can show a device as a device rather than a flat list
of entities.

## Proof of concept

A branch implements this end to end with two device types,
`appliance.espresso_machine` and `appliance.refrigerator`, and two integrations,
`lamarzocco` and `miele`. It is deliberately thin on the runtime side: the
resolution and validation API is present as a stub so the discussion can focus
on the model rather than the plumbing.

## Open questions

1. Should the device type be user overridable, in the way a device name is, or
   is it purely integration declared?
2. Should a device be able to declare more than one type, for example a
   washer-dryer, or do combined appliances get their own type?
3. Where does a trait belong when a device is modelled with child devices? The
   proof of concept lets a trait be filled by an entity on the device or on any
   of its children. Is that the right default?
4. Do we want a quality scale rule for declaring a device type, and at which
   tier?
