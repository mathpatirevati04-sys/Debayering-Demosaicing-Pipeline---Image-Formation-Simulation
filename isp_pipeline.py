"""
Camera ISP (Image Signal Processing) Pipeline Simulation
---------------------------------------------------------
This script simulates how a real camera with a Bayer sensor would turn
a multispectral reflectance image into a final RGB photo.

Pipeline steps:
1. Load a multispectral image cube (one image per wavelength band).
2. Use camera sensor spectral response (QE) curves to get R, G, B
   intensity images.
3. Arrange the R, G, B values into a Bayer RAW image (RGGB pattern),
   just like a real camera sensor.
4. Demosaic the RAW image to get a full RGB image (two methods:
   bilinear and edge-aware).
5. Apply white balance, color correction (CCM) and gamma correction.
6. Save the final images so the two demosaicing methods can be compared.
"""

import os

import cv2
import numpy as np
import pandas as pd
import imageio

# ----------------------------- CONFIG ----------------------------- #
# Change these paths if your data is stored somewhere else
MS_IMAGE_FOLDER = "data/balloons_ms"   # folder with the multispectral band images
QE_FOLDER = "data"                     # folder with the camera QE curve excel files
OUTPUT_FOLDER = "outputs"

QE_FILE_R = "spectral response curve red.xlsx"
QE_FILE_G = "spectral response curve green.xlsx"
QE_FILE_B = "spectral response curve blue.xlsx"

IMAGE_SIZE = 512   # size of the output image (assumes square images)
GAMMA = 2.2        # gamma value used for the final gamma correction

# Color correction matrix (CCM) - converts sensor colors to more natural colors
CCM = np.array([
    [1.6, -0.3, -0.3],
    [-0.2, 1.4, -0.2],
    [-0.1, -0.3, 1.4]
], dtype=np.float32)
# --------------------------------------------------------------------- #


def wavelength_to_index(wavelength: np.ndarray) -> np.ndarray:
    """Convert a wavelength (nm) to the band index of the loaded cube.
    Assumes the cube starts at 400nm with 10nm steps between bands."""
    return ((wavelength - 400) / 10).astype(np.int64)


def load_multispectral_cube(folder_path: str) -> np.ndarray:
    """Load all band images from a folder and stack them into a
    Height x Width x Bands cube."""
    files = sorted(os.listdir(folder_path))
    files = [f for f in files if f.lower().endswith(('.png', '.bmp', '.tif', '.jpg'))]

    if not files:
        raise FileNotFoundError(f"No image files found in '{folder_path}'")

    bands = []
    for f in files:
        img = cv2.imread(os.path.join(folder_path, f), cv2.IMREAD_UNCHANGED)
        img = img.astype(np.float32) / 255.0  # normalize 8-bit images to 0-1
        bands.append(img)

    return np.stack(bands, axis=-1)


def load_qe_curve(file_path: str, target_wavelengths: np.ndarray) -> np.ndarray:
    """Load a camera spectral response (QE) curve from Excel and
    interpolate it to the wavelengths we need."""
    df = pd.read_excel(file_path)
    wavelengths = df['Wavelength'].to_numpy()
    qe_values = df['Qe'].to_numpy()
    return np.interp(target_wavelengths, wavelengths, qe_values)


def compute_channel_intensity(
    ms_image: np.ndarray, wavelengths: np.ndarray, qe_curve: np.ndarray
) -> np.ndarray:
    """Compute the simulated sensor intensity for one color channel by
    combining the scene reflectance with the sensor's spectral response."""
    indices = wavelength_to_index(wavelengths)
    band_subset = ms_image[:, :, indices]
    intensity = np.sum(band_subset * qe_curve[None, None, :], axis=-1) * 10e-9
    return intensity


def build_bayer_raw(
    I_R: np.ndarray, I_G: np.ndarray, I_B: np.ndarray, size: int
) -> np.ndarray:
    """Arrange R, G, B intensity images into a single RGGB Bayer RAW image,
    the same way a real camera sensor only sees one color per pixel."""
    bayer = np.zeros((size, size), dtype=np.float32)
    bayer[0::2, 0::2] = I_R[0::2, 0::2]   # R
    bayer[0::2, 1::2] = I_G[0::2, 1::2]   # G
    bayer[1::2, 0::2] = I_G[1::2, 0::2]   # G
    bayer[1::2, 1::2] = I_B[1::2, 1::2]   # B

    bayer_norm = np.clip(bayer / bayer.max() * 65535, 0, 65535).astype(np.uint16)
    return bayer_norm


def demosaic(bayer_raw: np.ndarray, method: str = "bilinear") -> np.ndarray:
    """Reconstruct a full RGB image from the Bayer RAW image.
    method: 'bilinear' (fast, simple) or 'edge_aware' (sharper, slower)."""
    if method == "bilinear":
        return cv2.cvtColor(bayer_raw, cv2.COLOR_BAYER_RG2BGR).astype(np.float32)
    elif method == "edge_aware":
        return cv2.cvtColor(bayer_raw, cv2.COLOR_BAYER_RG2BGR_EA).astype(np.float32)
    else:
        raise ValueError("method must be 'bilinear' or 'edge_aware'")


def white_balance(image: np.ndarray) -> np.ndarray:
    """Simple gray-world white balance: makes the average R, G and B
    roughly equal, so the image doesn't look too red/blue overall."""
    mean_b = np.mean(image[:, :, 0])
    mean_g = np.mean(image[:, :, 1])
    mean_r = np.mean(image[:, :, 2])

    balanced = image.copy()
    balanced[:, :, 2] *= mean_g / mean_r
    balanced[:, :, 0] *= mean_g / mean_b
    return balanced


def apply_ccm(image: np.ndarray, ccm: np.ndarray) -> np.ndarray:
    """Apply the color correction matrix to every pixel."""
    h, w, _ = image.shape
    out = image.reshape(-1, 3) @ ccm.T
    return out.reshape(h, w, 3)


def gamma_correct(image: np.ndarray, gamma: float) -> np.ndarray:
    """Apply gamma correction and convert the image to 8-bit for saving."""
    img = np.clip(image, 0, None)
    img = img / np.max(img)
    img = np.power(img, 1 / gamma)
    return (img * 255).astype(np.uint8)


def process_to_final_image(
    demosaiced: np.ndarray, ccm: np.ndarray, gamma: float
) -> np.ndarray:
    """Run white balance, color correction and gamma correction in order."""
    balanced = white_balance(demosaiced)
    corrected = apply_ccm(balanced, ccm)
    return gamma_correct(corrected, gamma)


def main() -> None:
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # 1. Load the multispectral image cube
    ms_image = load_multispectral_cube(MS_IMAGE_FOLDER)
    print(f"Loaded multispectral cube with shape {ms_image.shape}")

    # 2. Wavelength ranges used for each color channel
    R_wavelengths = np.arange(660, 701, 10)
    G_wavelengths = np.arange(500, 651, 10)
    B_wavelengths = np.arange(400, 491, 10)

    # 3. Load the camera's spectral response (QE) curves
    QE_R = load_qe_curve(os.path.join(QE_FOLDER, QE_FILE_R), R_wavelengths)
    QE_G = load_qe_curve(os.path.join(QE_FOLDER, QE_FILE_G), G_wavelengths)
    QE_B = load_qe_curve(os.path.join(QE_FOLDER, QE_FILE_B), B_wavelengths)

    # 4. Compute the simulated pixel intensity for each channel
    I_R = compute_channel_intensity(ms_image, R_wavelengths, QE_R)
    I_G = compute_channel_intensity(ms_image, G_wavelengths, QE_G)
    I_B = compute_channel_intensity(ms_image, B_wavelengths, QE_B)

    # 5. Build the Bayer RAW image
    bayer_raw = build_bayer_raw(I_R, I_G, I_B, IMAGE_SIZE)
    imageio.imwrite(os.path.join(OUTPUT_FOLDER, "bayer_preview.png"), bayer_raw)
    print("Saved bayer_preview.png")

    # 6. Demosaic with both methods, post-process, and save results
    for method in ["bilinear", "edge_aware"]:
        demosaiced = demosaic(bayer_raw, method=method)
        final = process_to_final_image(demosaiced, CCM, GAMMA)
        out_path = os.path.join(OUTPUT_FOLDER, f"final_{method}.png")
        imageio.imwrite(out_path, final)
        print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
