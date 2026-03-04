"""Authentication service — pure business logic, no CLI prompts.

Used by both the CLI (auth.py) and Web UI (app.py) frontends.
"""

from src.modules.logger import logger
from src.config.constants import DEFAULT_REDIRECT_URI, VALIDATION_SUCCESS_CODE
from src.utils.http_client import TokenStore, SdpClient


def create_token_store(accounts_url, client_id, client_secret, refresh_token=""):
    """Create a TokenStore with the given credentials."""
    return TokenStore(
        accounts_url=accounts_url,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        redirect_uri=DEFAULT_REDIRECT_URI,
    )


def generate_access_token(token_store):
    """Generate an access token using a refresh token.

    Returns:
        (success: bool, message: str)
    """
    logger.info("Generating access token...")
    if token_store.generate_token():
        logger.success("Access token generated")
        return True, "Access token generated"
    return False, "Failed to generate access token"


def exchange_grant_code(token_store, code):
    """Exchange a grant token (authorization code) for refresh + access tokens.

    Returns:
        (success: bool, message: str)
    """
    logger.info("Exchanging grant code for tokens...")
    if token_store.generate_token_from_code(code):
        logger.success("Tokens obtained from grant code")
        return True, "Tokens obtained from grant code"
    return False, "Failed to exchange grant code"


def authenticate_token_store(token_store, auth_method, grant_code=None, label=""):
    """Authenticate a token store based on the chosen auth method.

    Args:
        token_store: TokenStore instance
        auth_method: 'refresh_token' or 'grant_token'
        grant_code: required when auth_method is 'grant_token'
        label: 'Source' or 'Target' for logging

    Returns:
        (success: bool, message: str)
    """
    if auth_method == "grant_token":
        logger.info(f"Exchanging {label.lower()} grant code for tokens...")
        if token_store.generate_token_from_code(grant_code):
            logger.success(f"{label} tokens obtained from grant code")
            return True, f"{label} tokens obtained from grant code"
        return False, f"Failed to exchange {label.lower()} grant code"
    else:
        logger.info(f"Generating {label.lower()} access token...")
        if token_store.generate_token():
            logger.success(f"{label} access token generated")
            return True, f"{label} access token generated"
        return False, f"Failed to generate {label.lower()} access token"


def create_sdp_client(base_url, portal, token_store, label=""):
    """Create an SdpClient instance."""
    return SdpClient(
        base_url=base_url,
        portal=portal,
        token_store=token_store,
        label=label,
    )


def validate_connection(client):
    """Call GET /statuses and check for status_code 2000.

    Returns:
        (success: bool, message: str)
    """
    logger.info(f"Validating {client.label} instance connection...")
    try:
        response = client.get("statuses")

        if response.status_code != 200:
            msg = f"[{client.label}] Validation failed — HTTP {response.status_code}"
            logger.error(msg)
            logger.debug(f"[{client.label}] Response body: {response.text}")
            return False, msg

        data = response.json()
        response_status = data.get("response_status", [])

        if (
            response_status
            and response_status[0].get("status_code") == VALIDATION_SUCCESS_CODE
        ):
            msg = f"[{client.label}] Connection validated successfully"
            logger.success(msg)
            return True, msg

        msg = f"[{client.label}] Unexpected response: {data}"
        logger.error(msg)
        return False, msg

    except Exception as exc:
        msg = f"[{client.label}] Validation error: {exc}"
        logger.error(msg)
        return False, msg


def revoke_tokens(*clients):
    """Revoke refresh tokens for any clients that were created from grant codes."""
    for client in clients:
        if client is not None:
            client.token_store.revoke_token()
