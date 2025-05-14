# gstreamer-rga / gst-rga

`gstreamer-rga` 是基于 Rockchip **RGA** 硬件的 GStreamer 插件，为瑞芯微 SoC (RK3588/RK356x/…) 提供硬件加速的 2D 色彩空间转换和缩放功能。

RGA 是瑞芯微的 2D 加速引擎，可执行 BLIT、调整大小、旋转和像素格式转换等操作。

> **状态：** 项目状态：实验性，但已在 RK3588 上测试，处理 6 路 1080p30 视频时，RGA3 core0/1 占用率均约 88 %。

## 目录

- [gstreamer-rga / gst-rga](#gstreamer-rga--gst-rga)
  - [目录](#目录)
  - [特性](#特性)
  - [环境要求](#环境要求)
  - [编译与安装](#编译与安装)
  - [快速体验](#快速体验)
  - [高级用法](#高级用法)
    - [core-mask 属性](#core-mask-属性)
    - [多路流压力测试](#多路流压力测试)
  - [最佳实践](#最佳实践)
  - [故障排除](#故障排除)
  - [鸣谢](#鸣谢)
  - [许可证](#许可证)

## 特性

- **色彩空间转换**：在 NV12/NV21/I420/YV12 等 YUV 与 RGB/BGR/BGRA/RGBA 等格式之间互转。
- **图像缩放**：输入分辨率最高 8192x8192，输出最高 4096×4096（RGA 硬件限制）。
- **多流并行**：在 RK3588 上通过 6 路 1080p30 解码 + 转换实测。
- **运行时核心选择**：`core-mask` 属性可绑定到 RGA3 / RGA2 指定核心。
- **零拷贝 DMA‑BUF**：若上游分配器提供 dmabuf FD，可直接映射避免 memcpy。

## 环境要求

| 组件          | 最低版本         | 说明                                |
| ------------- | ---------------- | ----------------------------------- |
| GStreamer     | 1.16             | 建议 1.18 及以上                    |
| librga        | ≥ v2.2.0         | 提供多核心调度与新版掩码            |
| Meson / Ninja | ≥ 1.3.2 / 1.11.1 | 构建系统                            |
| Rockchip 内核 | ≥ 5.10           | 启用 RGA3 IOMMU，含 `multi_rga`驱动 |

## 编译与安装

```bash
# 克隆源码
$ git clone https://github.com/corenel/gstreamer-rga.git && cd gstreamer-rga

# 配置（默认安装到 /usr/local）
$ meson setup build
# 或者无 root 安装到用户目录：
$ meson setup --prefix "$HOME/.local" build

# 编译
$ ninja -C build

# 安装（若安装到用户目录可省略 sudo）
$ sudo ninja -C build install

# 设置插件搜索路径（仅用户目录安装需要）
$ export GST_PLUGIN_PATH_1_0="$HOME/.local/lib/$(uname -m)-linux-gnu/gstreamer-1.0"

# 清理 GStreamer 缓存并验证
$ rm -rf ~/.cache/gstreamer-1.0/*
$ gst-inspect-1.0 rgavideoconvert | grep "RgaVidConv"

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

## 快速体验

```bash
# NV12 1080p → 640×480 BGR（自动调度核心）
gst-launch-1.0 videotestsrc ! \
  video/x-raw,width=1920,height=1080,format=NV12 ! \
  rgavideoconvert ! \
  video/x-raw,width=640,height=480,format=BGR ! fakesink

# 仅使用 RGA3，避开 RGA2 32 位限制
gst-launch-1.0 filesrc location=test.h264 ! h264parse ! mppvideodec \
  ! rgavideoconvert core-mask=rga3 \
  ! video/x-raw,width=1280,height=720,format=BGRx ! fakesink
```

## 高级用法

### core-mask 属性

| 字符串值      | 掩码位                     | 说明                 |
| ------------- | -------------------------- | -------------------- |
| `auto` (默认) | 0                          | 交由 librga 自行调度 |
| `rga3`        | RGA3\_CORE0 \| RGA3\_CORE1 | 64 位双核            |
| `rga2`        | RGA2\_CORE0                | 32 位核心            |
| `rga3_core0`  | 单核                       |                      |
| `rga3_core1`  | 单核                       |                      |
| `rga2_core0`  | 单核                       |                      |

使用示例：`… ! rgavideoconvert core-mask=rga3 ! …`

### 多路流压力测试

```bash
# 生成测试文件（1080p NV12 → H.264）
gst-launch-1.0 videotestsrc num-buffers=3000 ! \
  video/x-raw,width=1920,height=1080,format=NV12 ! \
  mpph264enc ! h264parse ! filesink location=test.h264

# 运行 6 路并行
GST_DEBUG="GST_TRACER:7" \
GST_TRACERS="cpuusage" \
  gst-launch-1.0 -e filesrc location=test.h264 ! h264parse ! tee name=t \
    $(for i in $(seq 1 6); do echo "t. ! queue ! mppvideodec ! rgavideoconvert core-mask=rga3 \
      ! video/x-raw,width=640,height=480,format=BGR ! queue ! fakesink sync=false "; done)

# 监控 RGA 负载（另一个终端）
watch -n 0.5 cat /sys/kernel/debug/rkrga/load
```

## 最佳实践

1. **大于 4 GB 内存的板卡优先使用 RGA3**，RGA2 仅能访问 32‑bit 物理地址。
2. 如需使用 RGA2，请确保上游缓冲区带有 **DMA32/IOMMU** 标志或限制内核低地址分配。
3. 在解码器与 `rgavideoconvert` 之间插入 **`queue`**，提升并行度与平滑度。

## 故障排除

| 现象                                                  | 原因                    | 解决方案                                |
| ----------------------------------------------------- | ----------------------- | --------------------------------------- |
| `swiotlb buffer is full` / `Failed to map attachment` | 高位地址缓冲调度到 RGA2 | 设置 `core-mask=rga3` 或强制 DMA32 分配 |
| `not negotiated`                                      | caps 不匹配             | 检查分辨率（输入≤8192，输出≤4096）      |
| `No such element rgavideoconvert`                     | 插件未被搜索到          | 确认 `GST_PLUGIN_PATH_1_0` 指向安装目录 |

## 鸣谢

- [airockchip/librga](https://github.com/airockchip/librga) – RGA 官方库。
- [higithubhi/gstreamer-rgaconvert](https://github.com/higithubhi/gstreamer-rgaconvert) – 最初的 GStreamer RGA 插件。

## 许可证

MIT – 详见 [LICENSE](LICENSE)。
