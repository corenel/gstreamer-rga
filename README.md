# gstreamer-rga

Hardware-accelerated 2D graphics processing on Rockchip platforms through RGA.

NOTE:

plugins can be installed locally by using "$HOME" as prefix:

  $ meson --prefix="$HOME" build/
  $ ninja -C build/ install

However be advised that the automatic scan of plugins in the user home
directory won't work under gst-build devenv.
