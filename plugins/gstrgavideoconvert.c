/* GStreamer
 * Copyright (C) 2025 FIXME <fixme@example.com>
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 51 Franklin Street, Suite 500,
 * Boston, MA 02110-1335, USA.
 */
/**
 * SECTION:element-gstrgavideoconvert
 *
 * The rgavideoconvert element does FIXME stuff.
 *
 * <refsect2>
 * <title>Example launch line</title>
 * |[
 * gst-launch-1.0 -v fakesrc ! video/x-raw,format=NV12,width=1920,height=1080 !
 * rgavideoconvert ! video/x-raw,format=RGBA,width=640,height=480 ! fakesink
 * ]|
 * convert 1920x1080 ---> 640x480 and NV12 ---> RGBA .
 * </refsect2>
 */

#include "gst/gstpluginfeature.h"
#ifdef HAVE_CONFIG_H
#include "config.h"  // NOLINT
#endif

#include <gst/allocators/gstdmabuf.h>
#include <gst/gst.h>
#include <gst/video/gstvideofilter.h>
#include <gst/video/video.h>

#include "gstrgavideoconvert.h"  // NOLINT
#include "rga/RgaApi.h"
#include "rga/im2d.h"

GST_DEBUG_CATEGORY_STATIC(gst_rga_video_convert_debug_category);
#define GST_CAT_DEFAULT gst_rga_video_convert_debug_category

#define GST_CASE_RETURN(a, b) \
  case a:                     \
    return b

/* prototypes */

static gboolean gst_rga_video_convert_start(GstBaseTransform *trans);
static gboolean gst_rga_video_convert_stop(GstBaseTransform *trans);

static GstCaps *gst_rga_video_convert_transform_caps(GstBaseTransform *trans,
                                                     GstPadDirection direction,
                                                     GstCaps *caps,
                                                     GstCaps *filter);

static gboolean gst_rga_video_convert_set_info(GstVideoFilter *filter,
                                               GstCaps *incaps,
                                               GstVideoInfo *in_info,
                                               GstCaps *outcaps,
                                               GstVideoInfo *out_info);

static GstFlowReturn gst_rga_video_convert_transform_frame(
    GstVideoFilter *filter, GstVideoFrame *inframe, GstVideoFrame *outframe);

/* pad templates */

#define VIDEO_SRC_CAPS                                                         \
  "video/x-raw, "                                                              \
  "format = (string) "                                                         \
  "{ I420, YV12, NV12, NV21, Y42B, NV16, NV61, RGB16, RGB15, BGR, RGB, BGRA, " \
  "RGBA, BGRx, RGBx }"                                                         \
  ", "                                                                         \
  "width = (int) [ 1, 4096 ] ,"                                                \
  "height = (int) [ 1, 4096 ] ,"                                               \
  "framerate = (fraction) [ 0, max ]"

#define VIDEO_SINK_CAPS                                                        \
  "video/x-raw, "                                                              \
  "format = (string) "                                                         \
  "{ I420, YV12, NV12, NV21, Y42B, NV16, NV61, RGB16, RGB15, BGR, RGB, BGRA, " \
  "RGBA, BGRx, RGBx }"                                                         \
  ", "                                                                         \
  "width = (int) [ 1, 8192 ] ,"                                                \
  "height = (int) [ 1, 8192 ] ,"                                               \
  "framerate = (fraction) [ 0, max ]"

/* element properties */

typedef enum {
  GST_RGA_PROP_0,
  GST_RGA_PROP_CORE_MASK,
  GST_RGA_PROP_LAST
} GstRgaProp;

static GParamSpec *rga_props[GST_RGA_PROP_LAST];

/* class initialization */

G_DEFINE_TYPE_WITH_CODE(
    GstRgaVideoConvert, gst_rga_video_convert, GST_TYPE_VIDEO_FILTER,
    GST_DEBUG_CATEGORY_INIT(gst_rga_video_convert_debug_category,
                            "rgavideoconvert", 0,
                            "video Colorspace conversion & scaler"));

static void gst_rga_video_convert_set_property(GObject *object, guint prop_id,
                                               const GValue *value,
                                               GParamSpec *pspec);

static void gst_rga_video_convert_get_property(GObject *object, guint prop_id,
                                               GValue *value,
                                               GParamSpec *pspec);

static void gst_rga_video_convert_class_init(GstRgaVideoConvertClass *klass) {
  GObjectClass *gobject_class = G_OBJECT_CLASS(klass);
  GstBaseTransformClass *base_transform_class = GST_BASE_TRANSFORM_CLASS(klass);
  GstVideoFilterClass *video_filter_class = GST_VIDEO_FILTER_CLASS(klass);

  /* Setting up pads and setting metadata should be moved to
   base_class_init if you intend to subclass this class. */
  gst_element_class_add_pad_template(
      GST_ELEMENT_CLASS(klass),
      gst_pad_template_new("src", GST_PAD_SRC, GST_PAD_ALWAYS,
                           gst_caps_from_string(VIDEO_SRC_CAPS)));
  gst_element_class_add_pad_template(
      GST_ELEMENT_CLASS(klass),
      gst_pad_template_new("sink", GST_PAD_SINK, GST_PAD_ALWAYS,
                           gst_caps_from_string(VIDEO_SINK_CAPS)));

  gst_element_class_set_static_metadata(
      GST_ELEMENT_CLASS(klass), "RgaVidConv Plugin", "Generic",
      "Converts video from one colorspace to another & Resizes via Rockchip "
      "RGA",
      "http://github.com/corenel/gstreamer-rga");

  /* element properties */
  static const GFlagsValue mask_values[] = {
      {IM_SCHEDULER_RGA3_DEFAULT, "auto", "auto"},
      {IM_SCHEDULER_RGA3_CORE0, "rga3_core0", "rga3_core0"},
      {IM_SCHEDULER_RGA3_CORE1, "rga3_core1", "rga3_core1"},
      {IM_SCHEDULER_RGA2_CORE0, "rga2_core0", "rga2_core0"},
      {IM_SCHEDULER_RGA3_CORE0 | IM_SCHEDULER_RGA3_CORE1, "rga3", "rga3"},
      {IM_SCHEDULER_RGA2_CORE0, "rga2", "rga2"},
      {0, NULL, NULL}};
  GType mask_type = g_flags_register_static("GstRgaCoreMask", mask_values);

  rga_props[GST_RGA_PROP_CORE_MASK] = g_param_spec_flags(
      "core-mask", "Core mask", "Select which RGA core(s) to use (bit-mask)",
      mask_type, IM_SCHEDULER_RGA3_DEFAULT, /* default == auto */
      G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS);

  gobject_class->set_property = gst_rga_video_convert_set_property;
  gobject_class->get_property = gst_rga_video_convert_get_property;
  g_object_class_install_property(gobject_class, GST_RGA_PROP_CORE_MASK,
                                  rga_props[GST_RGA_PROP_CORE_MASK]);

  base_transform_class->passthrough_on_same_caps = TRUE;

  base_transform_class->transform_caps =
      GST_DEBUG_FUNCPTR(gst_rga_video_convert_transform_caps);

  base_transform_class->start = GST_DEBUG_FUNCPTR(gst_rga_video_convert_start);
  base_transform_class->stop = GST_DEBUG_FUNCPTR(gst_rga_video_convert_stop);
  video_filter_class->set_info =
      GST_DEBUG_FUNCPTR(gst_rga_video_convert_set_info);
  video_filter_class->transform_frame =
      GST_DEBUG_FUNCPTR(gst_rga_video_convert_transform_frame);
}

static RgaSURF_FORMAT gst_gst_format_to_rga_format(GstVideoFormat format) {
  switch (format) {
    GST_CASE_RETURN(GST_VIDEO_FORMAT_I420, RK_FORMAT_YCbCr_420_P);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_YV12, RK_FORMAT_YCrCb_420_P);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_NV12, RK_FORMAT_YCbCr_420_SP);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_NV21, RK_FORMAT_YCrCb_420_SP);
#ifdef HAVE_NV12_10LE40
    GST_CASE_RETURN(GST_VIDEO_FORMAT_NV12_10LE40, RK_FORMAT_YCbCr_420_SP_10B);
#endif
    GST_CASE_RETURN(GST_VIDEO_FORMAT_Y42B, RK_FORMAT_YCbCr_422_P);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_NV16, RK_FORMAT_YCbCr_422_SP);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_NV61, RK_FORMAT_YCrCb_422_SP);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_RGB16, RK_FORMAT_RGB_565);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_RGB15, RK_FORMAT_RGBA_5551);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_BGR, RK_FORMAT_BGR_888);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_RGB, RK_FORMAT_RGB_888);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_BGRA, RK_FORMAT_BGRA_8888);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_RGBA, RK_FORMAT_RGBA_8888);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_BGRx, RK_FORMAT_BGRX_8888);
    GST_CASE_RETURN(GST_VIDEO_FORMAT_RGBx, RK_FORMAT_RGBX_8888);
    default:
      return RK_FORMAT_UNKNOWN;
  }
}

static gboolean gst_set_rga_info(rga_info_t *info, RgaSURF_FORMAT format,
                                 guint width, guint height, guint hstride,
                                 guint vstride) {
  gint pixel_stride;

  switch (format) {
    case RK_FORMAT_RGBX_8888:
    case RK_FORMAT_BGRX_8888:
    case RK_FORMAT_RGBA_8888:
    case RK_FORMAT_BGRA_8888:
      pixel_stride = 4;
      break;
    case RK_FORMAT_RGB_888:
    case RK_FORMAT_BGR_888:
      pixel_stride = 3;
      break;
    case RK_FORMAT_RGBA_5551:
    case RK_FORMAT_RGB_565:
      pixel_stride = 2;
      break;
    case RK_FORMAT_YCbCr_420_SP_10B:
    case RK_FORMAT_YCbCr_422_SP:
    case RK_FORMAT_YCrCb_422_SP:
    case RK_FORMAT_YCbCr_422_P:
    case RK_FORMAT_YCrCb_422_P:
    case RK_FORMAT_YCbCr_420_SP:
    case RK_FORMAT_YCrCb_420_SP:
    case RK_FORMAT_YCbCr_420_P:
    case RK_FORMAT_YCrCb_420_P:
      pixel_stride = 1;

      /* RGA requires yuv image rect align to 2 */
      width &= ~1;
      height &= ~1;
      break;
    default:
      return FALSE;
  }

  if (info->fd < 0 && !info->virAddr) return FALSE;

  if (hstride / pixel_stride >= width) hstride /= pixel_stride;

  info->mmuFlag = 1;
  rga_set_rect(&info->rect, 0, 0, width, height, hstride, vstride, format);
  return TRUE;
}

static gboolean gst_rga_info_from_video_frame(rga_info_t *info,
                                              GstVideoFrame *frame,
                                              GstMapInfo *mapInfo,
                                              GstMapFlags mapFlag) {
  RgaSURF_FORMAT rga_format =
      gst_gst_format_to_rga_format(GST_VIDEO_FRAME_FORMAT(frame));

  guint width = GST_VIDEO_FRAME_WIDTH(frame);
  guint height = GST_VIDEO_FRAME_HEIGHT(frame);
  guint hstride = GST_VIDEO_FRAME_PLANE_STRIDE(frame, 0);
  guint vstride = GST_VIDEO_FRAME_N_PLANES(frame) == 1
                      ? GST_VIDEO_INFO_HEIGHT(&frame->info)
                      : GST_VIDEO_INFO_PLANE_OFFSET(&frame->info, 1) / hstride;

  if (!gst_set_rga_info(info, rga_format, width, height, hstride, vstride)) {
    return FALSE;
  }
  GstBuffer *inbuf = frame->buffer;
  if (gst_buffer_n_memory(inbuf) == 1) {
    GstMemory *mem = gst_buffer_peek_memory(inbuf, 0);
    gsize offset;

    if (gst_is_dmabuf_memory(mem)) {
      gst_memory_get_sizes(mem, &offset, NULL);
      if (!offset) info->fd = gst_dmabuf_memory_get_fd(mem);
    }
  }

  if (info->fd <= 0) {
    gst_buffer_map(inbuf, mapInfo, mapFlag);
    info->virAddr = mapInfo->data;
  }
  return TRUE;
}

static GstCaps *gst_rga_video_convert_transform_caps(GstBaseTransform *trans,
                                                     GstPadDirection direction,
                                                     GstCaps *caps,
                                                     GstCaps *filter) {
  GST_DEBUG_OBJECT(trans,
                   "transform direction %s : caps=%" GST_PTR_FORMAT
                   "    filter=%" GST_PTR_FORMAT,
                   direction == GST_PAD_SINK ? "sink" : "src", caps, filter);

  GstCaps *ret;
  GstStructure *structure;
  GstCapsFeatures *features;
  gint i, n;

  ret = gst_caps_new_empty();
  n = gst_caps_get_size(caps);
  for (i = 0; i < n; i++) {
    structure = gst_caps_get_structure(caps, i);
    features = gst_caps_get_features(caps, i);

    /* If this is already expressed by the existing caps
     * skip this structure */
    if (i > 0 && gst_caps_is_subset_structure_full(ret, structure, features))
      continue;

    /* make copy */
    structure = gst_structure_copy(structure);

    if (direction == GST_PAD_SRC) {
      // rga 输出最大 4096
      gst_structure_set(structure, "width", GST_TYPE_INT_RANGE, 1, 4096,
                        "height", GST_TYPE_INT_RANGE, 1, 4096, NULL);
    } else {
      // 输入最大 8192
      gst_structure_set(structure, "width", GST_TYPE_INT_RANGE, 1, 8192,
                        "height", GST_TYPE_INT_RANGE, 1, 8192, NULL);
    }
    if (!gst_caps_features_is_any(features)) {
      gst_structure_remove_fields(structure, "format", "colorimetry",
                                  "chroma-site", NULL);
    }

    gst_caps_append_structure_full(ret, structure,
                                   gst_caps_features_copy(features));
  }

  if (filter) {
    GstCaps *intersection;

    intersection =
        gst_caps_intersect_full(filter, ret, GST_CAPS_INTERSECT_FIRST);
    gst_caps_unref(ret);
    ret = intersection;
  }

  GST_DEBUG_OBJECT(trans, "returning caps: %" GST_PTR_FORMAT, ret);

  return ret;
}

static void gst_rga_video_convert_set_property(GObject *object, guint prop_id,
                                               const GValue *value,
                                               GParamSpec *pspec) {
  GstRgaVideoConvert *rgavideoconvert = gst_rga_video_convert(object);
  switch (prop_id) {
    case GST_RGA_PROP_CORE_MASK:
      rgavideoconvert->core_mask = g_value_get_flags(value);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
  }
}

static void gst_rga_video_convert_get_property(GObject *object, guint prop_id,
                                               GValue *value,
                                               GParamSpec *pspec) {
  GstRgaVideoConvert *rgavideoconvert = gst_rga_video_convert(object);
  switch (prop_id) {
    case GST_RGA_PROP_CORE_MASK:
      g_value_set_flags(value, rgavideoconvert->core_mask);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
  }
}

static void gst_rga_video_convert_init(GstRgaVideoConvert *rgavideoconvert) {}

static gboolean gst_rga_video_convert_start(GstBaseTransform *trans) {
  GstRgaVideoConvert *rgavideoconvert = gst_rga_video_convert(trans);

  GST_DEBUG_OBJECT(rgavideoconvert, "start");
  c_RkRgaInit();
  if (rgavideoconvert->core_mask) {
    imconfig(IM_CONFIG_SCHEDULER_CORE, rgavideoconvert->core_mask);
  }
  return TRUE;
}

static gboolean gst_rga_video_convert_stop(GstBaseTransform *trans) {
  GstRgaVideoConvert *rgavideoconvert = gst_rga_video_convert(trans);

  GST_DEBUG_OBJECT(rgavideoconvert, "stop");
  c_RkRgaDeInit();
  return TRUE;
}

static gboolean gst_rga_video_convert_set_info(GstVideoFilter *filter,
                                               GstCaps *incaps,
                                               GstVideoInfo *in_info,
                                               GstCaps *outcaps,
                                               GstVideoInfo *out_info) {
  GstRgaVideoConvert *rgavideoconvert = gst_rga_video_convert(filter);
  GST_DEBUG_OBJECT(rgavideoconvert, "set_info");

  GstVideoFormat in_format = GST_VIDEO_INFO_FORMAT(in_info);
  GstVideoFormat out_format = GST_VIDEO_INFO_FORMAT(out_info);

  if (gst_gst_format_to_rga_format(in_format) == RK_FORMAT_UNKNOWN ||
      gst_gst_format_to_rga_format(in_format) == RK_FORMAT_UNKNOWN) {
    GST_INFO_OBJECT(filter, "don't support format. in format=%d,out format=%d",
                    in_format, out_format);
    return FALSE;
  }
  return TRUE;
}

/* transform */
static GstFlowReturn gst_rga_video_convert_transform_frame(
    GstVideoFilter *filter, GstVideoFrame *inframe, GstVideoFrame *outframe) {
  GstRgaVideoConvert *rgavideoconvert = gst_rga_video_convert(filter);

  GST_DEBUG_OBJECT(rgavideoconvert, "transform_frame");

  GstMapInfo inMapinfo = {
      0,
  };
  GstMapInfo outMapinfo = {
      0,
  };

  rga_info_t src_info = {
      0,
  };
  rga_info_t dst_info = {
      0,
  };

  if (!gst_rga_info_from_video_frame(&src_info, inframe, &inMapinfo,
                                     GST_MAP_READ))
    return GST_FLOW_ERROR;

  if (!gst_rga_info_from_video_frame(&dst_info, outframe, &outMapinfo,
                                     GST_MAP_WRITE))
    return GST_FLOW_ERROR;

  gboolean ret = TRUE;
  src_info.core = dst_info.core = rgavideoconvert->core_mask;
  if (c_RkRgaBlit(&src_info, &dst_info, NULL) < 0) {
    GST_WARNING_OBJECT(filter, "failed to blit");
    ret = FALSE;
  }

  gst_buffer_unmap(inframe->buffer, &inMapinfo);
  gst_buffer_unmap(outframe->buffer, &outMapinfo);

  if (!ret) {
    return GST_FLOW_ERROR;
  }

  return GST_FLOW_OK;
}

static gboolean plugin_init(GstPlugin *plugin) {
  /* FIXME Remember to set the rank if it's an element that is meant
   to be autoplugged by decodebin. */
  return gst_element_register(plugin, "rgavideoconvert", GST_RANK_PRIMARY,
                              GST_TYPE_RGA_VIDEO_CONVERT);
}

#ifndef VERSION
#define VERSION "1.0.0"
#endif
#ifndef PACKAGE
#define PACKAGE "gstreamer-rga"
#endif
#ifndef PACKAGE_NAME
#define PACKAGE_NAME "gstreamer-rga"
#endif
#ifndef GST_PACKAGE_ORIGIN
#define GST_PACKAGE_ORIGIN "https://github.com/corenel/gstreamer-rga.git"
#endif

GST_PLUGIN_DEFINE(GST_VERSION_MAJOR, GST_VERSION_MINOR, rgavideoconvert,
                  "video Colorspace conversion & scaler", plugin_init, VERSION,
                  "MIT/X11", PACKAGE_NAME, GST_PACKAGE_ORIGIN)
