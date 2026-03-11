"""Tests for the thread-safe audio ring buffer."""

import threading
import time

import numpy as np

from sip2sdr.audio.ring_buffer import RingBuffer


class TestRingBufferBasics:
    def test_write_and_read_exact(self) -> None:
        buf = RingBuffer(capacity=100)
        data = np.ones(10, dtype=np.int16)
        buf.write(data)
        result = buf.read(10)
        assert len(result) == 10
        np.testing.assert_array_equal(result, data)

    def test_read_returns_silence_on_underrun(self) -> None:
        buf = RingBuffer(capacity=100)
        result = buf.read(10)
        assert len(result) == 10
        np.testing.assert_array_equal(result, np.zeros(10, dtype=np.int16))

    def test_partial_underrun_fills_silence(self) -> None:
        buf = RingBuffer(capacity=100)
        data = np.ones(5, dtype=np.int16)
        buf.write(data)
        result = buf.read(10)
        np.testing.assert_array_equal(result[:5], data)
        np.testing.assert_array_equal(result[5:], np.zeros(5, dtype=np.int16))

    def test_write_wraps_around(self) -> None:
        buf = RingBuffer(capacity=8)
        buf.write(np.full(6, 1, dtype=np.int16))
        buf.read(4)  # consume 4, leaving 2
        buf.write(np.full(6, 2, dtype=np.int16))  # wraps around
        result = buf.read(8)
        assert result[0] == 1
        assert result[1] == 1
        assert result[2] == 2

    def test_overwrite_when_full(self) -> None:
        """When buffer is full, oldest data is overwritten."""
        buf = RingBuffer(capacity=4)
        buf.write(np.array([1, 2, 3, 4], dtype=np.int16))
        buf.write(np.array([5, 6], dtype=np.int16))  # overwrites 1,2
        result = buf.read(4)
        np.testing.assert_array_equal(result, [3, 4, 5, 6])

    def test_available_samples(self) -> None:
        buf = RingBuffer(capacity=100)
        assert buf.available == 0
        buf.write(np.ones(20, dtype=np.int16))
        assert buf.available == 20
        buf.read(10)
        assert buf.available == 10


class TestRingBufferThreadSafety:
    def test_concurrent_write_and_read(self) -> None:
        """Writer and reader threads must not deadlock or corrupt data."""
        buf = RingBuffer(capacity=4000)
        results: list[int] = []

        def writer() -> None:
            for _ in range(100):
                buf.write(np.ones(40, dtype=np.int16))
                time.sleep(0.0001)

        def reader() -> None:
            for _ in range(100):
                chunk = buf.read(40)
                results.append(len(chunk))
                time.sleep(0.0001)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert all(r == 40 for r in results)
