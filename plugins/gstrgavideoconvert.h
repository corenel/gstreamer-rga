/* GStreamer
 * Copyright (C) 2021 FIXME <fixme@example.com>
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
 * Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
 * Boston, MA 02110-1301, USA.
 */

#ifndef PLUGINS_GSTRGAVIDEOCONVERT_H_
#define PLUGINS_GSTRGAVIDEOCONVERT_H_

#include <gst/video/gstvideofilter.h>
#include <gst/video/video.h>

G_BEGIN_DECLS

#define GST_TYPE_RGA_VIDEO_CONVERT (gst_rga_video_convert_get_type())
#define gst_rga_video_convert(obj)                               \
  (G_TYPE_CHECK_INSTANCE_CAST((obj), GST_TYPE_RGA_VIDEO_CONVERT, \
                              GstRgaVideoConvert))
#define gst_rga_video_convert_CLASS(klass)                      \
  (G_TYPE_CHECK_CLASS_CAST((klass), GST_TYPE_RGA_VIDEO_CONVERT, \
                           GstRgaVideoConvertClass))
#define GST_IS_RGA_VIDEO_CONVERT(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj), GST_TYPE_RGA_VIDEO_CONVERT))
#define GST_IS_RGA_VIDEO_CONVERT_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass), GST_TYPE_RGA_VIDEO_CONVERT))

typedef struct _GstRgaVideoConvert GstRgaVideoConvert;
typedef struct _GstRgaVideoConvertClass GstRgaVideoConvertClass;

struct _GstRgaVideoConvert {
  GstVideoFilter base_rgavideoconvert;
  guint32 core_mask;
};

struct _GstRgaVideoConvertClass {
  GstVideoFilterClass base_rgavideoconvert_class;
};

GType gst_rga_video_convert_get_type(void);

G_END_DECLS

#endif  // PLUGINS_GSTRGAVIDEOCONVERT_H_
