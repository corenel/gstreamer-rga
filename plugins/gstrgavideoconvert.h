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
 * Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
 * Boston, MA 02110-1301, USA.
 */

#ifndef PLUGINS_GSTRGAVIDEOCONVERT_H_
#define PLUGINS_GSTRGAVIDEOCONVERT_H_

#include <gst/base/gstbasetransform.h>

G_BEGIN_DECLS

#define GST_TYPE_RGAVIDEOCONVERT (gst_rgavideoconvert_get_type())
#define GST_RGAVIDEOCONVERT(obj)                               \
  (G_TYPE_CHECK_INSTANCE_CAST((obj), GST_TYPE_RGAVIDEOCONVERT, \
                              GstRgavideoconvert))
#define GST_RGAVIDEOCONVERT_CLASS(klass)                      \
  (G_TYPE_CHECK_CLASS_CAST((klass), GST_TYPE_RGAVIDEOCONVERT, \
                           GstRgavideoconvertClass))
#define GST_IS_RGAVIDEOCONVERT(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj), GST_TYPE_RGAVIDEOCONVERT))
#define GST_IS_RGAVIDEOCONVERT_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass), GST_TYPE_RGAVIDEOCONVERT))

typedef struct _GstRgavideoconvert GstRgavideoconvert;
typedef struct _GstRgavideoconvertClass GstRgavideoconvertClass;

struct _GstRgavideoconvert {
  GstBaseTransform base_rgavideoconvert;
};

struct _GstRgavideoconvertClass {
  GstBaseTransformClass base_rgavideoconvert_class;
};

GType gst_rgavideoconvert_get_type(void);

G_END_DECLS

#endif  // PLUGINS_GSTRGAVIDEOCONVERT_H_
