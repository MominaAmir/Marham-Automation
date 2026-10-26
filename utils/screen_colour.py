"""Which chips are selected, when the app shows it ONLY by colour (the page source is the same for a
selected and an unselected chip): Scheduler Settings' slot length, Hospital Details' day chips,
Booking Summary's date chip.

A selected chip is green (filled or with a green border and text); an unselected one is grey/white.
We take ONE screenshot and measure, inside each chip's box, the share of clearly green pixels.
Needs Pillow:  pip install pillow   (without it the functions return None and the test notes that)."""
import io

try:
    from PIL import Image
except ImportError:                                    # Pillow not installed
    Image = None


def screenshot(driver):
    if Image is None:
        return None
    return Image.open(io.BytesIO(driver.get_screenshot_as_png())).convert("RGB")


def green_share(image, box):
    """Share (0..1) of green pixels in box (x1, y1, x2, y2), checking every 2nd pixel."""
    x1, y1, x2, y2 = box
    green = total = 0
    for y in range(max(y1, 0), min(y2, image.height), 2):
        for x in range(max(x1, 0), min(x2, image.width), 2):
            r, g, b = image.getpixel((x, y))
            total += 1
            if g > 110 and g - max(r, b) > 35:
                green += 1
    return green / total if total else 0.0


def selected_one(driver, named_boxes, min_gap=0.02):
    """For a group where exactly ONE chip is selected: {name: box} -> the selected name, or None
    (Pillow missing, or no chip clearly greener than the others). Also returns the measured shares."""
    image = screenshot(driver)
    if image is None:
        return None, {}
    shares = {name: round(green_share(image, box), 3) for name, box in named_boxes.items()}
    ranked = sorted(shares.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= min_gap:
        return ranked[0][0], shares
    return None, shares


def selected_many(driver, boxes, threshold=0.2):
    """For a group where several chips can be selected (days M..S): [box] -> [True/False], or None."""
    image = screenshot(driver)
    if image is None:
        return None
    return [green_share(image, box) >= threshold for box in boxes]