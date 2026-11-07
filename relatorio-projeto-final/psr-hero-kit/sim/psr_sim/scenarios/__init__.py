from .avoid import Avoid
from .base import Scenario
from .ctf import CaptureTheFlag
from .goto import Goto
from .soccer import Soccer
from .sumo import Sumo

SCENARIOS: dict[str, type[Scenario]] = {
    cls.name: cls for cls in (Avoid, Goto, CaptureTheFlag, Sumo, Soccer)
}
