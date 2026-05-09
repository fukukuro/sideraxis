import asyncio
import logging
import threading
import time
from itertools import count
from typing import Callable, Dict, List, Optional, Final

import serial

import exceptions


class SerialWorker:
    """
    Handles background serial communication with the hardware.
    Manages a reading thread and routes responses to asyncio Futures.
    """

    def __init__(self, port: str, baud: int, display_name: str) -> None:
        self._port: Final[str] = port
        self._baud: Final[int] = baud
        self._ser: Optional[serial.Serial] = None
        self._running = False
        self._queries: Dict[str, asyncio.Future[str]] = {}
        self._noqid_callbacks: List[Callable[[str], None]] = []
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.display_name = display_name
        print(f"name:{self.display_name}")
        # Internal QID generator to abstract request-response tracking
        self._qid_generator = count(1)

    def start(self) -> None:
        """Starts the background reading thread."""
        if self._running:
            return
        self._running = True
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the background reading thread and closes the port."""
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()
        if self._thread:
            self._thread.join(timeout=1.0)

        # Cancel any pending futures
        for fut in self._queries.values():
            if not fut.done():
                fut.cancel()
        self._queries.clear()

        logging.info(f"SerialWorker ({self._port}) stopped.")

    def register_noqid_callback(self, callback: Callable[[str], None]) -> None:
        """Registers a callback for messages that do not have a Query ID (e.g., READY, RECV)."""
        if callback not in self._noqid_callbacks:
            self._noqid_callbacks.append(callback)
            logging.debug(f"Registered NOQID callback in SerialWorker ({self._port})")

    async def send(self, cmd: str, timeout: float = 5.0) -> str:
        """
        Sends a command packet and waits for a response asynchronously.
        The Query ID (QID) is automatically generated and managed internally.
        """
        if not self._ser or not self._ser.is_open:
            raise exceptions.hardware.SerialPortNotOpenError(
                f"Serial port {self._port} is not open."
            )

        # Update or set the loop to the current running one
        current_loop = asyncio.get_running_loop()
        if self._loop is None or self._loop != current_loop:
            self._loop = current_loop
            logging.debug(f"SerialWorker ({self._port}) loop updated/initialized.")

        # Generate a unique QID for this request-response cycle
        qid = str(next(self._qid_generator))

        # Create a future to wait for the response
        fut = self._loop.create_future()
        self._queries[qid] = fut

        try:
            # Format: {qid}:{cmd}\n
            packet = f"{qid}:{cmd}\n".encode()
            self._ser.write(packet)
            logging.debug(f"Sent (QID {qid}): {cmd}")

            # Wait for the future to be completed by the reading thread
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            logging.warning(f"Response timeout for QID: {qid} on {self._port}")
            raise exceptions.hardware.SerialResponseTimeoutError(
                f"Response timeout for QID: {qid} on {self._port}"
            )
        finally:
            # Cleanup
            self._queries.pop(qid, None)

    def _process_line(self, line: str) -> None:
        """
        Parses a single line received from the serial port and dispatches it.
        Thread-safe bridge to the asyncio loop.
        """
        logging.debug(f"Received ({self._port}): {line}")

        parts = line.split(":", 2)
        if len(parts) < 3 or parts[0] != "RES":
            # Silently ignore non-response lines or malformed data
            return

        qid = parts[1]
        content = parts[2]

        if not self._loop:
            return

        if qid == "NOQID":
            for cb in self._noqid_callbacks:
                try:
                    self._loop.call_soon_threadsafe(cb, content)
                except Exception as e:
                    logging.error(f"Error in NOQID callback: {e}")
            return

        if qid in self._queries:
            self._loop.call_soon_threadsafe(self._set_query_result, qid, content)
        else:
            logging.debug(f"No matching query for QID: {qid}")

    def _set_query_result(self, qid: str, result: str) -> None:
        """Helper to set future result from within the event loop."""
        fut = self._queries.get(qid)
        if fut and not fut.done():
            fut.set_result(result)

    def _run(self) -> None:
        """Inner loop for the reading thread."""
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=0.1)
            logging.info(f"Serial port {self._port} opened at {self._baud} baud.")
            while self._running:
                try:
                    if self._ser.in_waiting > 0:
                        line = (
                            self._ser.readline()
                            .decode("utf-8", errors="replace")
                            .strip()
                        )
                        if line:
                            self._process_line(line)
                    time.sleep(0.01)
                except Exception as inner_e:
                    logging.error(f"Error reading from {self._port}: {inner_e}")
        except Exception as e:
            logging.critical(f"Fatal Serial Error on {self._port}: {e}")
        finally:
            self._running = False

    @property
    def port(self) -> str:
        return self._port

    @property
    def baud(self) -> int:
        return self._baud

    @property
    def running(self) -> bool:
        return self._running