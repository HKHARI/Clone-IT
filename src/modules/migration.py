"""CLI-only migration selection logic.

This module contains all interactive (questionary) prompts for migration
type/module selection and item selection. It is ONLY used by the CLI
entry point (migrate.py). The web UI (app.py) collects selections via
NiceGUI forms instead.

Removing this file (and migrate.py, auth.py, prompts.py) cleanly removes
the CLI interface without affecting the GUI or core migration logic.
"""

import questionary
from questionary import Choice, Separator

from src.modules.logger import logger
from src.config.constants import SUPPORTED_MIGRATIONS
from src.config.template_config import PAGE_SIZE
from src.services.migration_service import (
    get_migration_choices,
    get_module_choices,
    get_dependencies,
    get_steps,
    should_show_step,
    load_items,
)
from src.services.template_service import resolve_by_ids
from src.utils.prompts import select, confirm, text, checkbox


# ---------------------------------------------------------------------------
# Migration type & module selection
# ---------------------------------------------------------------------------

def run_migration_selection():
    """Interactive migration type and module selection.

    Returns:
        tuple[str, str] — (migration_type, module) e.g. ("udf", "request")
    """
    logger.info("Select migration type")

    migration_type = select("  Migration type:", get_migration_choices())

    dep_info = get_dependencies(migration_type)
    if dep_info["has_deps"]:
        logger.warn(
            f"Dependency warning: depends on "
            f"{', '.join(dep_info['dep_labels'])}. Ensure those are migrated first."
        )
        if not confirm("  Continue anyway?", default=True):
            return None, None

    module = select("  Select module:", get_module_choices(migration_type))
    logger.info(f"Module selected: {module}")

    return migration_type, module


# ---------------------------------------------------------------------------
# Generic step-based item collection
# ---------------------------------------------------------------------------

def collect_migration_items(migration_type, source_client, target_client, module):
    """Collect the user's item selection by iterating config steps.

    Reads the ``steps`` list from SUPPORTED_MIGRATIONS[migration_type]
    and renders each step as a CLI prompt. Returns a dict of kwargs
    to pass to run_migration().
    """
    steps = get_steps(migration_type)
    kwargs = {}
    current_mode = None  # tracks item_selection mode for condition checks

    for step in steps:
        if not should_show_step(step, current_mode, module):
            continue

        step_type = step["type"]

        if step_type == "item_selection":
            current_mode, selection = _handle_item_selection(
                step, source_client, target_client, module, kwargs
            )
            kwargs[step["key"]] = selection

        elif step_type == "toggle":
            kwargs[step["key"]] = confirm(
                f"  {step['label']}?", default=step.get("default", True)
            )

        elif step_type == "text_input":
            kwargs[step["key"]] = text(f"  {step['label']}:")

    return kwargs


# ---------------------------------------------------------------------------
# Item selection handler
# ---------------------------------------------------------------------------

def _handle_item_selection(step, source_client, target_client, module, kwargs):
    """Handle an item_selection step.

    Returns:
        (mode, items) where mode is the chosen mode string and items
        is the list to pass as the kwarg.
    """
    # Ask user which mode
    mode_choices = [
        {"label": m["label"], "value": m["value"]}
        for m in step["modes"]
    ]
    mode = select(f"  {step['label']} mode:", mode_choices)

    if mode == "source_ids":
        raw = text("  Enter comma-separated IDs:")
        return mode, resolve_by_ids(raw)

    # Fetch all items
    loader_key = step["item_loader"]
    all_items = load_items(
        loader_key, source_client, target_client, module, **kwargs
    )

    if not all_items:
        logger.info("No items found to migrate.")
        return mode, []

    if mode == "all":
        logger.info(f"  {len(all_items)} item(s) will be migrated.")
        return mode, all_items

    # mode == "selected" — present checkboxes
    item_key = step["item_key"]
    label_fmt = step.get("item_label", "{name}")

    choices = [
        {
            "label": label_fmt.format(**item),
            "value": item[item_key],
        }
        for item in all_items
    ]
    selected_keys = checkbox("  Select items to migrate:", choices)

    if not selected_keys:
        return mode, []

    selected_set = set(selected_keys)
    return mode, [item for item in all_items if item[item_key] in selected_set]


# ---------------------------------------------------------------------------
# Paginated selection helpers (used by template "selected" mode)
# ---------------------------------------------------------------------------

def _paginated_template_selection(templates):
    """Interactive paginated checkbox for template selection."""
    total = len(templates)
    if total == 0:
        return []

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    selected_ids = set()
    page = 0

    while True:
        start = page * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)
        page_items = templates[start:end]

        choices = _build_page_choices(page_items, selected_ids)

        if page > 0:
            choices.append(Choice(title="<< Previous page", value="__prev__"))
        if page < total_pages - 1:
            choices.append(Choice(title=">> Next page", value="__next__"))
        choices.append(Choice(title="Done — proceed with selected", value="__done__"))

        result = questionary.checkbox(
            f"  Select templates (page {page + 1}/{total_pages}):",
            choices=choices,
        ).ask()

        if result is None:
            return []

        nav = set(result) & {"__prev__", "__next__", "__done__"}
        page_ids = {t["id"] for t in page_items}
        actual = set(result) - nav
        selected_ids = (selected_ids - page_ids) | actual

        if "__done__" in nav:
            break
        elif "__next__" in nav:
            page += 1
        elif "__prev__" in nav:
            page -= 1

    return [t for t in templates if t["id"] in selected_ids]


def _build_page_choices(page_items, selected_ids):
    """Build questionary Choice list for one page of templates."""
    choices = []
    for t in page_items:
        label = t.get("name", t["id"])
        if t.get("inactive"):
            label += "  (inactive)"
        if t.get("is_default"):
            label += "  [default]"
        choices.append(Choice(
            title=label,
            value=t["id"],
            checked=t["id"] in selected_ids,
        ))
    choices.append(Separator("─" * 40))
    return choices
