import json
import requests

from src.modules.logger import logger


class TokenStore:
    """Holds OAuth credentials and manages access-token generation / refresh.

    For same_instance scenarios, a single TokenStore is shared by both the
    source and target SdpClient instances so a refresh updates both at once.
    """

    def __init__(self, accounts_url, client_id, client_secret, refresh_token, redirect_uri):
        self.accounts_url = accounts_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.redirect_uri = redirect_uri
        self.access_token = None
        self._generated_from_code = False

    def generate_token(self):
        url = f"{self.accounts_url}/oauth/v2/token"
        payload = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }

        logger.debug(f"Requesting access token from {url}")
        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error(f"Token request failed: {exc}")
            return False

        result = response.json()

        if "access_token" in result:
            self.access_token = result["access_token"]
            logger.debug("Access token obtained successfully")
            return True

        error = result.get("error", "unknown_error")
        logger.error(f"Token generation failed: {error}")
        return False

    def generate_token_from_code(self, code):
        """Exchange a grant token (authorization code) for refresh + access token.

        On success, stores both refresh_token and access_token on this instance,
        so all subsequent auto-refresh calls via generate_token() work normally.
        """
        url = f"{self.accounts_url}/oauth/v2/token"
        payload = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }

        logger.debug(f"Exchanging grant code at {url}")
        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error(f"Grant code exchange failed: {exc}")
            return False

        result = response.json()
        logger.debug(f"Grant code exchange response: {result}")

        if "refresh_token" in result and "access_token" in result:
            self.refresh_token = result["refresh_token"]
            self.access_token = result["access_token"]
            self._generated_from_code = True
            logger.debug("Refresh token and access token obtained from grant code")
            return True

        error = result.get("error", "unknown_error")
        if "invalid_code" in error.lower():
            logger.error(
                "Grant token has expired or is invalid. "
                "Please generate a new one and try again."
            )
        else:
            logger.error(f"Grant code exchange failed: {error}")
        return False

    def revoke_token(self):
        """Revoke the refresh token if it was generated from a grant code."""
        if not self._generated_from_code or not self.refresh_token:
            return

        url = f"{self.accounts_url}/oauth/v2/token/revoke"
        try:
            response = requests.post(url, data={"token": self.refresh_token}, timeout=30)
            result = response.json()
            if result.get("status") == "success":
                logger.success("Refresh token revoked successfully")
            else:
                logger.warn(f"Token revocation response: {result}")
        except Exception as exc:
            logger.warn(f"Token revocation failed: {exc}")


class SdpClient:
    """HTTP client for the SDP On-Demand v3 API.

    Automatically retries a request once if a 401 is received by refreshing
    the access token through the associated TokenStore.
    """

    COMMON_HEADERS = {
        "Accept": "application/vnd.manageengine.sdp.v3+json",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    def __init__(self, base_url, portal, token_store, label=""):
        self.base_api_url = f"{base_url}/app/{portal}/api/v3"
        self.token_store = token_store
        self.label = label

    def _auth_headers(self):
        headers = dict(self.COMMON_HEADERS)
        headers["Authorization"] = f"Zoho-oauthtoken {self.token_store.access_token}"
        return headers

    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_api_url}/{endpoint}"
        logger.debug(f"[{self.label}] {method.upper()} {url}")

        kwargs["headers"] = self._auth_headers()
        kwargs.setdefault("timeout", 30)
        response = getattr(requests, method)(url, **kwargs)

        if response.status_code == 401:
            logger.warn(f"[{self.label}] Access token expired — refreshing")
            if self.token_store.generate_token():
                kwargs["headers"] = self._auth_headers()
                response = getattr(requests, method)(url, **kwargs)
            else:
                logger.error(f"[{self.label}] Token refresh failed, cannot retry")

        logger.debug(f"[{self.label}] Response {response.status_code}")
        return response

    def get(self, endpoint, params=None):
        return self._request("get", endpoint, params=params)

    def post(self, endpoint, payload=None):
        data = {}
        if payload is not None:
            data["input_data"] = json.dumps(payload)
        return self._request("post", endpoint, data=data)

    def put(self, endpoint, payload=None):
        data = {}
        if payload is not None:
            data["input_data"] = json.dumps(payload)
        return self._request("put", endpoint, data=data)

    def delete(self, endpoint):
        return self._request("delete", endpoint)
