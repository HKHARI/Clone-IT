# Auth Module — `src/modules/auth.py`

> **Scope**: Authentication flow, token management, and connection validation  
> **Parent**: [`overview.md`](overview.md)  
> **Source file**: `src/modules/auth.py`  
> **Config**: `src/config/constants.py` (Zoho Accounts URLs)  
> **Last updated**: 2026-02-25

---

## 1. Interactive Flow

```
1. Ask: same instance? (yes/no)
2. Ask: Zoho Accounts URL (selection list — see §4)
   → If same_instance = false, ask separately for source and target
3. Ask: auth method → Refresh Token or Grant Token (Code)
4. Collect source credentials: base_url, portal, client_id, client_secret + token/code
5. If same_instance = true  → ask only target portal name
6. If same_instance = false → collect full target credentials (same auth method choice)
7. Generate/exchange tokens
8. Validate via GET /statuses
```

---

## 2. Token Management

### TokenStore Class

Holds OAuth credentials, generates/refreshes access tokens.

| Scenario | Behaviour |
|---|---|
| `same_instance = true` | ONE token, ONE TokenStore shared by both SdpClient instances |
| `same_instance = false` | Separate TokenStore per instance |

### Auto-Refresh

- `SdpClient` catches HTTP 401 → calls `TokenStore.generate_token()` → retries request
- Both source/target clients reference the same TokenStore object (by reference), so a refresh updates both instantly

### Defaults

- `redirect_uri` defaults to `https://www.zoho.com`

---

## 3. Token Generation

```
POST {accounts_url}/oauth/v2/token
  refresh_token=...
  grant_type=refresh_token
  client_id=...
  client_secret=...
  redirect_uri=https://www.zoho.com
```

---

## 4. Validation

```
GET {base_url}/app/{portal}/api/v3/statuses
```

Success criteria: HTTP 200 **AND** `response_status[0].status_code == 2000`

- `same_instance = true` → validate source only (same token)
- `same_instance = false` → validate both source and target

---

## 5. Return Contract

```python
(source_client: SdpClient, target_client: SdpClient)  # on success
(None, None)                                            # on failure → caller exits
```

---

## 6. Zoho Accounts URLs (from `constants.py`)

| Label | URL |
|---|---|
| US / Global | `https://accounts.zoho.com` |
| EU | `https://accounts.zoho.eu` |
| India | `https://accounts.zoho.in` |
| Australia | `https://accounts.zoho.com.au` |
| Japan | `https://accounts.zoho.jp` |
| China | `https://accounts.zoho.com.cn` |
| Canada | `https://accounts.zohocloud.ca` |
| Saudi Arabia | `https://accounts.zoho.sa` |

---

## 7. API Endpoints Used

| Endpoint | Method | Purpose |
|---|---|---|
| `{accounts_url}/oauth/v2/token` | POST | Generate access token from refresh token |
| `{accounts_url}/oauth/v2/token` | POST | Exchange grant code for refresh + access token |
| `{base}/app/{portal}/api/v3/statuses` | GET | Validate token / connection |

---

## 8. Grant Token Exchange

When user selects **"I have a Grant Token (Code)"**, the script calls `TokenStore.generate_token_from_code(code)` which POSTs to `{accounts_url}/oauth/v2/token` with `grant_type=authorization_code`. On success, both `refresh_token` and `access_token` are stored on the `TokenStore` instance — so subsequent 401 auto-refresh via `generate_token()` works normally.

> ⚠️ Grant codes expire in **1 minute**. If expired, a clear error is shown.

### Auto-Revocation

Refresh tokens generated from grant codes are automatically **revoked** when the migration completes (or fails). This happens in the `finally` block of `migrate.py` via `TokenStore.revoke_token()`. Tokens provided directly by the user are never revoked.
