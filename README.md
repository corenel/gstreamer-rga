# gstreamer-rga / gst-rga

Hardware‑accelerated 2D colour‑space conversion and scaling for Rockchip SoCs (RK3588/RK356x/…) powered by RGA.

RGA is Rockchip’s on‑chip 2D engine that performs BLIT, resize, rotation and pixel‑format transforms with very low CPU overhead.

> **Status:** experimental but production-tested for 6 x 1080p30 pipelines on RK3588. RGA3 core0 and core1 are 88 % occupied.

## Table of Contents

- [gstreamer-rga / gst-rga](#gstreamer-rga--gst-rga)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Requirements](#requirements)
  - [Building \& Installation](#building--installation)
  - [Quick Start](#quick-start)
  - [Advanced Usage](#advanced-usage)
    - [`core-mask` Property](#core-mask-property)
    - [Multiple streams (stress test)](#multiple-streams-stress-test)
  - [Best Practice](#best-practice)
  - [Troubleshooting](#troubleshooting)
  - [Acknowledgements](#acknowledgements)
  - [License](#license)

## Features

- **Colours‑space conversion** between NV12/NV21/I420/YV12/… and RGB/BGR/BGRA/RGBA.
- **Image resizing** up to 8192x8192 input, 4096x4096 output (RGA H/W limit).
- **Multistream aware** – tested with 6 parallel operations on RK3588.
- **Runtime core selection** ‑ new `core-mask` property lets you pin jobs to RGA3 or RGA2 cores.
- **Zero‑copy DMA‑BUF** support when upstream allocators provide dmabuf FDs.

## Requirements

| component       | minimum version | note                                                      |
| --------------- | --------------- | --------------------------------------------------------- |
| GStreamer       | 1.16            |                                                           |
| librga          | v2.2.0 +        |                                                           |
| Meson ‑ Ninja   | ≥ 1.3.2/1.11.1  | build system                                              |
| Rockchip kernel | ≥ 5.10          | enables IOMMU for RGA3 and provides RGA multi-core driver |

## Building & Installation

```bash
# 1. Clone
$ git clone https://github.com/corenel/gstreamer-rga.git
$ cd gstreamer-rga

# 2. Configure (default = /usr/local)
$ meson setup build
#    or install to HOME so you don’t need root:
$ meson setup --prefix "$HOME/.local" build

# 3. Compile
$ ninja -C build

# 4. Install (drop sudo if installing to HOME)
$ sudo ninja -C build install

# 5. Tell GStreamer where to find the plugin (if installing to HOME)
$ export GST_PLUGIN_PATH_1_0="$HOME/.local/lib/$(uname -m)-linux-gnu/gstreamer-1.0"

# 6. Clear GStreamer cache
$ rm -rf ~/.cache/gstreamer-1.0/*

# 7. Check installation
$ gst-inspect-1.0 rgavideoconvert

Factory Details:
  Rank                     primary (256)
  Long-name                RgaVidConv Plugin
  Klass                    Generic
  Description              Converts video from one colorspace to another & Resizes via Rockchip RGA
  Author                   http://github.com/corenel/gstreamer-rga

Plugin Details:
  Name                     rgavideoconvert
  Description              video Colorspace conversion & scaler
  Filename                 /usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstrgavideoconvert.so
  Version                  0.1.0
  License                  MIT/X11
  Source module            gst-rga
  Binary package           gstreamer-rga
  Origin URL               https://github.com/corenel/gstreamer-rga.git

GObject
 +----GInitiallyUnowned
       +----GstObject
             +----GstElement
                   +----GstBaseTransform
                         +----GstVideoFilter
                               +----GstRgaVideoConvert

Pad Templates:
  SINK template: 'sink'
    Availability: Always
    Capabilities:
      video/x-raw
                 format: { (string)I420, (string)YV12, (string)NV12, (string)NV21, (string)Y42B, (string)NV16, (string)NV61, (string)RGB16, (string)RGB15, (string)BGR, (string)RGB, (string)BGRA, (string)RGBA, (string)BGRx, (string)RGBx }
                  width: [ 1, 8192 ]
                 height: [ 1, 8192 ]
              framerate: [ 0/1, 2147483647/1 ]

  SRC template: 'src'
    Availability: Always
    Capabilities:
      video/x-raw
                 format: { (string)I420, (string)YV12, (string)NV12, (string)NV21, (string)Y42B, (string)NV16, (string)NV61, (string)RGB16, (string)RGB15, (string)BGR, (string)RGB, (string)BGRA, (string)RGBA, (string)BGRx, (string)RGBx }
                  width: [ 1, 4096 ]
                 height: [ 1, 4096 ]
              framerate: [ 0/1, 2147483647/1 ]

Element has no clocking capabilities.
Element has no URI handling capabilities.

Pads:
  SINK: 'sink'
    Pad Template: 'sink'
    Pad Template: 'sink'
  SRC: 'src'
    Pad Template: 'src'

Element Properties:

  core-mask           : Select which RGA core(s) to use (bit-mask)
                        flags: readable, writable
                        Flags "GstRgaCoreMask" Default: 0x00000000, "(none)"
                           (0x00000001): auto             - auto
                           (0x00000001): rga3_core0       - rga3_core0
                           (0x00000002): rga3_core1       - rga3_core1
                           (0x00000004): rga2_core0       - rga2_core0
                           (0x00000003): rga3             - rga3
                           (0x00000004): rga2             - rga2

  name                : The name of the object
                        flags: readable, writable
                        String. Default: "rgavideoconvert0"

  parent              : The parent of the object
                        flags: readable, writable
                        Object of type "GstObject"

  qos                 : Handle Quality-of-Service events
                        flags: readable, writable
                        Boolean. Default: true
```

## Quick Start

```bash
# NV12 1080p -> BGR 640×480 with automatic core scheduling
gst-launch-1.0 videotestsrc ! video/x-raw,width=1920,height=1080,format=NV12 \
  ! rgavideoconvert ! video/x-raw,width=640,height=480,format=BGR ! fakesink

# Pin work to RGA3 only – avoids 32-bit limitation of RGA2
gst-launch-1.0 filesrc location=test.h264 ! h264parse ! mppvideodec \
  ! rgavideoconvert core-mask=rga3 \
  ! video/x-raw,width=1280,height=720,format=BGRx ! fakesink
```

## Advanced Usage

### `core-mask` Property

The property is a **GFlags** bit‑mask.

| string value     | bits                                                 | meaning                     |
| ---------------- | ---------------------------------------------------- | --------------------------- |
| `auto` (default) | 0                                                    | let librga scheduler decide |
| `rga3`           | `IM_SCHEDULER_RGA3_CORE0 \| IM_SCHEDULER_RGA3_CORE1` | dual‑core 64‑bit            |
| `rga2`           | `IM_SCHEDULER_RGA2_CORE0`                            | legacy 32‑bit core          |
| `rga3_core0`     | single core                                          |                             |
| `rga3_core1`     | single core                                          |                             |
| `rga2_core0`     | single core                                          |                             |

Set it per element: `… ! rgavideoconvert core-mask=rga3 ! …`

### Multiple streams (stress test)

```bash
# Prepare test file
gst-launch-1.0 videotestsrc num-buffers=3000 ! video/x-raw,width=1920,height=1080,format=NV12 ! mpph264enc ! h264parse ! filesink location=test.h264

# Run 6 parallel streams (w/ gst-shark for CPU usage monitoring)
GST_DEBUG="GST_TRACER:7" \
GST_TRACERS="cpuusage" \
  gst-launch-1.0 -e filesrc location=test.h264 ! h264parse ! tee name=t \
    $(for i in $(seq 1 6); do echo "t. ! queue ! mppvideodec ! rgavideoconvert core-mask=rga3 \
      ! video/x-raw,width=640,height=480,format=BGR ! queue ! fakesink sync=false "; done)

# Monitor RGA usage (on a separate terminal)
watch -n 0.5 cat /sys/kernel/debug/rkrga/load
```

## Best Practice

1. **Prefer RGA3** on boards with > 4 GB RAM – RGA2 can only DMA below 4 GB.
2. Map upstream buffers with **DMA32/IOMMU** flags when you really need RGA2.
3. Always insert **`queue`** between decoder and `rgavideoconvert` for smooth parallelism.

## Troubleshooting

| symptom                                               | cause                                | remedy                                                |
| ----------------------------------------------------- | ------------------------------------ | ----------------------------------------------------- |
| `swiotlb buffer is full` + `Failed to map attachment` | buffers above 4 GB scheduled on RGA2 | set `core-mask=rga3` **or** force DMA32 allocations   |
| `not negotiated` errors                               | caps mismatch                        | verify width/height within limits (in≤8192, out≤4096) |
| `No such element rgavideoconvert`                     | plugin not found                     | ensure `GST_PLUGIN_PATH_1_0` includes install dir     |

## Acknowledgements

- [airockchip/librga](https://github.com/airockchip/librga) – original RGA library
- [higithubhi/gstreamer-rgaconvert](https://github.com/higithubhi/gstreamer-rgaconvert) – original GStreamer plugin

## License

MIT – see [LICENSE](LICENSE).
