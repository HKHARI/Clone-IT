from src.modules.logger import logger
from src.config.constants import ZOHO_ACCOUNTS_URLS
from src.utils.prompts import confirm, select, text, password
from src.services.auth_service import (
    create_token_store,
    authenticate_token_store,
    create_sdp_client,
    validate_connection,
)


def _validate_not_empty(val):
    if not val or not val.strip():
        return "This field cannot be empty"
    return True


def _validate_url(val):
    val = val.strip()
    if not val:
        return "URL cannot be empty"
    if not val.startswith("https://"):
        return "URL must start with https://"
    return True


def _collect_credentials(label):
    """Prompt the user for base URL, portal name, and OAuth credentials."""
    instance = _collect_instance_info(label)
    oauth = _collect_oauth_credentials(label)
    return {**instance, **oauth}


def _collect_instance_info(label):
    """Prompt for base URL and portal name only."""
    logger.info(f"--- {label} Instance Details ---")
    base_url = text(
        f"  {label} Base URL (e.g. https://sdpondemand.manageengine.com):",
        validate=_validate_url,
    )
    base_url = base_url.rstrip("/")
    portal = text(f"  {label} Portal Name:", validate=_validate_not_empty)
    return {"base_url": base_url, "portal": portal}


def _collect_oauth_credentials(label):
    """Prompt for OAuth credentials with auth method selection."""
    logger.info(f"--- {label} OAuth Credentials ---")

    auth_method = select(f"  How would you like to authenticate ({label})?", [
        {"label": "I have a Refresh Token", "value": "refresh_token"},
        {"label": "I have a Grant Token (Code)", "value": "grant_token"},
    ])

    client_id = text(f"  {label} Client ID:", validate=_validate_not_empty)
    client_secret = password(f"  {label} Client Secret:")

    if not client_secret:
        raise ValueError(f"{label} Client Secret cannot be empty")

    if auth_method == "refresh_token":
        refresh_token = password(f"  {label} Refresh Token:")
        if not refresh_token:
            raise ValueError(f"{label} Refresh Token cannot be empty")
        return {
            "auth_method": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    else:
        grant_code = password(f"  {label} Grant Token (Code):")
        if not grant_code:
            raise ValueError(f"{label} Grant Token cannot be empty")
        return {
            "auth_method": "grant_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_code": grant_code,
        }


def _validate_connection(client):
    """Delegate to auth_service.validate_connection."""
    success, _ = validate_connection(client)
    return success


def run_auth():
    """Interactive authentication wizard.

    Two scenarios:
      1. Same org     → shared accounts URL & OAuth token, different instances
      2. Different orgs → separate accounts URLs, credentials, and tokens

    Returns:
        tuple[SdpClient, SdpClient] — (source_client, target_client) on success,
        or (None, None) on failure.
    """
    same_org = confirm(
        "Are source and target under the same Zoho organization?", default=False
    )

    # --- Zoho Accounts URL(s) ---
    if same_org:
        accounts_url = select("Select Zoho Accounts URL:", ZOHO_ACCOUNTS_URLS)
    else:
        logger.info("Select Zoho Accounts URL for the source organization")
        source_accounts_url = select(
            "  Source Zoho Accounts URL:", ZOHO_ACCOUNTS_URLS
        )
        logger.info("Select Zoho Accounts URL for the target organization")
        target_accounts_url = select(
            "  Target Zoho Accounts URL:", ZOHO_ACCOUNTS_URLS
        )

    # --- Source credentials ---
    source_creds = _collect_credentials("Source")
    source_accts_url = accounts_url if same_org else source_accounts_url

    source_token_store = create_token_store(
        accounts_url=source_accts_url,
        client_id=source_creds["client_id"],
        client_secret=source_creds["client_secret"],
        refresh_token=source_creds.get("refresh_token", ""),
    )

    success, _ = authenticate_token_store(
        source_token_store,
        auth_method=source_creds["auth_method"],
        grant_code=source_creds.get("grant_code"),
        label="Source",
    )
    if not success:
        logger.error("Source authentication failed. Exiting.")
        return None, None

    source_client = create_sdp_client(
        base_url=source_creds["base_url"],
        portal=source_creds["portal"],
        token_store=source_token_store,
        label="source",
    )

    # --- Target ---
    if same_org:
        # Same org → shared base URL, accounts URL, and OAuth token
        target_portal = text("  Target Portal Name:", validate=_validate_not_empty)
        target_client = create_sdp_client(
            base_url=source_creds["base_url"],
            portal=target_portal,
            token_store=source_token_store,
            label="target",
        )
    else:
        # Separate org — full credentials and own token
        target_creds = _collect_credentials("Target")

        target_token_store = create_token_store(
            accounts_url=target_accounts_url,
            client_id=target_creds["client_id"],
            client_secret=target_creds["client_secret"],
            refresh_token=target_creds.get("refresh_token", ""),
        )

        success, _ = authenticate_token_store(
            target_token_store,
            auth_method=target_creds["auth_method"],
            grant_code=target_creds.get("grant_code"),
            label="Target",
        )
        if not success:
            logger.error("Target authentication failed. Exiting.")
            return None, None

        target_client = create_sdp_client(
            base_url=target_creds["base_url"],
            portal=target_creds["portal"],
            token_store=target_token_store,
            label="target",
        )

    # --- Validate both connections ---
    if not _validate_connection(source_client):
        logger.error("Source instance validation failed. Exiting.")
        return None, None

    if not _validate_connection(target_client):
        logger.error("Target instance validation failed. Exiting.")
        return None, None

    logger.success("Both instances authenticated and validated")
    return source_client, target_client
