"""TCP link to the ROS bridge (JSON lines) and the main simulation loop."""

from __future__ import annotations

import json
import socket
import threading
import time

from .world import DT, SUBSTEPS, World

PERIOD = DT * SUBSTEPS


class Hub:
    def __init__(self, world: World, host: str, tcp_port: int, realtime: bool = True):
        self.world = world
        self.realtime = realtime
        self.clients: list[socket.socket] = []
        self.lock = threading.Lock()
        self.latest = b"{}"
        self.reset_requested = False
        self.layout = json.dumps(world.scenario.layout()).encode()

        self.tcp = socket.socket()
        self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp.bind((host, tcp_port))
        self.tcp.listen(8)
        threading.Thread(target=self._accept, daemon=True).start()

    # --- TCP ---------------------------------------------------------------------

    def _accept(self) -> None:
        while True:
            conn, addr = self.tcp.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.sendall(b'{"type":"layout","layout":' + self.layout + b"}\n")
            with self.lock:
                self.clients.append(conn)
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()
            print(f"bridge connected from {addr[0]}", flush=True)

    def _read(self, conn: socket.socket) -> None:
        buf = b""
        try:
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        self._handle(json.loads(line))
        except (OSError, ValueError):
            pass
        finally:
            with self.lock:
                if conn in self.clients:
                    self.clients.remove(conn)
            conn.close()
            print("bridge disconnected", flush=True)

    def _handle(self, msg: dict) -> None:
        i = int(msg.get("id", -1))
        if not 0 <= i < self.world.n:
            return
        if msg.get("type") == "cmd_vel":
            self.world.set_cmd(i, float(msg["lin"]), float(msg["ang"]))
        elif msg.get("type") == "led":
            self.world.set_led(i, (float(msg["r"]), float(msg["g"]), float(msg["b"])))

    def _broadcast(self, payload: bytes) -> None:
        with self.lock:
            clients = list(self.clients)
        for conn in clients:
            try:
                conn.sendall(payload)
            except OSError:
                with self.lock:
                    if conn in self.clients:
                        self.clients.remove(conn)

    # --- main loop -------------------------------------------------------------------

    def run(self, duration: float | None = None) -> None:
        next_t = time.monotonic()
        while duration is None or self.world.t < duration:
            if self.reset_requested:
                self.reset_requested = False
                self.world.reset()
            state = self.world.tick()
            state["goals"] = self.world.scenario.goals()
            state["markers"] = self.world.scenario.markers()
            state["type"] = "state"
            payload = json.dumps(state).encode()
            self.latest = payload
            self._broadcast(payload + b"\n")
            if self.realtime:
                next_t += PERIOD
                delay = next_t - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                elif delay < -1.0:
                    next_t = time.monotonic()
