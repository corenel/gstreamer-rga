# 代码变更日志

本文档记录了 GStreamer 插件仓库 `gstreamer-rga` 的变更历史。

## v0.1.0 (Unreleased)

**Features**

- 功能：引入 `rgavideoconvert` GStreamer 插件，利用 Rockchip RGA 实现硬件加速的视频处理 #1
  - 插件基于 `GstVideoFilter` 基类实现，用于高效的色彩空间转换和图像缩放。
  - 集成 Rockchip `librga` 库，通过 `c_RkRgaBlit` API 执行核心的图形处理任务。
  - 支持在多种常见的视频格式（如 NV12, NV21, I420, YV12, RGB, BGR, RGBA, BGRA 等）之间进行转换。
  - 提供硬件加速的图像缩放功能，支持最大输入分辨率 8192x8192 和最大输出分辨率 4096x4096（受 RGA 硬件规格限制）。
  - 集成 DMABUF 支持，当上下游元素通过 DMA 文件描述符（FD）提供缓冲区时，可实现零拷贝内存操作，显著提升性能。
  - 在插件生命周期的 `start` 和 `stop` 阶段，自动完成 RGA 资源的初始化 (`c_RkRgaInit`) 和反初始化 (`c_RkRgaDeInit`)。
  - 插件注册等级（rank）设置为 `primary (256)`，使其在 GStreamer 自动插件选择时具有较高优先级。
- 功能：为 `rgavideoconvert` 插件添加 `core-mask` 属性，允许用户在运行时动态选择 RGA 硬件核心 #1
  - 用户可通过 `core-mask` GFlags 属性（例如指定 `auto`、`rga3`、`rga2`、`rga3_core0`、`rga3_core1` 等值）来精确控制 RGA 任务分配给哪些物理核心。
  - 该核心选择配置会在 RGA 初始化阶段通过 `imconfig(IM_CONFIG_SCHEDULER_CORE, ...)` 应用，并在每次帧转换操作（`c_RkRgaBlit`）时传递给 `librga`。

**Fixes**

- 修复：识别并提供通过 `core-mask` 属性管理 RGA 核心选择的机制，以解决在特定 Rockchip SoC（如 RK3588）上 RGA2 核心的 32 位 DMA 寻址限制问题 #1
  - 问题背景：部分 Rockchip SoC（如 RK3588）上的 RGA2 单元只能寻址 32 位物理地址空间（即低于 4GiB 的内存）。在拥有较大内存（例如 >= 8GiB）的设备上，若视频缓冲区被分配到高于 4GiB 的物理内存区域，并且 RGA 任务被调度到 RGA2 核心执行，则可能导致内核 `swiotlb` (Software I/O Translation Lookaside Buffer) 耗尽，引发内存映射失败（`Failed to map attachment`）错误，尤其在多路并行处理时严重影响稳定性。
  - 解决方案：插件引入 `core-mask` 属性。用户可通过在 `rgavideoconvert` 元素上设置 `core-mask=rga3`，将 RGA 任务显式调度到支持 40 位物理地址寻址的 RGA3 核心上执行，从而有效规避此硬件限制。此方法已作为最佳实践记录于项目文档中。

**Build & Deployment**

- 构建：更新 `meson.build` 构建系统配置以支持插件编译和依赖管理 #1
  - 添加对 `librga`（Rockchip RGA 用户空间库）的依赖。
  - 添加对 `gstreamer-video-1.0`（GStreamer 视频处理库）的依赖。
  - 添加对 `gstreamer-allocators-1.0`（GStreamer 内存分配器库，用于 DMABUF 支持）的依赖。

**Documentation**

- 文档：新增内容详尽的 `README.md` 项目文档，全面介绍插件信息 #1
  - 清晰阐述插件的主要特性、运行所需的软硬件环境要求。
  - 提供逐步的编译指南和安装说明。
  - 包含快速上手示例 (`gst-launch-1.0` 命令)，演示基本用法。
  - 详细解释 `core-mask` 属性的高级用法，包括不同值的含义及配置示例。
  - 提供多路视频流并行处理的压力测试方法和示例脚本。
  - 总结插件使用的最佳实践，帮助用户优化性能和稳定性。
  - 列出常见问题及其对应的故障排除指南。
- 文档：提供 `README.md` 的简体中文翻译版本 (`README.zh-CN.md`)，方便中文用户阅读和使用 #1
