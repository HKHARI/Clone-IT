"""SDP Migration Wizard — Web UI (NiceGUI)

Launch with:  python app.py   or   ./run_ui.sh
"""

import asyncio
from nicegui import ui, app

from src.modules.logger import logger
from src.config.constants import ZOHO_ACCOUNTS_URLS, SUPPORTED_MIGRATIONS
from src.services.auth_service import (
    create_token_store,
    authenticate_token_store,
    create_sdp_client,
    validate_connection,
    revoke_tokens,
)
from src.services.migration_service import (
    get_migration_choices,
    get_module_choices,
    get_dependencies,
    get_steps,
    should_show_step,
    load_items as svc_load_items,
    run_migration,
)
from src.services.template_service import resolve_by_ids


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNTS_URL_OPTIONS = {item["value"]: item["label"] for item in ZOHO_ACCOUNTS_URLS}
AUTH_METHOD_OPTIONS = {
    "refresh_token": "I have a Refresh Token",
    "grant_token": "I have a Grant Token (Code)",
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class WizardState:
    """Holds all wizard form data and runtime objects."""

    def __init__(self):
        # Step 1 — Organization
        self.same_org = False
        self.source_accounts_url = ZOHO_ACCOUNTS_URLS[0]["value"]
        self.target_accounts_url = ZOHO_ACCOUNTS_URLS[0]["value"]
        # Step 2 — Source
        self.source_base_url = ""
        self.source_portal = ""
        self.source_auth_method = "refresh_token"
        self.source_client_id = ""
        self.source_client_secret = ""
        self.source_refresh_token = ""
        self.source_grant_code = ""
        # Step 3 — Target
        self.target_base_url = ""
        self.target_portal = ""
        self.target_auth_method = "refresh_token"
        self.target_client_id = ""
        self.target_client_secret = ""
        self.target_refresh_token = ""
        self.target_grant_code = ""
        # Step 4 — Migration
        self.migration_type = ""
        self.module = ""
        # Item selection
        self.available_items = []    # list of dicts: {key/id, display_name/name, ...}
        self.selected_item_keys = [] # list of selected keys/IDs
        # Runtime
        self.source_client = None
        self.target_client = None


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

@ui.page("/")
def main_page():
    state = WizardState()
    log_area = None

    # --- Theme ---
    ui.dark_mode().enable()

    # --- Header ---
    with ui.header().classes("items-center justify-between q-pa-sm"):
        ui.label("SDP Migration Wizard").classes("text-h5 text-weight-bold")
        ui.label("v1.1 — Web UI").classes("text-caption text-grey-5")

    # --- Log panel helper ---
    def push_log(level, message):
        """Logger callback — pushes log lines to the UI log area."""
        if log_area is None:
            return
        color_map = {"INFO": "", "WARN": "⚠️ ", "ERROR": "❌ ", "PASS": "✅ "}
        prefix = color_map.get(level, "")
        log_area.push(f"{prefix}{message}")

    # --- Content ---
    with ui.column().classes("w-full max-w-3xl mx-auto q-pa-md"):

        with ui.stepper().props("vertical animated").classes("w-full") as stepper:

            # ============================================================
            # STEP 1 — Organization Type
            # ============================================================
            with ui.step("Organization"):
                ui.label("Are the source and target under the same Zoho organization?")
                same_org_switch = ui.switch("Same organization", value=False).bind_value(state, "same_org")

                ui.separator()
                ui.label("Zoho Accounts URLs").classes("text-subtitle2 q-mt-md")

                source_accounts = ui.select(
                    ACCOUNTS_URL_OPTIONS, label="Source Accounts URL",
                    value=state.source_accounts_url,
                ).classes("w-full").bind_value(state, "source_accounts_url")

                target_accounts = ui.select(
                    ACCOUNTS_URL_OPTIONS, label="Target Accounts URL",
                    value=state.target_accounts_url,
                ).classes("w-full").bind_value(state, "target_accounts_url")

                def toggle_target_accounts():
                    target_accounts.set_visibility(not state.same_org)

                same_org_switch.on_value_change(toggle_target_accounts)

                with ui.stepper_navigation():
                    ui.button("Next", on_click=stepper.next).props("color=primary")

            # ============================================================
            # STEP 2 — Source Credentials
            # ============================================================
            with ui.step("Source Credentials"):
                ui.label("Source Instance Details").classes("text-subtitle2")

                ui.input("Base URL", placeholder="https://sdpondemand.manageengine.com").bind_value(state, "source_base_url").classes("w-full")
                ui.input("Portal Name", placeholder="itdesk").bind_value(state, "source_portal").classes("w-full")

                ui.separator()
                ui.label("OAuth Credentials").classes("text-subtitle2 q-mt-md")

                src_auth = ui.select(
                    AUTH_METHOD_OPTIONS, label="Authentication Method",
                    value="refresh_token",
                ).classes("w-full").bind_value(state, "source_auth_method")

                ui.input("Client ID").bind_value(state, "source_client_id").classes("w-full")
                ui.input("Client Secret", password=True, password_toggle_button=True).bind_value(state, "source_client_secret").classes("w-full")

                src_refresh = ui.input(
                    "Refresh Token", password=True, password_toggle_button=True,
                ).bind_value(state, "source_refresh_token").classes("w-full")

                src_grant = ui.input(
                    "Grant Token (Code)", password=True, password_toggle_button=True,
                ).bind_value(state, "source_grant_code").classes("w-full")

                def toggle_src_auth():
                    src_refresh.set_visibility(state.source_auth_method == "refresh_token")
                    src_grant.set_visibility(state.source_auth_method == "grant_token")

                src_auth.on_value_change(toggle_src_auth)
                toggle_src_auth()

                with ui.stepper_navigation():
                    ui.button("Next", on_click=stepper.next).props("color=primary")
                    ui.button("Back", on_click=stepper.previous).props("flat")

            # ============================================================
            # STEP 3 — Target Credentials + Connect/Validate
            # ============================================================
            with ui.step("Target Credentials"):
                # If same org, just ask for portal name
                target_same_org_label = ui.label(
                    "Same organization — only portal name needed"
                ).classes("text-caption text-grey-5")

                target_full_section = ui.column().classes("w-full")
                with target_full_section:
                    ui.label("Target Instance Details").classes("text-subtitle2")
                    ui.input("Base URL", placeholder="https://sdpondemand.manageengine.com").bind_value(state, "target_base_url").classes("w-full")

                ui.input("Portal Name", placeholder="itdesk").bind_value(state, "target_portal").classes("w-full")

                target_auth_section = ui.column().classes("w-full")
                with target_auth_section:
                    ui.separator()
                    ui.label("OAuth Credentials").classes("text-subtitle2 q-mt-md")

                    tgt_auth = ui.select(
                        AUTH_METHOD_OPTIONS, label="Authentication Method",
                        value="refresh_token",
                    ).classes("w-full").bind_value(state, "target_auth_method")

                    ui.input("Client ID").bind_value(state, "target_client_id").classes("w-full")
                    ui.input("Client Secret", password=True, password_toggle_button=True).bind_value(state, "target_client_secret").classes("w-full")

                    tgt_refresh = ui.input(
                        "Refresh Token", password=True, password_toggle_button=True,
                    ).bind_value(state, "target_refresh_token").classes("w-full")

                    tgt_grant = ui.input(
                        "Grant Token (Code)", password=True, password_toggle_button=True,
                    ).bind_value(state, "target_grant_code").classes("w-full")

                    def toggle_tgt_auth():
                        tgt_refresh.set_visibility(state.target_auth_method == "refresh_token")
                        tgt_grant.set_visibility(state.target_auth_method == "grant_token")

                    tgt_auth.on_value_change(toggle_tgt_auth)
                    toggle_tgt_auth()

                def toggle_target_section():
                    target_same_org_label.set_visibility(state.same_org)
                    target_full_section.set_visibility(not state.same_org)
                    target_auth_section.set_visibility(not state.same_org)

                same_org_switch.on_value_change(toggle_target_section)

                # --- Connect & Validate ---
                status_label = ui.label("").classes("text-caption q-mt-md")

                async def connect_and_validate():
                    status_label.set_text("⏳ Authenticating...")

                    # Validate required fields
                    if not state.source_base_url or not state.source_portal:
                        ui.notify("Source Base URL and Portal are required", type="negative")
                        status_label.set_text("")
                        return
                    if not state.source_client_id or not state.source_client_secret:
                        ui.notify("Source Client ID and Secret are required", type="negative")
                        status_label.set_text("")
                        return
                    if not state.same_org:
                        if not state.target_base_url or not state.target_portal:
                            ui.notify("Target Base URL and Portal are required", type="negative")
                            status_label.set_text("")
                            return
                        if not state.target_client_id or not state.target_client_secret:
                            ui.notify("Target Client ID and Secret are required", type="negative")
                            status_label.set_text("")
                            return

                    try:
                        # --- Source auth ---
                        src_accounts = state.source_accounts_url
                        src_token_store = create_token_store(
                            accounts_url=src_accounts,
                            client_id=state.source_client_id,
                            client_secret=state.source_client_secret,
                            refresh_token=state.source_refresh_token,
                        )
                        success, msg = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: authenticate_token_store(
                                src_token_store,
                                auth_method=state.source_auth_method,
                                grant_code=state.source_grant_code,
                                label="Source",
                            ),
                        )
                        if not success:
                            ui.notify(f"Source auth failed: {msg}", type="negative")
                            status_label.set_text("❌ Source authentication failed")
                            return

                        source_client = create_sdp_client(
                            base_url=state.source_base_url.rstrip("/"),
                            portal=state.source_portal,
                            token_store=src_token_store,
                            label="source",
                        )

                        # --- Target auth ---
                        if state.same_org:
                            target_client = create_sdp_client(
                                base_url=state.source_base_url.rstrip("/"),
                                portal=state.target_portal,
                                token_store=src_token_store,
                                label="target",
                            )
                        else:
                            tgt_token_store = create_token_store(
                                accounts_url=state.target_accounts_url,
                                client_id=state.target_client_id,
                                client_secret=state.target_client_secret,
                                refresh_token=state.target_refresh_token,
                            )
                            success, msg = await asyncio.get_event_loop().run_in_executor(
                                None,
                                lambda: authenticate_token_store(
                                    tgt_token_store,
                                    auth_method=state.target_auth_method,
                                    grant_code=state.target_grant_code,
                                    label="Target",
                                ),
                            )
                            if not success:
                                ui.notify(f"Target auth failed: {msg}", type="negative")
                                status_label.set_text("❌ Target authentication failed")
                                return

                            target_client = create_sdp_client(
                                base_url=state.target_base_url.rstrip("/"),
                                portal=state.target_portal,
                                token_store=tgt_token_store,
                                label="target",
                            )

                        # --- Validate ---
                        status_label.set_text("⏳ Validating connections...")

                        src_ok, src_msg = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: validate_connection(source_client),
                        )
                        if not src_ok:
                            ui.notify(f"Source validation failed: {src_msg}", type="negative")
                            status_label.set_text("❌ Source validation failed")
                            return

                        tgt_ok, tgt_msg = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: validate_connection(target_client),
                        )
                        if not tgt_ok:
                            ui.notify(f"Target validation failed: {tgt_msg}", type="negative")
                            status_label.set_text("❌ Target validation failed")
                            return

                        state.source_client = source_client
                        state.target_client = target_client

                        ui.notify("Both instances connected and validated!", type="positive")
                        status_label.set_text("✅ Connected and validated")
                        stepper.next()

                    except Exception as exc:
                        ui.notify(f"Error: {exc}", type="negative")
                        status_label.set_text(f"❌ {exc}")

                with ui.stepper_navigation():
                    ui.button("Connect & Validate", on_click=connect_and_validate).props("color=positive")
                    ui.button("Back", on_click=stepper.previous).props("flat")

            # ============================================================
            # STEP 4 — Migration Config + Item Selection
            # ============================================================
            with ui.step("Migration"):

                # --- Phase 1: Migration Type & Module ---
                ui.label("Select Migration Type & Module").classes("text-subtitle2")

                mig_choices = {c["value"]: c["label"] for c in get_migration_choices()}
                mig_select = ui.select(
                    mig_choices, label="Migration Type",
                ).classes("w-full").bind_value(state, "migration_type")

                dep_warning = ui.label("").classes("text-caption text-warning q-mt-sm")
                module_select = ui.select({}, label="Module").classes("w-full").bind_value(state, "module")

                # --- Phase 2: Steps from config (hidden until module selected) ---
                phase2_section = ui.column().classes("w-full q-mt-md")
                phase2_section.set_visibility(False)

                # Dynamic step widgets — rebuilt when migration type changes
                step_widgets = {}       # key -> widget reference
                current_steps = []      # current config steps
                current_mode_key = [None]  # tracks which step key is item_selection
                current_mode_value = [None]  # tracks the selected mode

                with phase2_section:
                    ui.separator()
                    ui.label("Migration Scope").classes("text-subtitle2 q-mt-sm")
                    steps_container = ui.column().classes("w-full")

                # --- Phase 3: Item Selection (hidden until "Load Items") ---
                phase3_section = ui.column().classes("w-full q-mt-md")
                phase3_section.set_visibility(False)

                with phase3_section:
                    ui.separator()
                    load_status = ui.label("").classes("text-caption q-mb-sm")
                    items_container = ui.column().classes("w-full")

                # --- Load Items button (hidden until needed) ---
                load_btn = ui.button("🔍 Load Items", on_click=lambda: None).props("color=secondary")
                load_btn.set_visibility(False)

                # --- Build step widgets from config ---

                def rebuild_steps():
                    """Rebuild step widgets from the config for the selected migration type."""
                    mt = state.migration_type
                    mod = state.module
                    if not mt or not mod:
                        return

                    steps = get_steps(mt)
                    current_steps.clear()
                    current_steps.extend(steps)
                    step_widgets.clear()
                    current_mode_key[0] = None
                    current_mode_value[0] = None
                    steps_container.clear()

                    with steps_container:
                        for step in steps:
                            _build_step_widget(step, mt, mod)

                def _build_step_widget(step, mt, mod):
                    """Build a single step widget based on its type."""
                    step_key = step["key"]
                    step_type = step["type"]

                    if step_type == "item_selection":
                        current_mode_key[0] = step_key
                        mode_opts = {m["value"]: m["label"] for m in step["modes"]}
                        mode_select = ui.select(
                            mode_opts, label="Migration Mode",
                            value=list(mode_opts.keys())[0],
                        ).classes("w-full")
                        step_widgets[step_key] = mode_select
                        current_mode_value[0] = mode_select.value

                        def on_mode_change(step_cfg=step):
                            current_mode_value[0] = step_widgets[step_cfg["key"]].value
                            needs_selection = current_mode_value[0] == "selected"
                            load_btn.set_visibility(needs_selection)
                            if not needs_selection:
                                phase3_section.set_visibility(False)
                                items_container.clear()
                            # Refresh visibility of conditional steps
                            _refresh_conditional_steps()

                        mode_select.on_value_change(on_mode_change)

                    elif step_type == "toggle":
                        if not should_show_step(step, current_mode_value[0], mod):
                            sw = ui.switch(step["label"], value=step.get("default", False))
                            sw.set_visibility(False)
                        else:
                            sw = ui.switch(step["label"], value=step.get("default", False))
                        step_widgets[step_key] = sw

                    elif step_type == "text_input":
                        if not should_show_step(step, current_mode_value[0], mod):
                            inp = ui.input(step["label"]).classes("w-full")
                            inp.set_visibility(False)
                        else:
                            inp = ui.input(step["label"]).classes("w-full")
                        step_widgets[step_key] = inp

                def _refresh_conditional_steps():
                    """Show/hide steps based on current mode and module."""
                    mod = state.module
                    for step in current_steps:
                        if step["key"] in step_widgets and "condition" in step:
                            visible = should_show_step(step, current_mode_value[0], mod)
                            step_widgets[step["key"]].set_visibility(visible)

                # --- Wire up phase transitions ---

                def on_migration_change():
                    mt = state.migration_type
                    if not mt:
                        return
                    mod_choices = {c["value"]: c["label"] for c in get_module_choices(mt)}
                    module_select.options = mod_choices
                    module_select.update()
                    dep_info = get_dependencies(mt)
                    if dep_info["has_deps"]:
                        dep_warning.set_text(
                            f"⚠️ Depends on: {', '.join(dep_info['dep_labels'])}. "
                            "Ensure those are migrated first."
                        )
                    else:
                        dep_warning.set_text("")
                    phase2_section.set_visibility(False)
                    phase3_section.set_visibility(False)
                    load_btn.set_visibility(False)
                    state.available_items = []
                    state.selected_item_keys = []
                    items_container.clear()

                def on_module_change():
                    mod = state.module
                    mt = state.migration_type
                    if not mod or not mt:
                        return
                    phase2_section.set_visibility(True)
                    load_btn.set_visibility(False)
                    phase3_section.set_visibility(False)
                    state.available_items = []
                    state.selected_item_keys = []
                    items_container.clear()
                    rebuild_steps()

                mig_select.on_value_change(on_migration_change)
                module_select.on_value_change(on_module_change)

                # --- Load Items (generic) ---

                async def do_load_items():
                    mt = state.migration_type
                    mod = state.module
                    if not mt or not mod:
                        ui.notify("Please select migration type and module first", type="warning")
                        return
                    if not state.source_client or not state.target_client:
                        ui.notify("Not connected — go back and validate", type="negative")
                        return

                    phase3_section.set_visibility(True)
                    load_status.set_text("⏳ Fetching items...")
                    items_container.clear()
                    state.available_items = []
                    state.selected_item_keys = []

                    try:
                        # Find the item_selection step
                        sel_step = None
                        for s in current_steps:
                            if s["type"] == "item_selection":
                                sel_step = s
                                break
                        if sel_step is None:
                            return

                        # Collect extra opts from toggle/input steps
                        opts = {}
                        for s in current_steps:
                            if s["type"] in ("toggle", "text_input") and s["key"] in step_widgets:
                                if should_show_step(s, current_mode_value[0], mod):
                                    opts[s["key"]] = step_widgets[s["key"]].value

                        items = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: svc_load_items(
                                sel_step["item_loader"],
                                state.source_client, state.target_client, mod,
                                **opts,
                            ),
                        )

                        if not items:
                            load_status.set_text("✅ No items found to migrate.")
                            return

                        item_key = sel_step["item_key"]
                        label_fmt = sel_step.get("item_label", "{name}")

                        load_status.set_text(
                            f"Found {len(items)} item(s). Select which ones to migrate:"
                        )
                        state.available_items = items
                        state.selected_item_keys = [str(item[item_key]) for item in items]
                        _build_item_checkboxes(
                            items_container, state, items,
                            key_field=item_key,
                            label_fn=lambda item: label_fmt.format(**item),
                        )

                    except Exception as exc:
                        load_status.set_text(f"❌ Error: {exc}")
                        ui.notify(f"Error loading items: {exc}", type="negative")

                load_btn.on_click(do_load_items)

                with ui.stepper_navigation():
                    ui.button("Next", on_click=stepper.next).props("color=primary")
                    ui.button("Back", on_click=stepper.previous).props("flat")

            # ============================================================
            # STEP 5 — Execute & Results
            # ============================================================
            with ui.step("Execute"):
                ui.label("Migration Execution").classes("text-subtitle2")

                summary_label = ui.label("").classes("q-mb-md")
                progress = ui.linear_progress(value=0, show_value=False).classes("w-full q-mb-md")
                progress.set_visibility(False)

                log_area = ui.log(max_lines=500).classes("w-full h-80")
                log_area.set_visibility(False)
                result_label = ui.label("").classes("text-h6 q-mt-md")

                async def execute_migration():
                    mt = state.migration_type
                    mod = state.module

                    if not mt or not mod:
                        ui.notify("Please select a migration type and module", type="negative")
                        return
                    if not state.source_client or not state.target_client:
                        ui.notify("Not connected — go back and validate", type="negative")
                        return

                    # Determine the mode from item_selection step
                    is_selected_mode = current_mode_value[0] == "selected"

                    if is_selected_mode and not state.selected_item_keys:
                        ui.notify("No items selected — go back and select items", type="warning")
                        return

                    # Hide buttons during execution
                    start_btn.set_visibility(False)
                    back_btn.set_visibility(False)

                    mig_label = mig_choices.get(mt, mt)
                    if is_selected_mode:
                        count = len(state.selected_item_keys)
                        scope_text = f"({count} item{'s' if count != 1 else ''} selected)"
                    else:
                        scope_text = "(all items)"
                    summary_label.set_text(
                        f"Running: {mig_label} → {mod.capitalize()} {scope_text}"
                    )
                    progress.set_visibility(True)
                    progress.set_value(None)  # indeterminate
                    log_area.set_visibility(True)
                    log_area.clear()
                    result_label.set_text("")

                    # Hook logger to UI
                    logger.init()
                    logger.set_ui_callback(push_log)

                    try:
                        # Build kwargs from step widgets — generic for any migration type
                        kwargs = {}
                        for step in current_steps:
                            sk = step["key"]
                            st = step["type"]

                            if st == "item_selection":
                                sel_step = step
                                mode_val = current_mode_value[0]
                                item_key = step["item_key"]

                                if mode_val == "selected":
                                    # Use checkbox selection
                                    selected_set = set(str(k) for k in state.selected_item_keys)
                                    kwargs[sk] = [
                                        item for item in state.available_items
                                        if str(item[item_key]) in selected_set
                                    ]
                                elif mode_val == "source_ids":
                                    # Resolve IDs from text input
                                    for s2 in current_steps:
                                        if s2.get("type") == "text_input":
                                            raw = step_widgets.get(s2["key"])
                                            if raw:
                                                kwargs[sk] = resolve_by_ids(raw.value or "")
                                            break
                                    if sk not in kwargs:
                                        kwargs[sk] = []
                                else:
                                    # "all" mode — fetch everything via loader
                                    opts = {}
                                    for s2 in current_steps:
                                        if s2["type"] in ("toggle", "text_input") and s2["key"] in step_widgets:
                                            if should_show_step(s2, mode_val, mod):
                                                opts[s2["key"]] = step_widgets[s2["key"]].value
                                    all_items = await asyncio.get_event_loop().run_in_executor(
                                        None,
                                        lambda: svc_load_items(
                                            step["item_loader"],
                                            state.source_client, state.target_client, mod,
                                            **opts,
                                        ),
                                    )
                                    kwargs[sk] = all_items or []

                            elif st in ("toggle", "text_input"):
                                if sk in step_widgets and should_show_step(step, current_mode_value[0], mod):
                                    kwargs[sk] = step_widgets[sk].value

                        success = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: run_migration(mt, state.source_client, state.target_client, mod, **kwargs),
                        )

                        if success:
                            result_label.set_text("✅ Migration completed!")
                            ui.notify("Migration completed!", type="positive")
                        else:
                            result_label.set_text("❌ Migration handler not found")
                            ui.notify(f"Migration type '{mt}' is not implemented", type="negative")

                    except Exception as exc:
                        result_label.set_text(f"❌ Error: {exc}")
                        ui.notify(f"Migration error: {exc}", type="negative")
                    finally:
                        progress.set_value(1.0)
                        logger.clear_ui_callback()
                        revoke_tokens(state.source_client, state.target_client)
                        logger.close()
                        # Show "Run Another" and "Exit" buttons
                        run_another_btn.set_visibility(True)
                        exit_btn.set_visibility(True)

                def go_to_migration_step():
                    """Reset and go back to Step 4 for another migration."""
                    run_another_btn.set_visibility(False)
                    exit_btn.set_visibility(False)
                    start_btn.set_visibility(True)
                    back_btn.set_visibility(True)
                    result_label.set_text("")
                    summary_label.set_text("")
                    progress.set_visibility(False)
                    log_area.clear()
                    stepper.previous()

                async def exit_wizard():
                    """Shut down the app gracefully."""
                    ui.notify("Goodbye!", type="info")
                    await asyncio.sleep(0.5)
                    app.shutdown()

                with ui.stepper_navigation():
                    start_btn = ui.button("🚀 Start Migration", on_click=execute_migration).props("color=positive size=lg")
                    run_another_btn = ui.button("🔄 Run Another Migration", on_click=go_to_migration_step).props("color=primary size=lg")
                    run_another_btn.set_visibility(False)
                    exit_btn = ui.button("🚪 Exit", on_click=exit_wizard).props("color=negative size=lg")
                    exit_btn.set_visibility(False)
                    back_btn = ui.button("Back", on_click=stepper.previous).props("flat")


# ---------------------------------------------------------------------------
# Item selection helper
# ---------------------------------------------------------------------------

def _build_item_checkboxes(container, state, items, key_field, label_fn):
    """Build a scrollable list of checkboxes for item selection.

    Args:
        container: NiceGUI column to add checkboxes into
        state: WizardState — updates state.selected_item_keys
        items: list of item dicts
        key_field: dict key to use as the unique identifier (e.g. 'key' or 'id')
        label_fn: function that accepts an item dict and returns the display label
    """
    with container:
        # Select All / Deselect All
        def toggle_all(checked):
            if checked:
                state.selected_item_keys = [str(item[key_field]) for item in items]
            else:
                state.selected_item_keys = []
            # Update all checkboxes
            for cb_key, cb in checkbox_map.items():
                cb.set_value(checked)

        select_all = ui.checkbox(
            f"Select All ({len(items)} items)", value=True, on_change=lambda e: toggle_all(e.value),
        ).classes("text-weight-bold q-mb-sm")

        ui.separator()

        # Scrollable item list
        checkbox_map = {}
        with ui.scroll_area().classes("w-full").style("max-height: 300px"):
            for item in items:
                item_key = str(item[key_field])

                def make_handler(k):
                    def handler(e):
                        if e.value and k not in state.selected_item_keys:
                            state.selected_item_keys.append(k)
                        elif not e.value and k in state.selected_item_keys:
                            state.selected_item_keys.remove(k)
                    return handler

                cb = ui.checkbox(
                    label_fn(item), value=True, on_change=make_handler(item_key),
                )
                checkbox_map[item_key] = cb


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

ui.run(title="SDP Migration Wizard", port=8080, reload=False)
