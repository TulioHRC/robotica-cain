# -*- coding: utf-8 -*-

# Macro Begin:
from math import cos, pi, radians, sin, tan
import FreeCAD
import InvoluteGearFeature
import Part
from FreeCAD import Base


def makeGear(
    name,
    teeth,
    pressureAngle=20,
    module=1,
    helixAngle=10,
    height=10,
    bore=0,
    external=True,
    position=Base.Vector(0.00, 0.00, 0.00),
    rotation=0,
    extrude=False,
):
    # Gui.activateWorkbench("PartDesignWorkbench")
    involute = InvoluteGearFeature.makeInvoluteGear(name + "_involute")
    involute.NumberOfTeeth = teeth
    involute.ExternalGear = external
    involute.HighPrecision = True
    involute.PressureAngle = pressureAngle
    involute.Modules = module

    involuteRadius = module * teeth / 2.0

    doc = App.ActiveDocument

    if extrude:
        helix = doc.addObject("Part::Helix", name + "_helix")
        helix.Pitch = pi * 2.0 * involuteRadius * tan(pi * (90 - abs(helixAngle)) / 180.0)
        helix.Height = height
        helix.Radius = involuteRadius
        helix.Angle = 0.00
        if helixAngle > 0:
            helix.LocalCoord = 0
        else:
            helix.LocalCoord = 1

        helix.Style = 1
        helix.Placement = Base.Placement(
            Base.Vector(0.00, 0.00, 0.00),
            Base.Rotation(0.00, 0.00, 0.00, 1.00),
        )
        helix.Label = name + "_helix"
        App.ActiveDocument.recompute()

        sweep = doc.addObject("Part::Sweep", name)
        sweep.Sections = doc.getObject(name + "_involute")
        sweep.Spine = (doc.getObject(name + "_helix"), [])
        sweep.Solid = True
        sweep.Frenet = True

        sweep.Placement = Base.Placement(
            position, Base.Rotation(Base.Vector(0.0, 0.0, 1.0), rotation)
        )
        App.ActiveDocument.recompute()
        Gui.ActiveDocument.getObject(name + "_involute").Visibility = False

        if external:  # make bore
            if bore > 0:
                cylinder = doc.addObject("Part::Cylinder", name + "_bore")
                cylinder.Label = name + "_bore"
                cylinder.Radius = bore / 2.0
                cylinder.Height = height + 0.1
                cylinder.Placement = Base.Placement(
                    position,
                    Base.Rotation(Base.Vector(0.0, 0.0, 1.0), rotation),
                )

                cut = doc.addObject("Part::Cut", name + "_ext")
                cut.Base = doc.getObject(name)
                cut.Tool = doc.getObject(name + "_bore")
        else:  # make external ring
            cylinder = doc.addObject("Part::Cylinder", name + "_exthousing")
            cylinder.Label = name + "_exthousing"
            cylinder.Radius = involuteRadius + 10
            cylinder.Height = height - 0.1
            cylinder.Placement = Base.Placement(
                position, Base.Rotation(Base.Vector(0.0, 0.0, 1.0), rotation)
            )

            cut = doc.addObject("Part::Cut", name + "_ext")
            cut.Base = doc.getObject(name + "_exthousing")
            cut.Tool = doc.getObject(name)

    else:
        involute.Placement = Base.Placement(
            position, Base.Rotation(Base.Vector(0.0, 0.0, 1.0), rotation)
        )
    App.ActiveDocument.recompute()


def makePlanetary(
    name,
    module=1.25,
    sun_teeth=20,
    planet_teeth=20,
    z_off=0,
    helix=10,
    height=10,
    extrude=True,
    bore=0,
):
    ring_teeth = 2 * planet_teeth + sun_teeth
    mesh_distance = (sun_teeth + planet_teeth) * module / 2.0

    planet_rotation = (1 - (planet_teeth % 2)) * 180.0 / planet_teeth
    ring_rotation = 180.0 / ring_teeth + planet_rotation * planet_teeth / ring_teeth

    makeGear(
        name + "_sun",
        teeth=sun_teeth,
        pressureAngle=20,
        module=module,
        helixAngle=helix,
        height=height,
        bore=bore,
        position=Base.Vector(0.00, 0.00, z_off),
        rotation=0,
        extrude=extrude,
    )

    makeGear(
        name + "_ring",
        teeth=ring_teeth,
        pressureAngle=20,
        module=module,
        helixAngle=-helix,
        height=height,
        bore=bore,
        position=Base.Vector(0.0, 0.00, z_off),
        rotation=ring_rotation,
        external=False,
        extrude=extrude,
    )

    planet_angles = [0, 60, 120]

    for i, angle in enumerate(planet_angles):
        theta = radians(angle)
        x = mesh_distance * cos(theta)
        y = mesh_distance * sin(theta)
        makeGear(
            name + "_planet" + str(i + 1),
            teeth=planet_teeth,
            pressureAngle=20,
            module=module,
            helixAngle=-helix,
            height=height,
            bore=bore,
            position=Base.Vector(x, y, z_off),
            rotation=planet_rotation + angle,
            extrude=extrude,
        )

    App.ActiveDocument.recompute()


makePlanetary(
    "first",
    sun_teeth=34,
    planet_teeth=16,
    z_off=0,
    helix=15,
    height=10,
    bore=6,
)

Gui.SendMsgToActiveView("ViewFit")