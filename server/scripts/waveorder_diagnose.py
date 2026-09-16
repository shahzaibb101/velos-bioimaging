"""Two hypotheses for why waveorder scored badly on my data:
   A. regularisation default is too strong  -> sweep it far lower
   B. it is a weak-object linear model      -> test vs phase amplitude
"""
import numpy as np, torch
from waveorder.models import isotropic_thin_3d as wo
from velos import phantom, tie, metrics
from velos.optics import Optics, through_focus_stack

pixel, wl, n = 0.325, 0.532, 1.334
na_i, na_d = 0.12, 0.40
z = [-1.5, 0.0, 1.5]
kw = dict(yx_pixel_size=pixel, z_position_list=z, wavelength_illumination=wl,
          index_of_refraction_media=n, numerical_aperture_illumination=na_i,
          numerical_aperture_detection=na_d)

print("A. REGULARISATION SWEEP on waveorder's own linear phantom")
a, p = wo.generate_test_phantom(yx_shape=(256,256), yx_pixel_size=pixel,
    wavelength_illumination=wl, index_of_refraction_media=n,
    index_of_refraction_sample=1.40, sphere_radius=8.0)
atf, ptf = wo.calculate_transfer_function(yx_shape=(256,256), **kw)
data = wo.apply_transfer_function(a, p, atf, ptf)
for s in (1e-9, 1e-7, 1e-5, 1e-4, 1e-3):
    _, r = wo.reconstruct(zyx_data=data, regularization_strength=s, **kw)
    t, rr = p.numpy().ravel(), r.numpy().ravel()
    print(f"   reg {s:<8g} corr {np.corrcoef(t,rr)[0,1]:6.3f}  scale {(t*rr).sum()/(rr**2).sum():8.3f}")

print("\nB. WEAK vs STRONG OBJECT, my nonlinear forward model, best reg for each")
optics = Optics()
spec = phantom.generate((512,512), optics, seed=7)
for amplitude, tag in ((0.02, "0.02x  (~0.1 rad, weak)"),
                       (0.10, "0.10x  (~0.5 rad)"),
                       (1.00, "1.00x  (~5 rad, real cells)")):
    truth = tie.level(spec.phase * amplitude)
    clean = through_focus_stack(spec.phase * amplitude, optics)
    best = None
    for s in (1e-9, 1e-7, 1e-5, 1e-3):
        _, r = wo.reconstruct(zyx_data=torch.from_numpy(clean).float(),
                              regularization_strength=s, **kw)
        est = tie.level(r.numpy())
        c = metrics.correlation(truth, est)
        if best is None or c > best[0]:
            best = (c, s, (truth*est).sum()/(est**2).sum())
    mine = tie.level(tie.solve(clean, optics, method="uniform"))
    print(f"   {tag:<26} waveorder corr {best[0]:6.3f} (reg {best[1]:g}, scale {best[2]:7.2f})"
          f"   |  velos TIE corr {metrics.correlation(truth, mine):6.3f}")
