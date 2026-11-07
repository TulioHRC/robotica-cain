"""Entry point: python -m psr_sim --scenario avoid --robots 2"""

from __future__ import annotations

import argparse
import time

from .scenarios import SCENARIOS
from .server import Hub
from .world import World


def main() -> None:
    p = argparse.ArgumentParser(prog="psr_sim", description=__doc__)
    p.add_argument("--scenario", choices=sorted(SCENARIOS), default="avoid")
    p.add_argument("--robots", type=int, default=None, help="number of HeRo robots")
    p.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    p.add_argument("--viewer", action="store_true", help="open the Genesis 3D window (needs a display)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--tcp-port", type=int, default=11312)
    p.add_argument("--http-port", type=int, default=0, help="serve the web view on this port (0: off)")
    p.add_argument("--fps", type=int, default=30, help="refresh rate of the Genesis window")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--fast", action="store_true", help="do not pace the simulation to real time")
    p.add_argument("--duration", type=float, default=None, help="stop after this many simulated seconds")
    args = p.parse_args()

    scenario = SCENARIOS[args.scenario](args.robots, args.seed)
    world = World(scenario, backend=args.backend, viewer=args.viewer, fps=args.fps)
    hub = Hub(world, args.host, args.tcp_port, realtime=not args.fast)
    where = [f"bridge on tcp/{args.tcp_port}"]
    if args.http_port:
        from .web import start_web  # not shipped in the student kit

        start_web(hub, args.host, args.http_port)
        where.append(f"web view on http://localhost:{args.http_port}")
    print(f"scenario '{scenario.name}' with {scenario.n} robot(s): {', '.join(where)}", flush=True)
    t0 = time.monotonic()
    try:
        hub.run(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        wall = time.monotonic() - t0
        if args.duration:
            print(f"simulated {world.t:.0f} s in {wall:.1f} s of wall time ({world.t / wall:.1f}x real time)", flush=True)
        world.close()


if __name__ == "__main__":
    main()
