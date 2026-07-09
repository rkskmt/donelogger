"""Generate assets/demo.gif — an animated terminal showing donelogger in action.

Renders frames with Pillow (Consolas) and lets the caller stitch them into a GIF
with ffmpeg. Re-run this whenever the output format changes:

    python assets/make_demo.py
    ffmpeg -y -framerate 12 -i assets/_frames/f%03d.png \
        -vf "split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse" \
        assets/demo.gif
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "_frames")
os.makedirs(FRAMES, exist_ok=True)

# --- Catppuccin-ish dark palette -------------------------------------------
BG      = (30, 30, 46)
BAR     = (49, 50, 68)
RED     = (243, 139, 168)
YELLOW  = (249, 226, 175)
GREEN   = (166, 227, 161)
PEACH   = (250, 179, 135)
BLUE    = (137, 180, 250)
DIM     = (108, 112, 134)
TEXT    = (205, 214, 244)
ELAPSED = (249, 226, 175)   # highlight colour for the measured time

FS = 26
FONT = ImageFont.truetype("consola.ttf", FS)
BOLD = ImageFont.truetype("consolab.ttf", FS)

PAD_X, PAD_TOP = 28, 64        # PAD_TOP leaves room for the title bar
LINE_H = FS + 12
CW = FONT.getlength("M")        # monospace cell width

# Canvas sized to the widest line we render.
COLS = 60
W = int(PAD_X * 2 + CW * COLS)
H = PAD_TOP + LINE_H * 7 + 24


def seg(*parts):
    """A line is a list of (text, colour, bold) segments."""
    return [(t, c, b) for (t, c, b) in parts]


def log_line(ts, marker, marker_col, tag, elapsed, msg, hot=False):
    """Build a coloured donelogger output line as segments."""
    parts = [(ts, DIM, False), ("|", DIM, False), ("INFO", BLUE, False),
             ("|", DIM, False), (marker, marker_col, True)]
    inner = f"[{'Go' if marker == '+' else 'Done'} {tag}"
    parts.append((inner, TEXT, False))
    if elapsed:
        parts.append(("(", TEXT, False))
        parts.append((elapsed, ELAPSED if hot else ELAPSED, True))
        parts.append((")", TEXT, False))
    parts.append(("] ", TEXT, False))
    parts.append((msg, TEXT, False))
    return parts


# Static lines of the "session".
# The outer job wraps the inner load/train timers.
PROMPT = seg(("$ ", GREEN, True), ("python train.py", TEXT, False))
GO_JOB    = log_line("12:25:01", "+", GREEN, "job", None, "Starting training job")
GO_LOAD   = log_line("12:25:01", "+", GREEN, "load", None, "Loading dataset...")
DONE_LOAD = log_line("12:25:03", "-", PEACH, "load", "2.001s", "Finished loading", hot=True)
GO_TRAIN  = log_line("12:25:03", "+", GREEN, "train", None, "Training model...")
DONE_TRN  = log_line("12:26:27", "-", PEACH, "train", "1m23.40s", "Finished training", hot=True)
DONE_JOB  = log_line("12:26:27", "-", PEACH, "job", "1m25.40s", "Job complete", hot=True)

SPIN = "|/-\\"


def draw(lines, cursor=False, spinner=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # title bar
    d.rectangle([0, 0, W, 44], fill=BAR)
    for i, col in enumerate((RED, YELLOW, GREEN)):
        d.ellipse([PAD_X + i * 26, 14, PAD_X + i * 26 + 16, 30], fill=col)
    d.text((W / 2, 22), "donelogger", font=FONT, fill=DIM, anchor="mm")
    # body
    y = PAD_TOP
    for line in lines:
        x = PAD_X
        for text, col, bold in line:
            f = BOLD if bold else FONT
            d.text((x, y), text, font=f, fill=col)
            x += f.getlength(text)
        if line is lines[-1] and spinner is not None:
            d.text((x + CW, y), spinner, font=BOLD, fill=YELLOW)
        if line is lines[-1] and cursor:
            d.rectangle([x + 2, y + 2, x + 2 + CW, y + FS], fill=TEXT)
        y += LINE_H
    return img


frames = []          # (image, repeat_count)


def add(img, hold=1):
    frames.append((img, hold))


# 1) type the command
typed = "$ python train.py"
for i in range(2, len(typed) + 1, 2):
    line = seg(("$ ", GREEN, True), (typed[2:i], TEXT, False))
    add(draw([line], cursor=True))
add(draw([PROMPT], cursor=True), hold=4)

shown = [PROMPT]

# 2) whole job starts
shown = shown + [GO_JOB]
add(draw(shown, cursor=True), hold=3)

# 3) data_load starts
shown = shown + [GO_LOAD]
add(draw(shown, cursor=True), hold=3)

# 4) working spinner
for k in range(8):
    add(draw(shown, spinner=SPIN[k % 4]))

# 5) data_load done — flash the elapsed time
shown = shown + [DONE_LOAD]
for k in range(4):
    hot = log_line("12:25:03", "-", PEACH, "load", "2.001s", "Finished loading", hot=True)
    add(draw(shown[:-1] + [hot], cursor=False), hold=3)
add(draw(shown, cursor=True), hold=2)

# 6) train starts
shown = shown + [GO_TRAIN]
add(draw(shown, cursor=True), hold=3)

# 7) longer spinner
for k in range(12):
    add(draw(shown, spinner=SPIN[k % 4]))

# 8) train done — flash
shown = shown + [DONE_TRN]
for k in range(5):
    add(draw(shown, cursor=False), hold=3)

# 9) whole job done — flash
shown = shown + [DONE_JOB]
for k in range(5):
    add(draw(shown, cursor=False), hold=3)

# 10) hold final
add(draw(shown, cursor=True), hold=20)

# expand holds into individual frames
idx = 0
for img, hold in frames:
    for _ in range(hold):
        img.save(os.path.join(FRAMES, f"f{idx:03d}.png"))
        idx += 1

print(f"wrote {idx} frames to {FRAMES}  ({W}x{H})")
