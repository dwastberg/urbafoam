from math import log, sqrt

KAPPA = 0.41  # von Karman constant, as used by OpenFOAM's atmBoundaryLayer inlets and wall functions
CMU = 0.09


def turbulenceConstants(z, z0, Uref):
    """k, epsilon and omega of the Richards & Hoxey inlet profile at height `z`, used as initial values."""
    u_star = Uref * KAPPA / log((z + z0) / z0)
    ke = (u_star ** 2) / sqrt(CMU)
    eps = (u_star ** 3) / (KAPPA * (z + z0))
    omega = eps / (CMU * ke)
    return ke, eps, omega
