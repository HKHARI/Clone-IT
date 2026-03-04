"""SDP Migration Wizard — CLI Entry Point.

Launch with:  python migrate.py   or   ./run.sh

This is the CLI-only interface. It uses questionary prompts for user
interaction. The web UI (app.py) is a separate interface that collects
input via NiceGUI forms instead.

Removing this file (and src/modules/auth.py, src/modules/migration.py,
src/utils/prompts.py) cleanly removes the CLI without affecting the GUI.
"""

import sys

from src.modules.logger import logger
from src.modules.auth import run_auth
from src.modules.migration import run_migration_selection, collect_migration_items
from src.services.migration_service import run_migration
from src.services.auth_service import revoke_tokens


def main():
    logger.init()

    print()
    print("=" * 50)
    print("   SDP Migration Wizard  v1.0")
    print("=" * 50)
    print()

    logger.info("Migration wizard started")

    source_client = None
    target_client = None

    try:
        source_client, target_client = run_auth()

        if source_client is None or target_client is None:
            sys.exit(1)

        logger.success("Authentication complete — ready for migration")

        migration_type, module = run_migration_selection()

        if migration_type is None:
            logger.warn("Migration cancelled.")
            return

        # Collect user's item selection (questionary prompts)
        selection_kwargs = collect_migration_items(
            migration_type, source_client, target_client, module
        )

        if not run_migration(migration_type, source_client, target_client, module, **selection_kwargs):
            logger.error(f"Migration type '{migration_type}' is not yet implemented.")

    except KeyboardInterrupt:
        print()
        logger.warn("Operation cancelled by user")
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        logger.debug(f"Exception details: {repr(exc)}")
    finally:
        # Revoke refresh tokens that were generated from grant codes
        revoke_tokens(source_client, target_client)
        logger.close()


if __name__ == "__main__":
    main()
