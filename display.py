# =============================================================================
# display.py  —  Shared color-coded terminal output
# Author: Taline Bteddini  (Member 1)
#
# CONTRIBUTIONS IN THIS FILE
#   Written by Member 1: print_settings
#   AI-generated (Claude, Anthropic), reviewed by Member 1: ANSI color setup,
#                        thread-safe log_event, reset_clock, human_size
#
# All three parts print through log_event() so the sender and receiver logs
# use the same colors and never interleave half-lines between threads.
# =============================================================================
import os
import sys
import threading
import time

if os.name == "nt":
    os.system("")            # enables ANSI colors in the Windows 10+ terminal

USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ

RESET = "\033[0m"
COLORS = {
    "INFO":    "\033[37m",       # grey/white
    "SEND":    "\033[32m",       # green
    "ACK":     "\033[36m",       # cyan
    "DROP":    "\033[1;31m",     # bold red
    "HOLD":    "\033[35m",       # magenta
    "REORDER": "\033[33m",       # yellow
    "FLUSH":   "\033[33m",       # yellow
    "TIMEOUT": "\033[1;31m",     # bold red
    "RETX":    "\033[1;33m",     # bold yellow
    "DUPACK":  "\033[33m",       # yellow
    "WINDOW":  "\033[34m",       # blue
    "RECV":    "\033[32m",       # green
    "BUFFER":  "\033[35m",       # magenta
    "OK":      "\033[1;32m",     # bold green
    "ERROR":   "\033[1;31m",     # bold red
}

_print_lock = threading.Lock()
_t0 = time.monotonic()


def reset_clock():
    """Call once when the transfer starts so timestamps begin at 0."""
    global _t0
    _t0 = time.monotonic()


def log_event(side, kind, text):
    """One line per event, e.g.  [  0.012s] SENDER   DROPPED 13 (simulated)"""
    line = f"[{time.monotonic() - _t0:8.3f}s] {side:<8} {text}"
    color = COLORS.get(kind, "")
    if USE_COLOR and color:
        line = color + line + RESET
    with _print_lock:
        print(line, flush=True)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def print_settings(info, window_size, loss, reorder):
    """Settings block shown at start.  (Member 1)"""
    # TODO (Member 1): print a clear block with file name, size (human_size),
    #   chunk size, number of packets (DATA + END), window size N,
    #   loss and reorder probabilities. Wrap the prints in `with _print_lock:`
    #   so another thread can't print in the middle of it.

    with _print_lock:
        line = "=" * 60
        print(line)
        print(" RELIABLE FILE TRANSFER OVER UDP — SETTINGS")
        print("-" * 60)
        print(f" File          : {info['file_name']}")
        print(f" Size          : {human_size(info['file_size'])}")
        print(f" Chunk size    : {info['chunk_size']}")
        print(f" Packets       : {info['total_packets']}")
        print(f" Window size N : {window_size}")
        print(f" Loss          : {loss}")
        print(f" Reorder       : {reorder}")
        print(line, flush=True)

   