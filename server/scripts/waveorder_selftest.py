"""Does waveorder round-trip its OWN phantom through its OWN forward model?

If yes, any failure on my data is my calling convention and I must fix it.
If no, I am holding the whole model wrong.
"""
import numpy as np, torch
from waveorder.models import isotropic_thin_3d as wo

yx_shape, pixel, wavelength, n_media = (256, 256), 0.325, 0.532, 1.334
na_ill, na_det = 0.12, 0.40
z_list = [-1.5, 0.0, 1.5]

absorption, phase = wo.generate_test_phantom(
    yx_shape=yx_shape, yx_pixel_size=pixel, wavelength_illumination=wavelength,
    index_of_refraction_media=n_media, index_of_refraction_sample=1.40, sphere_radius=8.0,
)
print(f"phantom phase: {phase.min():.3f} to {phase.max():.3f} rad")
print(f"phantom absorption: {absorption.min():.3f} to {absorption.max():.3f}")

abs_tf, phase_tf = wo.calculate_transfer_function(
    yx_shape=yx_shape, yx_pixel_size=pixel, z_position_list=z_list,
    wavelength_illumination=wavelength, index_of_refraction_media=n_media,
    numerical_aperture_illumination=na_ill, numerical_aperture_detection=na_det,
)
data = wo.apply_transfer_function(absorption, phase, abs_tf, phase_tf)
print(f"simulated stack: {data.shape}, range {data.min():.3f} to {data.max():.3f}")

for strength in (1e-4, 1e-3, 1e-2):
    _, recovered = wo.reconstruct(
        zyx_data=data, yx_pixel_size=pixel, z_position_list=z_list,
        wavelength_illumination=wavelength, index_of_refraction_media=n_media,
        numerical_aperture_illumination=na_ill, numerical_aperture_detection=na_det,
        regularization_strength=strength,
    )
    t, r = phase.numpy().ravel(), recovered.numpy().ravel()
    corr = np.corrcoef(t, r)[0, 1]
    scale = (t * r).sum() / (r**2).sum()
    print(f"  reg {strength:<8g} corr {corr:6.3f}  best-fit scale {scale:7.3f}  "
          f"range {r.min():.3f} to {r.max():.3f}")
