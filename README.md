# Camera ISP Pipeline Simulation

This project simulates how a camera turns a scene into a final photo —
starting from raw spectral data, all the way to a finished RGB image.

It takes **multispectral images** (one image per light wavelength) and
processes them the same way a real camera sensor and image pipeline would,
step by step.

## What it does

1. **Load multispectral data** – reads a stack of images, each one
   showing how much light a scene reflects at a specific wavelength.

2. **Apply camera sensor response** – uses real camera spectral response
   (QE) curves to calculate how much red, green, and blue light the
   sensor would actually pick up.

3. **Build a Bayer RAW image** – arranges the R, G, B values into the
   same RGGB pattern used by real camera sensors (where each pixel only
   sees one color).

4. **Demosaicing** – fills in the missing colors to create a full RGB
   image. Two methods are compared:
   - **Bilinear interpolation** – fast and simple, but can blur edges.
   - **Edge-aware interpolation** – slower, but keeps edges sharper and
     reduces color artifacts.

5. **Post-processing** – applies white balance, color correction, and
   gamma correction to make the image look natural, like a real photo.

## Project structure

```
camera-isp-simulation/
├── isp_pipeline.py      # main script - run this
├── requirements.txt      # required Python packages
├── data/
│   ├── balloons_ms/      # multispectral input images go here
│   ├── spectral response curve red.xlsx
│   ├── spectral response curve green.xlsx
│   └── spectral response curve blue.xlsx
└── outputs/               # generated images are saved here
```

## How to run

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Add your multispectral images to `data/balloons_ms/` and the camera
   QE curve files to the `data/` folder.

3. Run the script:
   ```
   python isp_pipeline.py
   ```

4. Check the `outputs/` folder for:
   - `bayer_preview.png` – the simulated raw sensor image
   - `final_bilinear.png` – final image using bilinear demosaicing
   - `final_edge_aware.png` – final image using edge-aware demosaicing

## Data source

Multispectral images: [CAVE Multispectral Image Database](https://cave.cs.columbia.edu/repository/Multispectral)

## Notes

This was built as a university project to understand and compare how
different demosaicing methods affect image quality in a simulated camera
pipeline.
