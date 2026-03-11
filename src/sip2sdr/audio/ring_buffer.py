"""Thread-safe circular audio buffer for bridging GNU Radio and PJSUA2.

The GNU Radio flowgraph writes 8kHz int16 PCM samples into the buffer;
the PJSUA2 media port reads them out in fixed-size chunks.  When the
buffer underruns, silence (zeros) is returned instead of blocking.
"""

from __future__ import annotations

import threading

import numpy as np
from numpy.typing import NDArray


class RingBuffer:
    """Fixed-capacity circular buffer for int16 PCM audio samples.

    Thread-safe: a single writer (GNU Radio thread) and a single reader
    (PJSUA2 callback thread) may operate concurrently without external
    locking.

    Args:
        capacity: Maximum number of int16 samples the buffer can hold.
    """

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._buf: NDArray[np.int16] = np.zeros(capacity, dtype=np.int16)
        self._write_pos = 0
        self._read_pos = 0
        self._count = 0
        self._lock = threading.Lock()

    @property
    def available(self) -> int:
        """Number of samples currently available to read."""
        with self._lock:
            return self._count

    def write(self, data: NDArray[np.int16]) -> None:
        """Write *data* into the buffer, overwriting oldest samples if full.

        Args:
            data: 1-D array of int16 samples to enqueue.
        """
        with self._lock:
            n = len(data)
            # If writing more than capacity, only keep the last `capacity` samples.
            if n >= self._capacity:
                data = data[-self._capacity :]
                n = self._capacity
                self._write_pos = 0
                self._read_pos = 0
                self._count = 0

            space = self._capacity - self._write_pos
            if n <= space:
                self._buf[self._write_pos : self._write_pos + n] = data
            else:
                self._buf[self._write_pos :] = data[:space]
                self._buf[: n - space] = data[space:]

            self._write_pos = (self._write_pos + n) % self._capacity

            if self._count + n > self._capacity:
                # Overwrite: advance read pointer past the overwritten region.
                overflow = self._count + n - self._capacity
                self._read_pos = (self._read_pos + overflow) % self._capacity
                self._count = self._capacity
            else:
                self._count += n

    def read(self, n: int) -> NDArray[np.int16]:
        """Read exactly *n* samples, padding with silence on underrun.

        Args:
            n: Number of int16 samples to return.

        Returns:
            Array of exactly *n* int16 samples.
        """
        with self._lock:
            available = self._count
            to_copy = min(n, available)
            out = np.zeros(n, dtype=np.int16)

            if to_copy > 0:
                space = self._capacity - self._read_pos
                if to_copy <= space:
                    out[:to_copy] = self._buf[self._read_pos : self._read_pos + to_copy]
                else:
                    out[:space] = self._buf[self._read_pos :]
                    out[space:to_copy] = self._buf[: to_copy - space]

                self._read_pos = (self._read_pos + to_copy) % self._capacity
                self._count -= to_copy

            return out
