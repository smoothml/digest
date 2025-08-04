import yaml
from enum import Enum


def enum_value_representer(dumper: yaml.Dumper, data: Enum) -> yaml.ScalarNode:
    """Represent an enum value as a string in YAML.

    Args:
        dumper: The YAML dumper.
        data: The enum value to represent.

    Returns:
        The YAML scalar node representing the enum value.
    """
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data.value), style="")


def str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Set custom format for multiline strings.

    Args:
        dumper: The YAML dumper.
        data: The string data.

    Returns:
        The YAML node.
    """
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def register_enum_representer() -> None:
    """Register enum value representer globally for all Enum classes.

    This ensures that enum values are serialized as their string values
    rather than as Python objects.
    """
    yaml.add_representer(Enum, enum_value_representer)
    yaml.add_multi_representer(Enum, enum_value_representer)


def register_str_representer() -> None:
    """Register string representer globally for all string types."""
    yaml.add_representer(str, str_representer)


def register_all_representers() -> None:
    """Register all custom YAML representers.

    This is a convenience function that registers all available representers
    in this module in a single call.
    """
    register_enum_representer()
    register_str_representer()
