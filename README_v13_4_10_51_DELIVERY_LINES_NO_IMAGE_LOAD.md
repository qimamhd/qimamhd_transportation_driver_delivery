# 13.0.4.10.51 - Deliveries list without loading trip sheet images

- `has_trip_sheet_image` in `/delivery-lines` and `/current-batch` was computed with
  `bool(line.trip_sheet_image)`, which loads every image file (attachment field) just to test presence.
- Now one `ir.attachment` search per request returns the ids of lines that have an image.
- Response shape and values unchanged. No app update, no new fields.
