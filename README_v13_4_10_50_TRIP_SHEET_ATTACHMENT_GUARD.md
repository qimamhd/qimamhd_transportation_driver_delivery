# 13.0.4.10.50 - Protect the trip sheet attachment

- Deleting or replacing an existing trip sheet image is allowed only while the batch is
  `draft` or `done` (before review starts). Enforced in `write()`; the "حذف المرفق" button is hidden otherwise.
- Adding an image to a line that has none stays allowed in any state.
- Every add / replace / delete is posted in the batch chatter with the line id (author = current user).
- The "إضافة مرفق" wizard accepts JPG or PNG only, max 5 MB.
- New non-stored related field `batch_state` on the line (for the view). No app update needed.
