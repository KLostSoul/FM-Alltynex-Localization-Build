"""Nonblocking, reentrant workspace lock shared by all build-data writers."""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import hashlib
import os
from pathlib import Path
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = hashlib.sha256(os.path.normcase(str(ROOT)).encode('utf-8')).hexdigest()
LOCK_PATH = Path(tempfile.gettempdir()) / f'alltynex-{IDENTITY}.lock'
_guard = threading.Lock()
_local = threading.local()


class WorkspaceBusyError(RuntimeError):
    def __init__(self):
        super().__init__('Another Alltynex build or save is running. Try again after it finishes.')


@contextmanager
def workspace_lock():
    # The builder also calls locked token/output helpers on the same thread.
    if getattr(_local, 'held', False):
        yield
        return
    if not _guard.acquire(blocking=False):
        raise WorkspaceBusyError()
    handle = None
    locked = False
    try:
        handle = LOCK_PATH.open('a+b')
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'\0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise WorkspaceBusyError() from error
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise WorkspaceBusyError() from error
        locked = True
        _local.held = True
        yield
    finally:
        _local.held = False
        try:
            if locked:
                if os.name == 'nt':
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            try:
                if handle is not None:
                    handle.close()
            finally:
                _guard.release()
    # Do not unlink the lock file: processes must keep locking the same file.
    # OS locks are released when the handle closes, including process exit.


def exclusive_workspace(function):
    @wraps(function)
    def run(*args, **kwargs):
        with workspace_lock():
            return function(*args, **kwargs)
    return run
