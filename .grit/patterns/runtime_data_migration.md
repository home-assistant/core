---
tags: [migration, code_quality]
---
# Migrate integration from hass.data to entry.runtime_data

Migrate an integration from hass.data to entry.runtime_data

```grit
language python

pattern refactor_functions($config_entry_type, $file_name, $config_entry_type_defined) {
    function_definition($parameters, $body) as $func where {
        // change config entry type
        $parameters <: contains typed_parameter(name=$entry_name, $type) where {
            $type <: type(type="ConfigEntry"),
            $type => $config_entry_type,
            if ($file_name <: not `__init__`) {
                //$config_entry_type <: ensure_import_from(source = `.`),
            },
        },

        if (and {$file_name <: `__init__`, $config_entry_type_defined <: undefined}) {
            if ($func <: within decorated_definition() as $decorated) {
                // we need to insert the new type before all function decorators
                $func = $decorated,
            },
            $config_entry_type_definition = `# TODO: Please add the correct type\n`,
            $config_entry_type_definition += `type $config_entry_type = ConfigEntry`,
            $func => `$config_entry_type_definition\n\n$func`,
            $config_entry_type_defined = true,
        },

        // migrate hass.data to entry.runtime_data
        $body <: maybe contains assignment($left, $right) as $assignment where {
            or {
                and {
                    $right <: `hass.data[$_][entry.entry_id]`,
                    $assignment => `$left = $entry_name.runtime_data`
                },
                and {
                    $left <: or {
                            `hass.data.setdefault($...)[entry.entry_id]`,
                            `hass.data[$_][entry.entry_id]`,
                        } as $runtime_data where {
                            $runtime_data => `$entry_name.runtime_data`
                        },
                }
            }
        },
    }
}

multifile {
    bubble($domain_list) file($name, $body) where {
        // find all integrations, which can be migrated
        $filename <: r".*components/([^/]+)/__init__\.py$"($domain),
        $body <: contains or {
        `hass.data.setdefault($...)[entry.entry_id]`,
        `hass.data[$_][entry.entry_id]`,
        },
        if ($domain_list <: undefined) {
            $domain_list = []
        },
        $domain_list += $domain,
    },
    bubble($domain_list) file($name, $body) where {
        // migrate files
        $filename <: r".*components/([^/]+)/([^/]+)\.py$"($domain, $file_name),
        $domain_list <: includes $domain,
        $config_entry_type = capitalize($domain),
        $config_entry_type += "ConfigEntry",
        $body <: contains refactor_functions($config_entry_type, $file_name, $config_entry_type_defined),
    },
}
```