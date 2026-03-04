import os
import sys
from datetime import datetime
from colorama import Fore, Style, init as colorama_init


class Logger:
    """Dual-file logger with colored console output.

    Writes to two log files per session:
      - <timestamp>_debug.log  : all levels (DEBUG, INFO, WARN, ERROR)
      - <timestamp>.log        : user-readable (INFO, WARN, ERROR) — also printed to console
    """

    def __init__(self):
        self._initialized = False
        self._debug_file = None
        self._info_file = None
        self._ui_callback = None

    def init(self):
        if self._initialized:
            return

        colorama_init()

        # When frozen by PyInstaller, __file__ points inside a temp dir.
        # Write logs next to the executable so users can find them easily.
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logs_dir = os.path.join(base_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._debug_file = open(
            os.path.join(logs_dir, f"{timestamp}_debug.log"), "a", encoding="utf-8"
        )
        self._info_file = open(
            os.path.join(logs_dir, f"{timestamp}.log"), "a", encoding="utf-8"
        )
        self._initialized = True
        self.debug(f"Log session started — debug log: {self._debug_file.name}")

    def _timestamp(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write(self, level, message):
        line = f"[{self._timestamp()}] [{level:5s}] {message}"
        if self._debug_file:
            self._debug_file.write(line + "\n")
            self._debug_file.flush()
        if level != "DEBUG" and self._info_file:
            self._info_file.write(line + "\n")
            self._info_file.flush()
        if self._ui_callback and level != "DEBUG":
            try:
                self._ui_callback(level, message)
            except Exception:
                pass
        return line

    def debug(self, message):
        self._write("DEBUG", message)

    def info(self, message):
        line = self._write("INFO", message)
        print(line)

    def success(self, message):
        line = self._write("INFO", message)
        print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")

    def warn(self, message):
        line = self._write("WARN", message)
        print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")

    def error(self, message):
        line = self._write("ERROR", message)
        print(f"{Fore.RED}{line}{Style.RESET_ALL}")

    def close(self):
        if self._initialized:
            self.debug("Log session ended")
            if self._debug_file:
                self._debug_file.close()
            if self._info_file:
                self._info_file.close()
            self._initialized = False

    def set_ui_callback(self, callback):
        """Register a callback fn(level, message) for UI log forwarding."""
        self._ui_callback = callback

    def clear_ui_callback(self):
        """Remove the UI callback."""
        self._ui_callback = None


logger = Logger()
