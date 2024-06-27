---
tags: [migration, code_quality]
---
# Migrate integration from hass.data to entry.runtime_data

Migrate an integration from hass.data to entry.runtime_data

```grit
engine marzano(0.1)
language python

pattern refactor_functions($config_entry_type) {
    function_definition($parameters, $body) where {
        // change entry type
        $entry = $parameters[1],
        $entry <: typed_parameter(name=$entry_name, $type) where {
            $type <: type(type="ConfigEntry"),
            $type => $config_entry_type
        },

        // migrate hass.data to entry.runtime_data
        $body <: maybe contains assignment($left, right=$runtime_data) as $assignment where {
            $runtime_data <: `hass.data[$_][entry.entry_id]`,
            $assignment => `$left = $entry_name.runtime_data`
        },
    }
}

pattern refactor_init($config_entry_type) {
    function_definition(name="async_setup_entry", $parameters, $body) as $func where {
        // change entry type
        $entry = $parameters[1],
        $entry <: typed_parameter(name=$entry_name, $type) where {
            $type => $config_entry_type
        },

        // migrate hass.data to entry.runtime_data
        $body <: contains or {
            `hass.data.setdefault($...)[entry.entry_id]`,
            `hass.data[$_][entry.entry_id]`,
            } as $runtime_data where {
                $runtime_data => `$entry_name.runtime_data`
            },

        $config_entry_type_definition = `# TODO: Please add the correct type\n`,
        $config_entry_type_definition += `type $config_entry_type = ConfigEntry`,
        $func => `$config_entry_type_definition\n\n$func`
    }
}

multifile {
    bubble($domain, $config_entry_type) file($name, $body) where {
        $file_parts = split($name, "/"),
        $components_folder = $file_parts[-3],
        $components_folder <: includes `components`, // with includes we allow also custom_components
        $domain = $file_parts[-2],
        $config_entry_type = capitalize($domain),
        $config_entry_type += "ConfigEntry",
        $name <: includes `__init__.py`,
        $body <: contains and {
            refactor_init($config_entry_type),
            maybe refactor_functions($config_entry_type)
        },
    },
    bubble($domain, $config_entry_type) file($name, $body) where {
        $file_parts = split($name, "/"),
        $domain = $file_parts[-2],
        $body <: contains refactor_functions($config_entry_type)
    }
}
```