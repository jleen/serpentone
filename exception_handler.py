"""
Exception handling for multi-threaded audio application.

Provides thread-aware exception handling that crashes the program immediately
with full stack traces and thread context for debugging.
"""

import os
import sys
import threading
import traceback
from datetime import datetime
from typing import Any, Callable, Dict


class ExceptionHandler:
    """Centralized exception handler with thread context awareness."""

    @staticmethod
    def get_thread_context() -> Dict[str, Any]:
        """Get current thread context information.

        Returns:
            Dictionary with thread name, ID, and whether it's the main thread.
        """
        thread = threading.current_thread()
        return {
            "thread_name": thread.name,
            "thread_id": thread.ident,
            "is_main": thread is threading.main_thread(),
        }

    @staticmethod
    def log_and_crash(exc: Exception, context: Dict[str, Any]) -> None:
        """Log exception with full context and crash the program.

        Args:
            exc: The exception that was raised
            context: Context dictionary with source, callback_type, etc.
        """
        thread_ctx = ExceptionHandler.get_thread_context()
        context.update(thread_ctx)

        error_msg = [
            "=" * 80,
            f"FATAL EXCEPTION at {datetime.now().isoformat()}",
            f"Thread: {context.get('thread_name')} (ID: {context.get('thread_id')})",
            f"Source: {context.get('source', 'Unknown')}",
            f"Callback Type: {context.get('callback_type', 'Unknown')}",
        ]

        # Add method info if available
        if 'method' in context:
            error_msg.append(f"Method: {context.get('method')}")

        error_msg.extend([
            f"Exception Type: {type(exc).__name__}",
            f"Exception Message: {str(exc)}",
            "-" * 80,
            "Full Traceback:",
            traceback.format_exc(),
            "=" * 80,
        ])

        print("\n".join(error_msg), file=sys.stderr, flush=True)
        os._exit(1)


def wrap_callback(source: str, callback_type: str) -> Callable:
    """Decorator to wrap callback functions with exception handling.

    Args:
        source: Source of the callback (e.g., "MIDI", "Keyboard", "SuperCollider")
        callback_type: Type of callback (e.g., "note_event", "key_press", "boot")

    Returns:
        Decorator function that wraps the callback
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ExceptionHandler.log_and_crash(e, {
                    "source": source,
                    "callback_type": callback_type,
                })
        return wrapper
    return decorator


# Thread-local storage for cross-thread exception propagation
_exception_store = threading.local()


def wrap_call_from_thread(func: Callable, context: Dict[str, Any]) -> Callable:
    """Wrap a callable passed to call_from_thread() to detect exceptions.

    This stores any exception that occurs in thread-local storage so we can
    detect it after call_from_thread() returns.

    Args:
        func: The callable to wrap
        context: Context dictionary with source, method, etc.

    Returns:
        Wrapped callable that stores exceptions
    """
    def wrapper():
        try:
            return func()
        except Exception as e:
            # Store exception with its context for later retrieval
            _exception_store.exception = (e, context)
            raise  # Re-raise so Textual knows something went wrong
    return wrapper


def check_call_from_thread_exception() -> None:
    """Check if an exception occurred in a call_from_thread() call.

    If an exception was stored, this triggers a crash with full context.
    Should be called immediately after call_from_thread() returns.
    """
    if hasattr(_exception_store, 'exception'):
        exc, context = _exception_store.exception
        del _exception_store.exception  # Clear it
        ExceptionHandler.log_and_crash(exc, context)
