# Clone-IT — SDP Migration Wizard

A standalone desktop tool for migrating SDP configurations between instances.

## Download

Download the executable for your platform from the [GitHub Actions](../../actions) build artifacts:

| Platform | File | 
|----------|------|
| **Windows** | `Clone-IT.exe` |
| **macOS** | `Clone-IT` (from `Clone-IT-macos`) |
| **Linux** | `Clone-IT` (from `Clone-IT-linux`) |

---

## Installation & Usage

### Windows

1. Download `Clone-IT.exe` from the build artifacts
2. Double-click to run — no installation needed
3. If Windows SmartScreen shows a warning, click **"More info"** → **"Run anyway"** (this happens because the exe is not code-signed)
4. The web UI opens automatically at `http://localhost:8080` in your default browser

### macOS

1. Download `Clone-IT` from the build artifacts
2. Open **Terminal** and navigate to the download location:
   ```bash
   cd ~/Downloads
   ```
3. Make it executable:
   ```bash
   chmod +x Clone-IT
   ```
4. Run it:
   ```bash
   ./Clone-IT
   ```
5. If macOS shows **"cannot be opened because the developer cannot be verified"**:
   - Go to **System Settings** → **Privacy & Security** → scroll down and click **"Open Anyway"**
   - Or run: `xattr -d com.apple.quarantine Clone-IT`
6. The web UI opens automatically at `http://localhost:8080`

### Linux

1. Download `Clone-IT` from the build artifacts
2. Open a terminal and navigate to the download location:
   ```bash
   cd ~/Downloads
   ```
3. Make it executable:
   ```bash
   chmod +x Clone-IT
   ```
4. Run it:
   ```bash
   ./Clone-IT
   ```
5. The web UI opens automatically at `http://localhost:8080`

---

## Logs

Log files are created in a `logs/` folder next to the executable:

```
Downloads/
├── Clone-IT          # the executable
└── logs/
    ├── 2026-03-04_12-00-00_debug.log
    └── 2026-03-04_12-00-00.log
```

---

## Building from Source

> **For maintainers only.** End users should use the pre-built executables above.

### Prerequisites
- Python 3.9+
- pip

### Build locally (macOS/Linux)
```bash
pip install -r requirements-ui.txt pyinstaller
pyinstaller --onefile --name "Clone-IT" --collect-all nicegui --hidden-import nicegui app.py
# Output: dist/Clone-IT
```

### Build all platforms via GitHub Actions
1. Push code to GitHub
2. Go to **Actions** → **Build Clone-IT Executables** → **Run workflow**
3. Download artifacts when the build completes (~5-10 min)
