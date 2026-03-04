import sys
import questionary
from questionary import Choice


def confirm(message, default=True):
    result = questionary.confirm(message, default=default).ask()
    if result is None:
        _abort()
    return result


def select(message, choices):
    """Present a selection list.

    Args:
        choices: list of dicts with ``label`` and ``value`` keys.
    """
    q_choices = [Choice(title=c["label"], value=c["value"]) for c in choices]
    result = questionary.select(message, choices=q_choices).ask()
    if result is None:
        _abort()
    return result


def text(message, validate=None):
    kwargs = {"message": message}
    if validate:
        kwargs["validate"] = validate
    result = questionary.text(**kwargs).ask()
    if result is None:
        _abort()
    return result.strip()


def password(message):
    result = questionary.password(message).ask()
    if result is None:
        _abort()
    return result.strip()


def checkbox(message, choices):
    """Present a multi-select checkbox list.

    Args:
        choices: list of dicts with ``label`` and ``value`` keys.

    Returns:
        list of selected values.
    """
    q_choices = [Choice(title=c["label"], value=c["value"]) for c in choices]
    result = questionary.checkbox(message, choices=q_choices).ask()
    if result is None:
        _abort()
    return result


def _abort():
    print("\nOperation cancelled by user.")
    sys.exit(0)
