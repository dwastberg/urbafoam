from math import log, sqrt

def turbulenceConstants(z, z0, Uref):
    k = 0.42
    Cmu = 0.09
    sigma_k = 1.0
    sigma_e = 1.3
    u_star = Uref * k / log((z + z0) / z0)
    ke = (u_star ** 2) / sqrt(Cmu)
    eps = (u_star ** 3) / (k * (z + z0))
    omega = eps / (Cmu * k)
    return ke, eps, omega