# The Meritocratic Humanist

Humanism. Merit. Consequence. A continuing log on earned excellence.

The site at https://merithumanist.github.io is generated from this repo. Each Log lives in its own folder; everything else is built automatically.

## Adding a Log

1. Copy the previous Log's folder, e.g. `logs/067/` → `logs/068/`.
2. Edit `logs/068/log.md`:
   - `seq:` the Log number × 10 (`680`). Special Logs slot between, e.g. `675`.
   - `title:`, `alt:`, and `image:` (the image file's name in the same folder).
   - `status: scheduled` and `scheduled:` the post time in **UTC**, e.g. `2026-11-18T14:00:00Z`.
   - Replace the text under the second `---`. A blank line starts a new paragraph.
3. Put the image in the same folder.
4. `git add logs/068 && git ci -m "Log 068" && git push`

The site checks hourly and shows a scheduled Log once its time has passed.

## Status

- `published`: always shown
- `scheduled`: shown once `scheduled` (UTC) has passed
- `draft`: never shown

## Local preview

```
pip install pyyaml pillow
python build.py --preview   # includes scheduled and draft Logs
cd _site && python -m http.server
```

Images are resized to 1200px and stripped of metadata when the site is built.
