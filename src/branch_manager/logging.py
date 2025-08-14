"""Simple logging utility for the branch-manager application."""

import sys
from datetime import datetime
from enum import Enum
from typing import Any


class LogLevel(Enum):
    """Log levels for the application."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class Logger:
    """Simple logger with DEBUG, INFO, WARN, and ERROR levels."""

    def __init__(self, verbose: bool = False) -> None:
        """Initialize the logger.

        Args:
            verbose: Whether to show INFO and DEBUG level messages
        """
        self.verbose = verbose

    def _log(self, level: LogLevel, message: str, *args: Any) -> None:
        """Internal logging method.

        Args:
            level: Log level
            message: Log message
            *args: Additional arguments for string formatting
        """
        # Skip DEBUG messages if not in verbose mode
        if level == LogLevel.DEBUG and not self.verbose:
            return

        # Format message with args if provided
        if args:
            try:
                formatted_message = message % args
            except (TypeError, ValueError):
                formatted_message = f"{message} {' '.join(str(arg) for arg in args)}"
        else:
            formatted_message = message

        # Get current timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Format log entry
        log_entry = f"[{timestamp}] {level.value}: {formatted_message}"

        # Write to appropriate stream
        if level == LogLevel.ERROR:
            print(log_entry, file=sys.stderr)
        else:
            print(log_entry)

    def debug(self, message: str, *args: Any) -> None:
        """Log a DEBUG message.

        Args:
            message: Log message
            *args: Additional arguments for string formatting
        """
        self._log(LogLevel.DEBUG, message, *args)

    def info(self, message: str, *args: Any) -> None:
        """Log an INFO message.

        Args:
            message: Log message
            *args: Additional arguments for string formatting
        """
        self._log(LogLevel.INFO, message, *args)

    def warn(self, message: str, *args: Any) -> None:
        """Log a WARN message.

        Args:
            message: Log message
            *args: Additional arguments for string formatting
        """
        self._log(LogLevel.WARN, message, *args)

    def error(self, message: str, *args: Any) -> None:
        """Log an ERROR message.

        Args:
            message: Log message
            *args: Additional arguments for string formatting
        """
        self._log(LogLevel.ERROR, message, *args)


# Global logger instance
_logger: Logger | None = None


def get_logger() -> Logger:
    """Get the global logger instance.

    Returns:
        The global logger instance
    """
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger


def setup_logger(verbose: bool = False) -> Logger:
    """Setup the global logger with configuration.

    Args:
        verbose: Whether to enable verbose (INFO and DEBUG) logging

    Returns:
        The configured logger instance
    """
    global _logger
    _logger = Logger(verbose=verbose)
    return _logger


def debug(message: str, *args: Any) -> None:
    """Log a DEBUG message using the global logger."""
    get_logger().debug(message, *args)


def info(message: str, *args: Any) -> None:
    """Log an INFO message using the global logger."""
    get_logger().info(message, *args)


def warn(message: str, *args: Any) -> None:
    """Log a WARN message using the global logger."""
    get_logger().warn(message, *args)


def error(message: str, *args: Any) -> None:
    """Log an ERROR message using the global logger."""
    get_logger().error(message, *args)
