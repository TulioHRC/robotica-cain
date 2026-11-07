"""Genesis physics world: planar HeRo robots, obstacles, walls and a puck.

Every movable body hangs from a fixed anchor through two slide joints and one
hinge (x, y, yaw), so the simulation is 2D with full 3D contact handling. A
robot is a velocity-controlled body with a force limit, which keeps the
differential-drive constraint (no lateral velocity) and makes pushing contests
depend on traction, as on the real robot.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np

from .geometry import ROBOT_RADIUS, cast_beams, wrap_angle
from .scenarios.base import Pose, Scenario

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "hero"

DT = 0.01  # physics step (s)
SUBSTEPS = 2  # physics steps per control tick (50 Hz)

Z0 = 0.0105  # height of the base_link origin above the floor
WALL_HEIGHT = 0.06

V_MAX = 0.20  # m/s, limit applied to /cmd_vel
W_MAX = 4.0  # rad/s
ROBOT_MASS = 0.15  # kg
FORCE_MAX = 0.20  # N, wheel traction limit
TORQUE_MAX = 4e-3  # N m
KV_LIN = 3.0
KV_YAW = 3e-3
ROBOT_FRICTION = 0.1  # plastic shells slide on each other
CMD_TIMEOUT = 0.5  # s without /cmd_vel: stop (the firmware does the same)

HAT_OFFSET = (-0.00245, -0.00216, 0.06027)  # hat_joint of hero_description/urdf/hero.xacro
HAT_MESH = ASSETS / "hat.obj"
FLAG_MESH = ASSETS / "flag.obj"
FLAG_SCALE = 1.0


def _np(x) -> np.ndarray:
    if hasattr(x, "detach"):
        x = x.detach().cpu().numpy()
    return np.asarray(x, dtype=float)


def _planar_chain(name: str, tip_link: str, with_z: bool = False) -> str:
    """URDF fragment: fixed anchor + x/y slide + yaw hinge ending in link `tip_link`.

    With `with_z` a free vertical slide follows the hinge, so the body can fall
    off an elevated platform (dof order: x, y, yaw, z).
    """
    tiny = '<inertial><mass value="0.001"/><inertia ixx="1e-7" iyy="1e-7" izz="1e-7" ixy="0" ixz="0" iyz="0"/></inertial>'
    spin_child = "yaw_link" if with_z else tip_link
    z_joint = f"""
  <link name="yaw_link">{tiny}</link>
  <joint name="slide_z" type="prismatic">
    <parent link="yaw_link"/><child link="{tip_link}"/><axis xyz="0 0 1"/>
    <limit lower="-1" upper="1" effort="100" velocity="10"/>
  </joint>""" if with_z else ""
    return f"""
  <link name="anchor">{tiny}</link>
  <link name="x_link">{tiny}</link>
  <link name="y_link">{tiny}</link>
  <joint name="slide_x" type="prismatic">
    <parent link="anchor"/><child link="x_link"/><axis xyz="1 0 0"/>
    <limit lower="-100" upper="100" effort="100" velocity="10"/>
  </joint>
  <joint name="slide_y" type="prismatic">
    <parent link="x_link"/><child link="y_link"/><axis xyz="0 1 0"/>
    <limit lower="-100" upper="100" effort="100" velocity="10"/>
  </joint>
  <joint name="spin" type="continuous">
    <parent link="y_link"/><child link="{spin_child}"/><axis xyz="0 0 1"/>
  </joint>{z_joint}"""


def hat_mesh(path: Path, rgb: tuple[float, float, float]) -> Path:
    """Copy of the real HeRo hat mesh with a material of the given colour."""
    mtl = path.with_suffix(".mtl")
    mtl.write_text(f"newmtl hat\nKd {rgb[0]} {rgb[1]} {rgb[2]}\nKa {rgb[0]} {rgb[1]} {rgb[2]}\nKs 0.1 0.1 0.1\nd 1\n")
    lines = []
    for line in HAT_MESH.read_text().splitlines():
        if line.startswith("mtllib"):
            line = f"mtllib {mtl.name}\nusemtl hat"
        lines.append(line)
    path.write_text("\n".join(lines) + "\n")
    return path


def flag_mesh(path: Path, rgb: tuple[float, float, float]) -> Path:
    """Copy of the HeRo flag mesh whose cloth has the given colour (the pole stays dark)."""
    mtl = path.with_suffix(".mtl")
    mtl.write_text(
        "newmtl color_2829873\nKd 0.17 0.18 0.19\nKa 0.05 0.05 0.05\nKs 0.3 0.3 0.3\nd 1\n\n"
        f"newmtl color_15277357\nKd {rgb[0]} {rgb[1]} {rgb[2]}\nKa 0.05 0.05 0.05\nKs 0.3 0.3 0.3\nd 1\n"
    )
    text = FLAG_MESH.read_text().replace("mtllib flag.mtl", f"mtllib {mtl.name}")
    path.write_text(text)
    return path


def flag_urdf(name: str, mesh: Path) -> str:
    """A flag with no collision, moved by hand through its x/y/yaw joints."""
    return f"""<?xml version="1.0"?>
<robot name="{name}">{_planar_chain(name, "flag_link")}
  <link name="flag_link">
    <inertial><mass value="0.001"/><inertia ixx="1e-7" iyy="1e-7" izz="1e-7" ixy="0" ixz="0" iyz="0"/></inertial>
    <visual><geometry><mesh filename="{mesh}" scale="{FLAG_SCALE} {FLAG_SCALE} {FLAG_SCALE}"/></geometry></visual>
  </link>
</robot>
"""


def hero_urdf(name: str, rgb: tuple[float, float, float], hat: Path, with_z: bool = False) -> str:
    m, r, h = ROBOT_MASS, ROBOT_RADIUS, 0.042
    izz = 0.5 * m * r * r
    ixx = m * (3 * r * r + h * h) / 12.0
    body = ASSETS / "base_link.obj"
    wheel = ASSETS / "wheel.obj"
    return f"""<?xml version="1.0"?>
<robot name="{name}">{_planar_chain(name, "base_link", with_z)}
  <link name="base_link">
    <inertial><origin xyz="0 0 0.0121"/><mass value="{m}"/>
      <inertia ixx="{ixx}" iyy="{ixx}" izz="{izz}" ixy="0" ixz="0" iyz="0"/></inertial>
    <collision><origin xyz="0 0 0.0121"/><geometry><cylinder radius="{r}" length="{h}"/></geometry></collision>
    <visual><origin rpy="0 0 1.5708"/><geometry><mesh filename="{body}"/></geometry></visual>
    <visual><origin xyz="0 0.0323 0.01548"/><geometry><mesh filename="{wheel}"/></geometry></visual>
    <visual><origin rpy="-3.14159 0 0" xyz="0 -0.0323 0.01548"/><geometry><mesh filename="{wheel}"/></geometry></visual>
    <visual><origin xyz="{HAT_OFFSET[0]} {HAT_OFFSET[1]} {HAT_OFFSET[2]}"/><geometry><mesh filename="{hat}"/></geometry></visual>
  </link>
</robot>
"""


def puck_urdf(radius: float, mass: float, rgb) -> str:
    """A ball: a sphere that slides (2D) with very low friction."""
    i = 0.4 * mass * radius * radius
    return f"""<?xml version="1.0"?>
<robot name="puck">{_planar_chain("puck", "puck_link")}
  <link name="puck_link">
    <inertial><origin xyz="0 0 0.0121"/><mass value="{mass}"/>
      <inertia ixx="{i}" iyy="{i}" izz="{i}" ixy="0" ixz="0" iyz="0"/></inertial>
    <collision><origin xyz="0 0 0.0121"/><geometry><sphere radius="{radius}"/></geometry></collision>
    <visual><origin xyz="0 0 0.0121"/><geometry><sphere radius="{radius}"/></geometry>
      <material name="puck"><color rgba="{rgb[0]} {rgb[1]} {rgb[2]} 1"/></material></visual>
  </link>
</robot>
"""


class World:
    def __init__(self, scenario: Scenario, backend: str = "cpu", viewer: bool = False, fps: int = 30):
        import genesis as gs

        self.gs = gs
        self.scenario = scenario
        self.viewer = viewer
        self._marker_nodes: dict = {}
        self._caption_key = None
        self.shown = ""
        self.n = scenario.n
        self.t = 0.0
        self.tmp = tempfile.TemporaryDirectory(prefix="psr_sim_")

        gs.init(backend=gs.gpu if backend == "gpu" else gs.cpu, logging_level="warning")
        # an elevated platform (sumo) needs gravity and a free vertical joint
        self.platform = scenario.platform()
        self.ndof = 4 if self.platform else 3
        self.z_top = self.platform["h"] if self.platform else 0.0
        self.scene = gs.Scene(
            sim_options=gs.options.SimOptions(dt=DT, gravity=(0.0, 0.0, -9.81 if self.platform else 0.0)),
            rigid_options=gs.options.RigidOptions(
                enable_collision=True,
                enable_self_collision=False,
                enable_joint_limit=False,
            ),
            viewer_options=gs.options.ViewerOptions(
                camera_pos=(0.0, -2.6, 2.4), camera_lookat=(0.0, 0.0, 0.0), camera_fov=40,
                refresh_rate=fps,  # software rendering (no GPU) keeps up better at 30 fps
                enable_help_text=False,  # its overlay covers the scoreboard caption
            ),
            show_viewer=viewer,
        )

        self.statics = scenario.statics()
        self.circles = np.array(
            [[s.x, s.y, s.r] for s in self.statics if s.kind == "circle" and s.solid]
        ).reshape(-1, 3)
        self.segments = np.array(
            [seg for s in self.statics if s.solid for seg in s.segments()]
        ).reshape(-1, 4)
        if not self.platform:  # neutral surround so the arena does not float in a void
            self.scene.add_entity(
                gs.morphs.Box(size=(6.0, 6.0, 0.01), pos=(0.0, 0.0, -0.0065), fixed=True, collision=False),
                surface=gs.surfaces.Default(color=(0.80, 0.81, 0.84, 1.0)),
            )
        for s in self.statics:
            self._add_static(s)
        if self.platform:
            self._add_platform(self.platform)

        self.colors = scenario.colors()
        self.robots = []
        for i, rgb in enumerate(self.colors):
            path = Path(self.tmp.name) / f"hero_{i}.urdf"
            hat = hat_mesh(Path(self.tmp.name) / f"hat_{i}.obj", rgb)
            path.write_text(hero_urdf(f"hero_{i}", rgb, hat, with_z=bool(self.platform)))
            self.robots.append(
                self.scene.add_entity(gs.morphs.URDF(file=str(path), fixed=True, pos=(0, 0, Z0)))
            )

        self.flag_ents = []
        for k, spec in enumerate(scenario.flags()):
            mesh = flag_mesh(Path(self.tmp.name) / f"flag_{k}.obj", spec["color"])
            path = Path(self.tmp.name) / f"flag_{k}.urdf"
            path.write_text(flag_urdf(f"flag_{k}", mesh))
            self.flag_ents.append(self.scene.add_entity(gs.morphs.URDF(file=str(path), fixed=True, pos=(0, 0, 0))))

        self.puck = None
        spec = scenario.puck_spec()
        self.puck_spec = spec
        if spec is not None:
            path = Path(self.tmp.name) / "puck.urdf"
            path.write_text(puck_urdf(spec.radius, spec.mass, spec.color))
            self.puck = self.scene.add_entity(gs.morphs.URDF(file=str(path), fixed=True, pos=(0, 0, Z0)))

        self.scene.build()
        self._configure()

        self.cmd = np.zeros((self.n, 2))
        self.cmd_t = np.full(self.n, -1e9)
        self.led = [tuple(c) for c in self.colors]
        self.pending = None
        self.message = ""
        self.fallen = [False] * self.n
        self.last: dict | None = None
        self.teleport(scenario.spawn(), scenario.puck_spawn())

    # --- construction ---------------------------------------------------------

    def _add_static(self, s) -> None:
        gs = self.gs
        surface = gs.surfaces.Default(color=(*s.color, 1.0))
        if s.solid:
            thick, zc, solid = s.height or WALL_HEIGHT, (s.height or WALL_HEIGHT) / 2, True
        elif s.height:  # tall but not solid (goal posts)
            thick, zc, solid = s.height, s.height / 2, False
        else:  # paint: a thin slab, each layer a little higher
            thick, solid = 0.002, False
            zc = s.layer * 0.0006 - thick / 2
        kw = {"fixed": True} if solid else {"fixed": True, "collision": False}
        if s.kind == "box":
            morph = gs.morphs.Box(size=(s.w, s.h, thick), pos=(s.x, s.y, zc), **kw)
        elif s.kind == "ring":
            import trimesh

            self._rings = getattr(self, "_rings", 0) + 1
            path = Path(self.tmp.name) / f"ring_{self._rings}.obj"
            trimesh.creation.annulus(r_min=s.r - s.w, r_max=s.r, height=thick, sections=72).export(str(path))
            morph = gs.morphs.Mesh(file=str(path), pos=(s.x, s.y, zc), **kw)
        else:
            morph = gs.morphs.Cylinder(radius=s.r, height=thick, pos=(s.x, s.y, zc), **kw)
        self.scene.add_entity(morph, surface=surface)

    def _add_platform(self, spec: dict) -> None:
        """Raised ring, drawn only: a robot is held at the platform height by its
        vertical joint while its centre is inside spec['r'] and is released (it
        falls to the floor) as soon as the centre crosses the edge. Holding it
        by control keeps floor friction out of the pushing contest.
        """
        gs = self.gs
        r, h = spec["r"], spec["h"]
        self.scene.add_entity(gs.morphs.Plane(), surface=gs.surfaces.Default(color=(0.78, 0.78, 0.8, 1.0)))
        self.scene.add_entity(
            gs.morphs.Cylinder(radius=r + 0.012, height=h - 0.0015, pos=(0.0, 0.0, (h - 0.0015) / 2),
                               fixed=True, collision=False),
            surface=gs.surfaces.Default(color=(0.95, 0.95, 0.95, 1.0)),
        )
        self.scene.add_entity(
            gs.morphs.Cylinder(radius=r, height=h - 0.0005, pos=(0.0, 0.0, (h - 0.0005) / 2),
                               fixed=True, collision=False),
            surface=gs.surfaces.Default(color=(0.12, 0.12, 0.14, 1.0)),
        )

    def _configure(self) -> None:
        dofs = np.arange(3)
        kv = np.array([KV_LIN, KV_LIN, KV_YAW])
        fmax = np.array([FORCE_MAX, FORCE_MAX, TORQUE_MAX])
        for robot in self.robots:
            robot.set_dofs_armature(np.full(3, 1e-6), dofs)
            robot.set_dofs_kp(np.zeros(3), dofs)
            robot.set_dofs_kv(kv, dofs)
            robot.set_dofs_force_range(-fmax, fmax, dofs)
            robot.get_link("base_link").set_friction(ROBOT_FRICTION)
            if self.platform:  # vertical joint: pure gravity, no drive
                robot.set_dofs_armature(np.full(1, 1e-6), np.array([3]))
                robot.set_dofs_kp(np.full(1, 4000.0), np.array([3]))
                robot.set_dofs_kv(np.full(1, 60.0), np.array([3]))
        for flag in self.flag_ents:
            flag.set_dofs_armature(np.full(3, 1e-6), dofs)
            flag.set_dofs_kp(np.zeros(3), dofs)
            flag.set_dofs_kv(np.zeros(3), dofs)
        if self.puck is not None:
            spec = self.puck_spec
            fric = spec.friction * spec.mass * 9.81  # Coulomb friction as a force limit
            self.puck.set_dofs_armature(np.full(3, 1e-6), dofs)
            self.puck.set_dofs_kp(np.zeros(3), dofs)
            self.puck.set_dofs_kv(np.array([1.0, 1.0, 1e-3]), dofs)
            self.puck.set_dofs_force_range(
                -np.array([fric, fric, fric * spec.radius]), np.array([fric, fric, fric * spec.radius]), dofs
            )
            self.puck.get_link("puck_link").set_friction(0.1)
            self.puck.control_dofs_velocity(np.zeros(3), dofs)

    # --- state ------------------------------------------------------------------

    def teleport(self, poses: list[Pose], puck: Pose | None = None) -> None:
        dofs = np.arange(3)
        for robot, p in zip(self.robots, poses):
            if p is None:
                continue
            pos = [p.x, p.y, p.yaw] + ([self.z_top] if self.platform else [])
            robot.set_dofs_position(np.array(pos), np.arange(self.ndof), zero_velocity=True)
            robot.control_dofs_velocity(np.zeros(3), dofs)
        if self.puck is not None and puck is not None:
            self.puck.set_dofs_position(np.array([puck.x, puck.y, 0.0]), dofs, zero_velocity=True)
            self.puck.control_dofs_velocity(np.zeros(3), dofs)
        self.cmd[:] = 0.0
        self.fallen = [False] * self.n
        self.scene.step()  # refresh contacts after the jump

    def read(self) -> dict:
        """Ground-truth state plus the lidar of every robot."""
        pos = [_np(r.get_dofs_position()) for r in self.robots]
        vel = [_np(r.get_dofs_velocity()) for r in self.robots]
        robots = []
        for i in range(self.n):
            x, y, yaw = pos[i][:3]
            yaw = wrap_angle(yaw)
            vx, vy, w = vel[i][:3]
            circles = [self.circles]
            others = [[pos[j][0], pos[j][1], ROBOT_RADIUS] for j in range(self.n) if j != i]
            if others:
                circles.append(np.array(others))
            puck = None
            if self.puck is not None:
                pp = _np(self.puck.get_dofs_position())
                pv = _np(self.puck.get_dofs_velocity())
                puck = {"x": pp[0], "y": pp[1], "vx": pv[0], "vy": pv[1], "r": self.puck_spec.radius}
                circles.append(np.array([[pp[0], pp[1], self.puck_spec.radius]]))
            ranges = cast_beams(np.array([x, y]), yaw, np.vstack(circles), self.segments)
            robots.append({
                "id": i, "x": float(x), "y": float(y), "yaw": float(yaw),
                "z": float(pos[i][3]) if self.platform else 0.0,
                "v": float(vx * math.cos(yaw) + vy * math.sin(yaw)), "w": float(w),
                "ranges": [round(float(r), 4) for r in ranges],
                "color": [float(c) for c in self.led[i]],
                "held": bool(self.scenario.held(i)),
            })
        if self.puck is None:
            puck = None
        return {"t": self.t, "robots": robots, "puck": puck}

    # --- stepping -----------------------------------------------------------------

    def set_cmd(self, i: int, lin: float, ang: float) -> None:
        self.cmd[i] = (np.clip(lin, -V_MAX, V_MAX), np.clip(ang, -W_MAX, W_MAX))
        self.cmd_t[i] = self.t

    def set_led(self, i: int, rgb) -> None:
        self.led[i] = tuple(rgb)

    def tick(self) -> dict:
        """One control period: referee, controls, SUBSTEPS physics steps."""
        sc = self.scenario
        state = self.read()
        sc.t = self.t

        if self.pending is not None and self.t >= sc.paused_until:
            ev, self.pending = self.pending, None
            if ev.poses:
                self.teleport(ev.poses, ev.puck)
            elif ev.puck is not None:
                self.teleport([], ev.puck)
            sc.round_start = self.t
            self.message = ""
            state = self.read()
        if self.pending is None:
            ev = sc.referee(state["robots"], state["puck"])
            if ev is not None:
                self.pending = ev
                sc.paused_until = self.t + ev.pause
                self.message = ev.message
        self._sync_markers()
        self._sync_flags()
        self._sync_captions()

        frozen = self.pending is not None
        dofs = np.arange(3)
        for i, robot in enumerate(self.robots):
            if frozen or sc.held(i) or self.t - self.cmd_t[i] > CMD_TIMEOUT:
                target = np.zeros(3)
            else:
                lin, ang = self.cmd[i]
                yaw = state["robots"][i]["yaw"]
                target = np.array([lin * math.cos(yaw), lin * math.sin(yaw), ang])
            robot.control_dofs_velocity(target, dofs)
            if self.platform:
                r = state["robots"][i]
                if math.hypot(r["x"], r["y"]) > self.platform["r"]:
                    self.fallen[i] = True
                if self.fallen[i]:
                    robot.control_dofs_force(np.zeros(1), np.array([3]))  # free fall
                else:
                    robot.control_dofs_position(np.array([self.z_top]), np.array([3]))

        for _ in range(SUBSTEPS):
            self.scene.step()
            self.t += DT
        self.shown = self.message or sc.notice()
        state["message"] = self.shown
        state["game"] = sc.public()
        self.last = state
        return state

    def _sync_captions(self) -> None:
        """Scoreboard (top) and the referee's message (centre) as text in the Genesis window."""
        if not self.viewer:
            return
        text = self.scenario.scoreboard()
        shown = self.message or self.scenario.notice()
        key = (text, shown)
        if key == self._caption_key:
            return
        self._caption_key = key
        pv = self.scene.visualizer.viewer._pyrender_viewer
        if pv is None:
            return
        from genesis.ext.pyrender.constants import TextAlign

        captions = []
        if text:
            captions.append({"text": text, "location": TextAlign.TOP_CENTER, "font_name": "OpenSans-Bold",
                             "font_pt": 30, "color": (0.10, 0.10, 0.13, 1.0), "scale": 1.0})
        if shown:
            captions.append({"text": shown, "location": TextAlign.CENTER, "font_name": "OpenSans-Bold",
                             "font_pt": 44, "color": (0.59, 0.04, 0.13, 1.0), "scale": 1.0})
        pv.viewer_flags["caption"] = captions or None

    def _sync_flags(self) -> None:
        for ent, spec in zip(self.flag_ents, self.scenario.flags()):
            ent.set_dofs_position(np.array([spec["x"], spec["y"], 0.0]), np.arange(3), zero_velocity=True)

    def _sync_markers(self) -> None:
        """Show the scenario's targets (go-to-goal) as spheres in the Genesis window."""
        if not self.viewer:
            return
        wanted = {
            m["id"]: m for m in self.scenario.markers() if m.get("kind") == "target" and "id" in m
        }
        for key, (xy, node) in list(self._marker_nodes.items()):
            m = wanted.get(key)
            if m is None or (m["x"], m["y"]) != xy:
                self.scene.clear_debug_object(node)
                del self._marker_nodes[key]
        for key, m in wanted.items():
            if key not in self._marker_nodes:
                node = self.scene.draw_debug_sphere(
                    pos=(m["x"], m["y"], 0.03), radius=m["r"], color=(*m["color"], 0.85)
                )
                self._marker_nodes[key] = ((m["x"], m["y"]), node)

    def close(self) -> None:
        self.tmp.cleanup()

    def reset(self) -> None:
        """Restart the scoreboard and put everything back at the spawn poses."""
        self.pending = None
        self.message = ""
        self.scenario.paused_until = -1.0
        self.scenario.reset()
        self.scenario.round_start = self.t
        self.teleport(self.scenario.spawn(), self.scenario.puck_spawn())
