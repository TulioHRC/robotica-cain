#!/usr/bin/env python3
import sys

sys.dont_write_bytecode = True

from avoid import Avoid


class AvoidSemVies(Avoid):
    CONFIG = "SV"
    W_VAG = 0.0


if __name__ == "__main__":
    AvoidSemVies().run()
