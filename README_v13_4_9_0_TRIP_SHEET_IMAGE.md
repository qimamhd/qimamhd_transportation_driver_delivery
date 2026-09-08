# 13.0.4.9.0 - Trip sheet image

Adds an optional backward-compatible binary trip sheet image on each driver delivery line. New mobile build 0.5.48+79 requires the image in both route and direct-delivery flows. The API validates JPG/PNG and limits decoded image size to 2.5 MB. Existing older clients remain compatible because the server field itself is not mandatory.
