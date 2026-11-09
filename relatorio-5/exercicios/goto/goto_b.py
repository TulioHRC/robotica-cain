#!/usr/bin/env python3
import sys

sys.dont_write_bytecode = True

from goto import Goto


class GotoB(Goto):
    CONFIG = "B"
    K_ALPHA = 1.0


if __name__ == "__main__":
    GotoB().run()
