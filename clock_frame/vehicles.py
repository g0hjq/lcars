"""
vehicles.py

The city clock's cars, vans, taxis and buses, made in 3D. Each is built from its side view (the
shape of its body, its windows, doors and lamps), widened into a solid: rounded at the corners
seen from above, its glass leaning in towards the roof and its lower panels curving under. It
is then seen from where you stand (above the road, a little way back) at several places across
the screen, so that its roof shows, and its front as it comes towards you and its back as it
goes away. Each picture is shaded by which way each bit of it faces: the light from the sky
above, and the sky (and the road below the horizon) reflected in its paint and glass.

It is drawn as a cloud of points, more than one to each pixel, the nearest kept at each pixel,
twice as big as it is shown, then shrunk for smooth edges. Its pictures are made once, when the
city clock is first shown.
"""

import math
import numpy as np
import pygame
from .common import smoothstep, toSurface

# The vehicles, seen from the side facing right. x goes from the back (0) to the front (1) and
# y from the top of the roof (0) to the road (1). outline is the top of the body, from the
# bottom of the back bumper over the roof to the bottom of the front one; glass is each window;
# pillars are the posts between the windows, seams the shut lines of the doors, belt the bottom
# of the windows, sill the bottom of the body, and head and tail the lamps (x0, y0, x1, y1). The
# wheels are at wheelX, wheel times the length across. width is how wide it is (times its
# length), corner how round its corners are seen from above (times half its width), tumble how
# far its glass leans in, and tuck how far its lower panels curve under.
VEHICLES = {
    "saloon": dict(length=76, ratio=0.31, width=0.39, corner=0.55, tumble=0.2, tuck=0.07,
                   wheelX=(0.18, 0.80), wheel=0.072, belt=0.37, sill=0.86,
                   outline=[(0.0, 0.80), (0.0, 0.50), (0.02, 0.40), (0.21, 0.36), (0.28, 0.33), (0.37, 0.07), (0.46, 0.02),
                            (0.60, 0.02), (0.68, 0.08), (0.77, 0.34), (0.95, 0.41), (1.0, 0.52), (1.0, 0.80)],
                   glass=[[(0.30, 0.36), (0.38, 0.10), (0.46, 0.06), (0.60, 0.06), (0.665, 0.11), (0.745, 0.36)]],
                   pillars=[0.52], seams=[0.33, 0.52, 0.72], head=(0.95, 0.43, 1.0, 0.51), tail=(0.0, 0.42, 0.035, 0.52)),
    "hatch": dict(length=68, ratio=0.37, width=0.42, corner=0.55, tumble=0.2, tuck=0.07,
                  wheelX=(0.17, 0.81), wheel=0.078, belt=0.40, sill=0.85,
                  outline=[(0.0, 0.80), (0.0, 0.45), (0.01, 0.30), (0.04, 0.12), (0.10, 0.04), (0.55, 0.03), (0.63, 0.10),
                           (0.74, 0.38), (0.95, 0.45), (1.0, 0.55), (1.0, 0.80)],
                  glass=[[(0.05, 0.40), (0.07, 0.16), (0.12, 0.08), (0.55, 0.07), (0.61, 0.12), (0.71, 0.40)]],
                  pillars=[0.16, 0.42], seams=[0.42, 0.70], head=(0.95, 0.46, 1.0, 0.54), tail=(0.0, 0.38, 0.03, 0.50)),
    "estate": dict(length=80, ratio=0.32, width=0.38, corner=0.5, tumble=0.18, tuck=0.07,
                   wheelX=(0.18, 0.80), wheel=0.07, belt=0.37, sill=0.86,
                   outline=[(0.0, 0.80), (0.0, 0.45), (0.01, 0.12), (0.04, 0.04), (0.60, 0.03), (0.68, 0.09), (0.77, 0.35),
                            (0.95, 0.42), (1.0, 0.52), (1.0, 0.80)],
                   glass=[[(0.04, 0.37), (0.05, 0.11), (0.08, 0.07), (0.59, 0.07), (0.665, 0.12), (0.745, 0.37)]],
                   pillars=[0.24, 0.50], seams=[0.31, 0.50, 0.71], head=(0.95, 0.44, 1.0, 0.52), tail=(0.0, 0.40, 0.03, 0.50)),
    "suv": dict(length=80, ratio=0.42, width=0.42, corner=0.45, tumble=0.14, tuck=0.05, trim=0.70,
                wheelX=(0.17, 0.82), wheel=0.085, belt=0.42, sill=0.82,
                outline=[(0.0, 0.82), (0.0, 0.15), (0.03, 0.04), (0.62, 0.03), (0.72, 0.10), (0.80, 0.37), (0.97, 0.41),
                         (1.0, 0.50), (1.0, 0.82)],
                glass=[[(0.03, 0.40), (0.04, 0.12), (0.07, 0.08), (0.61, 0.08), (0.70, 0.13), (0.775, 0.40)]],
                pillars=[0.25, 0.49], seams=[0.29, 0.49, 0.74], head=(0.95, 0.43, 1.0, 0.51), tail=(0.0, 0.30, 0.03, 0.44)),
    "van": dict(length=88, ratio=0.52, width=0.40, corner=0.3, tumble=0.08, tuck=0.03, trim=0.80,
                wheelX=(0.16, 0.83), wheel=0.07, belt=0.36, sill=0.86,
                outline=[(0.0, 0.84), (0.0, 0.04), (0.02, 0.01), (0.74, 0.01), (0.80, 0.07), (0.87, 0.33), (0.98, 0.41),
                         (1.0, 0.55), (1.0, 0.84)],
                glass=[[(0.765, 0.37), (0.775, 0.11), (0.80, 0.09), (0.855, 0.36)]],
                pillars=[], seams=[0.44, 0.70, 0.75, 0.88], head=(0.955, 0.46, 1.0, 0.54), tail=(0.0, 0.50, 0.025, 0.66)),
    "taxi": dict(length=74, ratio=0.40, width=0.40, corner=0.5, tumble=0.15, tuck=0.06, sign=True,
                 wheelX=(0.18, 0.81), wheel=0.072, belt=0.42, sill=0.86,
                 outline=[(0.0, 0.80), (0.0, 0.44), (0.03, 0.30), (0.08, 0.08), (0.14, 0.03), (0.62, 0.03), (0.69, 0.10),
                          (0.76, 0.40), (0.95, 0.45), (1.0, 0.55), (1.0, 0.80)],
                 glass=[[(0.08, 0.40), (0.11, 0.13), (0.15, 0.08), (0.36, 0.08), (0.36, 0.40)],
                        [(0.40, 0.40), (0.40, 0.08), (0.62, 0.08), (0.67, 0.14), (0.73, 0.40)]],
                 pillars=[0.56], seams=[0.38, 0.56, 0.74], head=(0.955, 0.45, 1.0, 0.55), tail=(0.0, 0.42, 0.03, 0.52)),
    "double": dict(length=176, ratio=0.70, width=0.23, corner=0.25, tumble=0.03, tuck=0.01, bus=True,
                   wheelX=(0.16, 0.76), wheel=0.06, belt=0.50, sill=0.92,
                   outline=[(0.0, 0.92), (0.0, 0.05), (0.02, 0.0), (0.97, 0.0), (1.0, 0.05), (1.0, 0.92)],
                   glass=[[(x, 0.10), (x + 0.088, 0.10), (x + 0.088, 0.36), (x, 0.36)] for x in np.arange(0.03, 0.92, 0.097)] +
                         [[(0.95, 0.10), (0.995, 0.10), (0.995, 0.38), (0.95, 0.38)]] +
                         [[(x, 0.50), (x + 0.088, 0.50), (x + 0.088, 0.73), (x, 0.73)] for x in np.arange(0.03, 0.78, 0.097)] +
                         [[(0.81, 0.48), (0.90, 0.48), (0.90, 0.88), (0.81, 0.88)], [(0.93, 0.48), (0.995, 0.48), (0.995, 0.80), (0.93, 0.80)]],
                   pillars=[], seams=[0.855], head=(0.975, 0.82, 1.0, 0.87), tail=(0.0, 0.80, 0.015, 0.88)),
    "single": dict(length=168, ratio=0.38, width=0.24, corner=0.25, tumble=0.03, tuck=0.01, bus=True,
                   wheelX=(0.17, 0.77), wheel=0.055, belt=0.50, sill=0.88,
                   outline=[(0.0, 0.88), (0.0, 0.08), (0.02, 0.0), (0.97, 0.0), (1.0, 0.08), (1.0, 0.88)],
                   glass=[[(x, 0.14), (x + 0.088, 0.14), (x + 0.088, 0.50), (x, 0.50)] for x in np.arange(0.03, 0.80, 0.097)] +
                         [[(0.82, 0.12), (0.90, 0.12), (0.90, 0.84), (0.82, 0.84)], [(0.93, 0.10), (0.995, 0.10), (0.995, 0.62), (0.93, 0.62)]],
                   pillars=[], seams=[0.86], head=(0.975, 0.70, 1.0, 0.78), tail=(0.0, 0.66, 0.015, 0.78)),
}
CAR_COLOURS = [(236, 236, 232), (186, 188, 192), (24, 26, 28), (150, 22, 28), (28, 54, 116), (36, 66, 50), (92, 94, 98),
               (206, 206, 200), (104, 26, 36), (60, 92, 132), (54, 58, 66), (170, 150, 120)]

# What each bit is made of, and how much of the sky it reflects looking straight at it
PAINT, GLASS, TRIM, LAMP, TAIL, CHROME, RUBBER, PLATE, WELL, SIGN = range(10)
REFLECT = np.array([0.12, 0.3, 0.04, 0.5, 0.25, 0.55, 0.02, 0.05, 0.0, 0.15], np.float32)

S = 2                   # drawn this many times bigger, then shrunk
DENSITY = 1.5           # points to each of those pixels, along each way
DISTANCE = 1300         # how far you stand from the middle of the road, in pixels at the road's scale


# Rounds the corners of a line of points, keeping its ends
def rounded(points, rounds=3):
    points = [tuple(map(float, pt)) for pt in points]
    for _ in range(rounds):
        out = [points[0]]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            out += [(0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1), (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1)]
        out.append(points[-1])
        points = out
    return points


# How many samples to take along a length of this many pixels
def count(length):
    return max(2, int(length * S * DENSITY) + 2)


##==================================================================
## THE SIDE VIEW
##==================================================================

# The side of the vehicle as a picture R pixels to each of its pixels: which bits are body,
# their colours and what they are made of, and where the top of the body is at each x
class Side:
    R = 4

    def __init__(self, spec, colour, L, Hc):
        R = self.R
        self.nu, self.nv = int(L * R), int(Hc * R)
        size = (self.nu, self.nv)
        u = (np.arange(self.nu, dtype=np.float32)[:, None] + 0.5) / self.nu
        v = (np.arange(self.nv, dtype=np.float32)[None, :] + 0.5) / self.nv

        def maskOf(points):
            board = pygame.Surface(size)
            board.fill((0, 0, 0))
            pygame.draw.polygon(board, (255, 255, 255), [(x * self.nu, y * self.nv) for x, y in points])
            return pygame.surfarray.array_red(board) > 127

        belt, sill = spec["belt"], spec["sill"]
        body = maskOf(rounded(spec["outline"]) + [(0.985, sill), (0.015, sill)])
        glass = np.zeros(size, bool)
        for pane in spec["glass"]:
            glass |= maskOf(pane if spec.get("bus") else rounded(pane, 2))
        glass &= body

        paint = np.array(colour, np.float32)
        rgb = np.broadcast_to(paint, size + (3,)).copy()
        kind = np.full(size, PAINT, np.int8)
        U, V = np.broadcast_arrays(u, v)
        if spec.get("trim"):                                # black plastic along the bottom
            trim = body & (V > spec["trim"])
            rgb[trim] = (30, 30, 32)
            kind[trim] = TRIM
        rgb[glass] = (16, 20, 26)
        kind[glass] = GLASS
        edge = glass & ~(np.roll(glass, R, 0) & np.roll(glass, -R, 0) & np.roll(glass, R, 1) & np.roll(glass, -R, 1))
        rgb[edge] = (14, 14, 16)
        kind[edge] = TRIM
        for px in spec["pillars"]:
            post = glass & (np.abs(U - px) < 1.6 / L)
            rgb[post] = (12, 12, 14)
            kind[post] = TRIM
        for sx in spec["seams"]:                            # the doors' shut lines and handles
            seam = body & ~glass & (np.abs(U - sx) < 0.5 / L) & (V > belt - 0.02) & (V < sill - 0.04)
            rgb[seam] *= 0.45
            if not spec.get("bus"):
                handle = body & (np.abs(U - (sx - 0.07)) < 2.2 / L) & (np.abs(V - (belt + 0.08)) < 0.6 / Hc)
                rgb[handle] = paint * 0.7 + 40
                kind[handle] = CHROME
        for key, look, what in (("head", (200, 204, 210), LAMP), ("tail", (150, 18, 24), TAIL)):
            x0, y0, x1, y1 = spec[key]
            lamp = body & (U >= x0 - 0.002) & (U <= x1 + 0.002) & (V >= y0) & (V <= y1)
            rgb[lamp] = look
            kind[lamp] = what
            if key == "head":                               # a strip of daytime running light
                strip = lamp & (V < y0 + 0.25 * (y1 - y0))
                rgb[strip] = (255, 255, 250)
        self.body, self.rgb, self.kind = body, rgb, kind
        top = np.where(body.any(axis=1), body.argmax(axis=1), self.nv - 1)
        self.vtop = (top + 0.5) / self.nv                   # the top of the body at each column

    def at(self, u, v):
        i = np.clip((u * self.nu).astype(int), 0, self.nu - 1)
        j = np.clip((v * self.nv).astype(int), 0, self.nv - 1)
        return i, j

    def top(self, u):
        return self.vtop[np.clip((u * self.nu).astype(int), 0, self.nu - 1)]


##==================================================================
## THE POINTS
##==================================================================

class Points:
    def __init__(self):
        self.parts = []

    def add(self, x, y, z, nx, ny, nz, rgb, kind, ao=1.0, lit=False):
        n = max(np.size(a) for a in (x, y, z))

        def full(a):
            a = np.asarray(a, np.float32).ravel()
            return np.broadcast_to(a, (n,)).astype(np.float32)

        rgb = np.broadcast_to(np.asarray(rgb, np.float32), (n, 3)).astype(np.float32)
        self.parts.append((full(x), full(y), full(z), full(nx), full(ny), full(nz), rgb,
                           np.broadcast_to(np.asarray(kind, np.int8), (n,)).ravel(), full(ao),
                           np.broadcast_to(np.asarray(lit, bool), (n,)).ravel()))

    def arrays(self):
        return [np.concatenate(column) for column in zip(*self.parts)]


# A box, all six sides of it
def addBox(points, x0, x1, y0, y1, z0, z1, rgb, kind, lit=False):
    xs = np.linspace(x0, x1, count(x1 - x0))
    ys = np.linspace(y0, y1, count(y1 - y0))
    zs = np.linspace(z0, z1, count(z1 - z0))
    for a, b, c, normal in ((xs, ys, z1, (0, 0, 1)), (xs, ys, z0, (0, 0, -1))):
        X, Y = np.meshgrid(a, b)
        points.add(X, Y, c, *normal, rgb, kind, lit=lit)
    for a, b, c, normal in ((xs, zs, y0, (0, -1, 0)), (xs, zs, y1, (0, 1, 0))):
        X, Z = np.meshgrid(a, b)
        points.add(X, c, Z, *normal, rgb, kind, lit=lit)
    for a, b, c, normal in ((ys, zs, x0, (-1, 0, 0)), (ys, zs, x1, (1, 0, 0))):
        Y, Z = np.meshgrid(a, b)
        points.add(np.full(Y.size, c), Y, Z, *normal, rgb, kind, lit=lit)


# The whole vehicle as points, in pixels with the middle of where it stands on the road at 0:
# x forwards, y down, z towards you
def vehiclePoints(spec, colour, L):
    Hc = L * spec["ratio"]
    side = Side(spec, colour, L, Hc)
    belt, sill = spec["belt"], spec["sill"]
    hw = spec["width"] * L / 2
    rc = spec["corner"] * hw
    tumble, tuck = spec["tumble"], spec["tuck"]
    horizon = belt + (sill - belt) * 0.45
    points = Points()

    # how far out the sides are at each height, as a fraction of the most, and how fast that changes
    shoulder = 0.05 if not spec.get("bus") else 0.015
    def taper(v):
        return (1 - tumble * np.clip((belt - v) / belt, 0, 1) - tuck * smoothstep(horizon, sill, v)
                - shoulder * (1 - smoothstep(belt, belt + 0.14, v)) * (v > belt - 0.02))

    def taperSlope(v, dv=0.01):
        return (taper(v + dv) - taper(v - dv)) / (2 * dv) / Hc     # per pixel down

    # the outline seen from above, going round one side: its u, how far out, and which way it faces
    plan = []
    middle = np.linspace(rc / L, 1 - rc / L, count(L - 2 * rc))
    plan.append((middle, np.full_like(middle, hw), np.zeros_like(middle), np.ones_like(middle)))
    phi = np.linspace(0, math.pi / 2, count(rc * math.pi / 2))
    for end in (0, 1):
        dx = rc - rc * np.sin(phi)                          # from that end
        u = dx / L if end == 0 else 1 - dx / L
        plan.append((u, (hw - rc) + rc * np.cos(phi), (-1 if end == 0 else 1) * np.sin(phi), np.cos(phi)))
    pu, pz, pnx, pnz = (np.concatenate(a) for a in zip(*plan))
    rows = np.linspace(0, 1, count(Hc))
    U, V = np.meshgrid(pu, rows, indexing="ij")
    Z, _ = np.meshgrid(pz, rows, indexing="ij")
    NX, _ = np.meshgrid(pnx, rows, indexing="ij")
    NZ, _ = np.meshgrid(pnz, rows, indexing="ij")
    U, V, Z, NX, NZ = U.ravel(), V.ravel(), Z.ravel(), NX.ravel(), NZ.ravel()
    i, j = side.at(np.clip(U, 0.002, 0.998), V)
    keep = side.body[i, j]
    x, y = (U - 0.5) * L, (V - 1) * Hc
    wheelR = spec["wheel"] * L
    for wx in spec["wheelX"]:                               # the wheel arches cut out
        keep &= np.hypot(x - (wx - 0.5) * L, y + wheelR) > wheelR * 1.12
    U, V, Z, NX, NZ, x, y, i, j = (a[keep] for a in (U, V, Z, NX, NZ, x, y, i, j))
    T = taper(V)
    rgb, kind = side.rgb[i, j].copy(), side.kind[i, j].copy()
    ao = 1 - 0.35 * smoothstep(sill - 0.14, sill, V)
    for s in (1, -1):
        ny = -Z * taperSlope(V) * np.abs(NZ)
        points.add(x, y, s * Z * T, NX, ny, s * NZ, rgb, kind, ao)

    # the ends, flat across between their rounded corners
    across = np.linspace(-1, 1, count(2 * (hw - rc)))
    for end in (0, 1):
        u = 0.002 if end == 0 else 0.998
        inset = 0.015 if end == 0 else 0.985
        F, V = np.meshgrid(across, rows, indexing="ij")
        F, V = F.ravel(), V.ravel()
        i, _ = side.at(np.full_like(V, u), V)
        i2, j = side.at(np.full_like(V, inset), V)
        keep = side.body[i, j]
        F, V, i, j = F[keep], V[keep], i2[keep], j[keep]
        z = F * (hw - rc) * taper(V)
        rgb, kind = side.rgb[i, j].copy(), side.kind[i, j].copy()
        lamps = (kind == LAMP) | (kind == TAIL)
        inner = np.abs(z) < 0.45 * hw
        if end == 1:                                        # a grille between the headlamps
            grille = lamps & inner
            rgb[grille] = (34, 34, 38)
            kind[grille] = TRIM
            y0, y1 = spec["head"][3] + 0.03, spec["head"][3] + 0.11
        else:
            rgb[lamps & inner] = side.rgb[0, 0]
            kind[lamps & inner] = PAINT
            y0, y1 = spec["tail"][3] + 0.03, spec["tail"][3] + 0.11
        plate = (np.abs(z) < 0.26 * hw) & (V > y0) & (V < y1) & (V < sill - 0.02)
        rgb[plate] = (238, 236, 228) if end == 1 else (236, 196, 40)    # white at the front, yellow at the back
        kind[plate] = PLATE
        points.add((u - 0.5) * L, (V - 1) * Hc, z, -1 if end == 0 else 1, 0, 0, rgb, kind,
                   1 - 0.35 * smoothstep(sill - 0.14, sill, V))

    # the top: roof, bonnet, boot and the glass between them, curving down a little to the sides
    us = np.linspace(0.004, 0.996, count(L))
    vt = side.top(us)
    k = max(3, int(len(us) / L * 2.5))                     # smoothed over a couple of pixels
    padded = np.concatenate([np.full(k, vt[0]), vt, np.full(k, vt[-1])])
    vt = np.convolve(padded, np.hanning(2 * k + 1) / np.hanning(2 * k + 1).sum(), "same")[k:-k]
    yt = (vt - 1) * Hc
    slope = np.gradient(yt, (us[1] - us[0]) * L)
    dx = np.minimum(us * L, (1 - us) * L)
    half = np.where(dx < rc, (hw - rc) + np.sqrt(np.clip(rc * rc - (rc - dx) ** 2, 0, None)), hw) * taper(vt)
    crown = 0.06 * hw if not spec.get("bus") else 0.02 * hw
    across = np.linspace(-1, 1, count(2 * hw))
    A, Ui = np.meshgrid(across, np.arange(len(us)), indexing="ij")
    A, Ui = A.ravel(), Ui.ravel()
    z = A * half[Ui]
    y = yt[Ui] + crown * A * A
    nx, ny, nz = slope[Ui], -np.ones_like(z), 2 * crown * A / np.maximum(half[Ui], 1)
    i, j = side.at(us[Ui], np.minimum(vt[Ui] + 1.5 / Hc, 1))
    rgb, kind = side.rgb[i, j].copy(), side.kind[i, j].copy()
    xs = [x for pane in spec["glass"] for x, _ in pane]
    roof = vt.min()
    screen = ((us[Ui] > min(xs) - 0.1) & (us[Ui] < max(xs) + 0.1) & (vt[Ui] < belt - 0.015) &
              (vt[Ui] > roof + 0.025) & (np.abs(slope[Ui]) > 0.25))
    steep = screen & (not spec.get("bus"))                 # the windscreen and the back window
    flat = ~steep & (kind == GLASS)
    rgb[steep] = (16, 20, 26)
    kind[steep] = GLASS
    rgb[flat] = side.rgb[0, 0] if spec.get("bus") else colour
    kind[flat] = PAINT
    points.add((us[Ui] - 0.5) * L, y, z, nx, ny, nz, rgb, kind)

    # wing mirrors, and a taxi's sign
    if not spec.get("bus"):
        front = max(x for pane in spec["glass"] for x, _ in pane)
        mx = (front - 0.04 - 0.5) * L
        my = (belt - 1) * Hc
        for s in (1, -1):
            z0, z1 = sorted((s * hw * 0.92, s * (hw + 3.5)))
            addBox(points, mx - 2.5, mx + 1.5, my - 2.6, my + 0.4, z0, z1, np.array(colour, np.float32) * 0.85, PAINT)
    if spec.get("sign"):
        roof = (side.top(np.array([0.42]))[0] - 1) * Hc
        addBox(points, (0.34 - 0.5) * L, (0.46 - 0.5) * L, roof - 4, roof + 0.5, -0.32 * hw, 0.32 * hw, (236, 170, 40), SIGN, lit=True)

    # the wheels: tyres, alloy wheels with spokes on their outsides, and dark wells above them
    tw = 0.24 * hw
    for wx in spec["wheelX"]:
        cx, cy = (wx - 0.5) * L, -wheelR
        theta = np.linspace(0, 2 * math.pi, count(2 * math.pi * wheelR), endpoint=False)
        for s in (1, -1):
            zc = s * (hw * 0.9 - tw / 2)
            Th, Wd = np.meshgrid(theta, np.linspace(-tw / 2, tw / 2, count(tw)), indexing="ij")
            points.add(cx + wheelR * np.cos(Th), cy + wheelR * np.sin(Th), zc + Wd, np.cos(Th), np.sin(Th), 0,
                       (26, 26, 28), RUBBER)
            Th, Rho = np.meshgrid(theta, np.linspace(0, wheelR, count(wheelR)), indexing="ij")
            Th, Rho = Th.ravel(), Rho.ravel()
            spokes = (np.cos(5 * Th) > -0.2) | (Rho < 0.22 * wheelR) | ((Rho > 0.58 * wheelR) & (Rho < 0.66 * wheelR))
            alloy = Rho < 0.66 * wheelR
            rgb = np.where((alloy & spokes)[:, None], np.array((172, 174, 180), np.float32),
                           np.where(alloy[:, None], np.array((34, 34, 36), np.float32), np.array((30, 30, 32), np.float32)))
            rgb = np.where((Rho < 0.1 * wheelR)[:, None], np.array((90, 90, 96), np.float32), rgb)
            kinds = np.where(alloy & spokes, CHROME, RUBBER).astype(np.int8)
            points.add(cx + Rho * np.cos(Th), cy + Rho * np.sin(Th), zc + s * tw / 2, 0, 0, s, rgb, kinds)
            points.add(cx + Rho * np.cos(Th), cy + Rho * np.sin(Th), zc - s * tw / 2, 0, 0, -s, (22, 22, 24), RUBBER)
        arc = np.linspace(math.pi, 2 * math.pi, count(math.pi * wheelR * 1.12))
        Th, Zw = np.meshgrid(arc, np.linspace(-hw * 0.95, hw * 0.95, count(hw * 1.9)), indexing="ij")
        points.add(cx + 1.12 * wheelR * np.cos(Th), cy + 1.12 * wheelR * np.sin(Th), Zw, -np.cos(Th), -np.sin(Th), 0,
                   (8, 8, 9), WELL)
    return points.arrays(), Hc, hw


##==================================================================
## SEEING IT
##==================================================================

# The vehicle seen from (camX, camY): where your eye is, from the middle of where it stands on
# the road. Returns its picture by daylight, how much of the sky each pixel reflects (for
# colouring with the sky's colour), its lights inside (or None), where its middle on the road
# is in the picture, and where its lamps and near wheels are.
def view(model, camX, camY):
    (x, y, z, nx, ny, nz, rgb, kind, ao, lit), Hc, hw, spec, L = model
    D = DISTANCE
    length = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
    nx, ny, nz = nx / length, ny / length, nz / length
    vx, vy, vz = camX - x, camY - y, D - z
    distance = np.sqrt(vx * vx + vy * vy + vz * vz)
    vx, vy, vz = vx / distance, vy / distance, vz / distance
    facing = nx * vx + ny * vy + nz * vz
    front = facing > -0.02
    (x, y, z, nx, ny, nz, vx, vy, vz, facing, rgb, kind, ao, lit) = (
        a[front] for a in (x, y, z, nx, ny, nz, vx, vy, vz, facing, rgb, kind, ao, lit))
    scale = D / (D - z)
    sx = camX + (x - camX) * scale
    sy = camY + (y - camY) * scale

    left, top = math.floor(sx.min()) - 2, math.floor(sy.min()) - 2
    w, h = math.ceil(sx.max()) + 3 - left, math.ceil(sy.max()) + 3 - top
    W2, H2 = w * S, h * S
    ix = ((sx - left) * S).astype(np.int32)
    iy = ((sy - top) * S).astype(np.int32)
    pixel = iy * W2 + ix
    order = np.argsort(D - z, kind="stable")                # the nearest first
    _, first = np.unique(pixel[order], return_index=True)
    chosen = order[first]

    # the light: from the sky above, and the sky (or the road, below the horizon) reflected
    facing = np.clip(facing[chosen], 0, 1)
    nxc, nyc, nzc = nx[chosen], ny[chosen], nz[chosen]
    diffuse = rgb[chosen] * ((0.55 + 0.45 * np.clip(-nyc, 0, 1) + 0.08 * np.clip(nzc, 0, 1)) * ao[chosen])[:, None]
    up = -(2 * facing * nyc - vy[chosen])                   # how far up the reflected ray goes
    sky = (0.06 + 0.2 * smoothstep(-0.35, -0.1, up) + 0.1 * smoothstep(-0.05, 0.02, up)
           + 0.55 * smoothstep(0.03, 0.2, up) + 0.09 * np.clip(up, 0, 1))
    r0 = REFLECT[kind[chosen]]
    fresnel = r0 + (1 - r0) * (1 - facing) ** 4 * (kind[chosen] != RUBBER) * (kind[chosen] != WELL)
    shine = np.clip(fresnel * sky, 0, 1)

    colour = np.zeros((H2 * W2, 3), np.float32)
    gleam = np.zeros(H2 * W2, np.float32)
    cover = np.zeros(H2 * W2, bool)
    glow = np.zeros((H2 * W2, 3), np.float32)
    where = pixel[chosen]
    colour[where] = diffuse
    gleam[where] = shine
    cover[where] = True
    inside = None
    litPoints = lit[chosen] | ((kind[chosen] == GLASS) & bool(spec.get("bus")) & (np.abs(nzc) > 0.5))
    if litPoints.any():
        glow[where[litPoints]] = np.where((kind[chosen][litPoints] == SIGN)[:, None],
                                          np.array((255, 190, 60), np.float32), np.array((255, 226, 170), np.float32))
        inside = glow.reshape(H2, W2, 3)
    colour, gleam, cover = colour.reshape(H2, W2, 3), gleam.reshape(H2, W2), cover.reshape(H2, W2)

    # fill any pixel missed between points from its neighbours
    for _ in range(2):
        for axis in (0, 1):
            a, b = np.roll(cover, 1, axis), np.roll(cover, -1, axis)
            hole = ~cover & a & b
            if hole.any():
                colour[hole] = (np.roll(colour, 1, axis)[hole] + np.roll(colour, -1, axis)[hole]) / 2
                gleam[hole] = (np.roll(gleam, 1, axis)[hole] + np.roll(gleam, -1, axis)[hole]) / 2
                if inside is not None:
                    inside[hole] = (np.roll(inside, 1, axis)[hole] + np.roll(inside, -1, axis)[hole]) / 2
                cover |= hole

    image = pygame.transform.smoothscale(toSurface(colour, cover * 255.0), (w, h))
    shineImage = pygame.transform.smoothscale(toSurface(np.repeat(gleam[..., None] * 255, 3, axis=2)).convert(), (w, h))
    insideImage = pygame.transform.smoothscale(toSurface(inside).convert(), (w, h)) if inside is not None else None

    def project(px, py, pz):
        k = D / (D - pz)
        return camX + (px - camX) * k - left, camY + (py - camY) * k - top

    hx0, hy0, hx1, hy1 = spec["head"]
    tx0, ty0, tx1, ty1 = spec["tail"]
    head = project((hx1 - 0.5) * L, ((hy0 + hy1) / 2 - 1) * Hc, 0.7 * hw)
    tail = project((tx0 - 0.5) * L, ((ty0 + ty1) / 2 - 1) * Hc, 0.7 * hw)
    wheels = [project((wx - 0.5) * L, 0, hw * 0.9)[0] for wx in spec["wheelX"]]
    return dict(image=image, shine=shineImage, inside=insideImage, anchor=(-left, -top), head=head, tail=tail, wheels=wheels)


# A vehicle ready to be seen: its points, made once
def makeModel(spec, colour, length):
    arrays, Hc, hw = vehiclePoints(spec, colour, length)
    return arrays, Hc, hw, spec, length
