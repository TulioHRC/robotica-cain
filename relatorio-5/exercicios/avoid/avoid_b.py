#!/usr/bin/env python3
import sys

sys.dont_write_bytecode = True

from avoid import Avoid


class AvoidB(Avoid):
    CONFIG = "B"
    V_LIN = 0.20
    D_LENTO = 0.20
    D_PARE = 0.06
    D_GIRO = 0.09
    D_LIVRE = 0.14
    D_INF = 0.20


if __name__ == "__main__":
    AvoidB().run()
