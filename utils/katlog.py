import logging
from datetime import datetime


class LazyLogger:

    def __init__(self, name: str = "ColorLogger"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self._handler = None
        self.logger.propagate = False

    def _get_color(self, level: str) -> str:
        """Return ANSI color codes based on log level."""
        colors = {
            "DEBUG": "\033[36m",
            "INFO": "\033[34m",
            "SUCCESS": "\033[1;32m",
            "WARNING": "\033[33m",
            "ERROR": "\033[31m",
            "CRITICAL": "\033[1;31m",
        }
        return colors.get(level, "\033[0m")

    def _log(self, level: str, message: str):
        """Internal log method with formatting."""
        if not self._handler:
            self._handler = logging.StreamHandler()
            self._handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(self._handler)

        timestamp = datetime.now().strftime("%d:%m:%y")
        color = self._get_color(level)
        reset = "\033[0m"
        formatted_msg = f"{timestamp} {color}[{level}]:{reset} {message}"
        self.logger.log(getattr(logging, level, logging.INFO), formatted_msg)

    def debug(self, message: str):
        self._log("DEBUG", message)

    def info(self, message: str):
        self._log("INFO", message)

    def success(self, message: str):
        self._log("SUCCESS", message)

    def warning(self, message: str):
        self._log("WARNING", message)

    def error(self, message: str):
        self._log("ERROR", message)

    def critical(self, message: str):
        self._log("CRITICAL", message)


logger = LazyLogger()
