"""
Cross-platform single-instance guard.

Acquires an OS-level advisory lock on a lock file so only one copy of the
automation can run at a time. Running two copies at once made both pick up the
same story before either updated its status, creating duplicate test cases.

The lock is held by the OS for the lifetime of the process and released
automatically when the process exits (even on a crash), so there is no stale
lock file to clean up manually.
"""
import sys
from pathlib import Path

LOCK_PATH = Path(__file__).parent / "automation.lock"


class AlreadyRunningError(RuntimeError):
    """Raised when another instance already holds the lock."""


class SingleInstanceLock:
    """Context manager that fails fast if another instance is running."""

    def __init__(self, lock_path: Path = LOCK_PATH):
        self._lock_path = lock_path
        self._handle = None

    def __enter__(self) -> "SingleInstanceLock":
        # Keep the file open for the whole process lifetime; the OS releases the
        # lock when this handle is closed (on exit or crash).
        self._handle = open(self._lock_path, "a+")
        try:
            self._acquire(self._handle)
        except OSError as exc:
            self._handle.close()
            self._handle = None
            raise AlreadyRunningError(
                f"Another instance is already running (lock: {self._lock_path})"
            ) from exc
        return self

    def __exit__(self, *_exc) -> None:
        if self._handle is not None:
            self._release(self._handle)
            self._handle.close()
            self._handle = None

    @staticmethod
    def _acquire(handle) -> None:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _release(handle) -> None:
        try:
            if sys.platform == "win32":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            # Best-effort release; closing the handle frees the lock anyway.
            pass
