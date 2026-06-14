"""
Demosaicing Quality Comparison
--------------------------------
Compares the bilinear and edge-aware demosaicing results against a
"ground truth" RGB image derived directly from the multispectral cube
(i.e. without ever going through the Bayer mosaic step).

Metrics used:
- PSNR (Peak Signal-to-Noise Ratio) - higher is better
- SSIM (Structural Similarity Index) - closer to 1 is better

Run this after isp_pipeline.py has generated the Bayer RAW image.
"""

import os
import numpy as np
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from isp_pipeline import (
    MS_IMAGE_FOLDER,
    OUTPUT_FOLDER,
    load_multispectral_cube,
    wavelength_to_index,
    build_bayer_raw,
    demosaic,
    IMAGE_SIZE,
)


def normalize_to_uint8(image: np.ndarray) -> np.ndarray:
    """Scale an image to the full 0-255 range for fair comparison."""
    img = image.astype(np.float32)
    img -= img.min()
    if img.max() > 0:
        img /= img.max()
    return (img * 255).astype(np.uint8)


def build_ground_truth_rgb(ms_image: np.ndarray) -> np.ndarray:
    """Build a reference RGB image directly from the multispectral cube
    by averaging the bands in each color's wavelength range (no Bayer
    sampling, no demosaicing)."""
    R_wavelengths = np.arange(660, 701, 10)
    G_wavelengths = np.arange(500, 651, 10)
    B_wavelengths = np.arange(400, 491, 10)

    R = ms_image[:, :, wavelength_to_index(R_wavelengths)].mean(axis=-1)
    G = ms_image[:, :, wavelength_to_index(G_wavelengths)].mean(axis=-1)
    B = ms_image[:, :, wavelength_to_index(B_wavelengths)].mean(axis=-1)

    rgb = np.stack([R, G, B], axis=-1)
    return normalize_to_uint8(rgb)


def main() -> None:
    ms_image = load_multispectral_cube(MS_IMAGE_FOLDER)

    # Ground truth RGB, built straight from the spectral cube
    ground_truth = build_ground_truth_rgb(ms_image)

    # Re-build the Bayer RAW image the same way isp_pipeline.py does
    R_wavelengths = np.arange(660, 701, 10)
    G_wavelengths = np.arange(500, 651, 10)
    B_wavelengths = np.arange(400, 491, 10)

    I_R = ms_image[:, :, wavelength_to_index(R_wavelengths)].mean(axis=-1)
    I_G = ms_image[:, :, wavelength_to_index(G_wavelengths)].mean(axis=-1)
    I_B = ms_image[:, :, wavelength_to_index(B_wavelengths)].mean(axis=-1)

    bayer_raw = build_bayer_raw(I_R, I_G, I_B, IMAGE_SIZE)

    print(f"{'Method':<15}{'PSNR (dB)':<15}{'SSIM':<10}")
    print("-" * 40)

    results = []
    for method in ["bilinear", "edge_aware"]:
        demosaiced = demosaic(bayer_raw, method=method)
        # cv2 demosaicing returns BGR -> convert to RGB for comparison
        demosaiced_rgb = demosaiced[:, :, ::-1]
        demosaiced_rgb = normalize_to_uint8(demosaiced_rgb)

        psnr = peak_signal_noise_ratio(ground_truth, demosaiced_rgb)
        ssim = structural_similarity(ground_truth, demosaiced_rgb, channel_axis=-1)

        print(f"{method:<15}{psnr:<15.2f}{ssim:<10.4f}")
        results.append((method, psnr, ssim))

    # Save results to a markdown table for the README / report
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    with open(os.path.join(OUTPUT_FOLDER, "metrics.md"), "w") as f:
        f.write("| Method | PSNR (dB) | SSIM |\n")
        f.write("|---|---|---|\n")
        for method, psnr, ssim in results:
            f.write(f"| {method} | {psnr:.2f} | {ssim:.4f} |\n")

    print(f"\nSaved {os.path.join(OUTPUT_FOLDER, 'metrics.md')}")


if __name__ == "__main__":
    main()
