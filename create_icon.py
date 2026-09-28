"""Generate a premium modern app icon for YouTube Video Downloader Pro."""

import os
import math
from PIL import Image, ImageDraw, ImageFilter


def create_premium_icon(output_dir="assets"):
    os.makedirs(output_dir, exist_ok=True)
    size = 1024  # Render at high resolution then downsample for crispness
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    
    # 1. Outer background: rounded squircle with subtle drop shadow
    # Create shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    margin = 80
    corner_radius = 210
    
    s_draw.rounded_rectangle(
        [margin + 10, margin + 25, size - margin - 10, size - margin + 5],
        radius=corner_radius,
        fill=(0, 0, 0, 160)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=28))
    img.alpha_composite(shadow)
    
    # 2. Main base badge: Deep Obsidian / Midnight Dark Gradient with subtle inner glow
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(badge)
    
    # Draw smooth gradient inside rounded rectangle
    base_mask = Image.new("L", (size, size), 0)
    bm_draw = ImageDraw.Draw(base_mask)
    bm_draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=corner_radius,
        fill=255
    )
    
    # Gradient image for base
    grad_base = Image.new("RGBA", (size, size))
    for y in range(size):
        ratio = y / size
        # Dark obsidian navy/graphite gradient
        r = int(18 + ratio * 8)
        g = int(21 + ratio * 6)
        b = int(32 + ratio * 12)
        for x in range(size):
            grad_base.putpixel((x, y), (r, g, b, 255))
    
    img.paste(grad_base, (0, 0), base_mask)
    
    # Border stroke: Premium Red/Neon Crimson glow outline
    stroke_mask = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sm_draw = ImageDraw.Draw(stroke_mask)
    sm_draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=corner_radius,
        outline=(255, 30, 60, 220),
        width=8
    )
    # Add subtle glow around border
    glow_border = stroke_mask.filter(ImageFilter.GaussianBlur(radius=6))
    img.alpha_composite(glow_border)
    img.alpha_composite(stroke_mask)
    
    # 3. Inner YouTube Rounded Card / Shield (Vibrant YouTube Crimson Red Gradient)
    yt_card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    yt_draw = ImageDraw.Draw(yt_card)
    card_margin_x = 210
    card_margin_y = 230
    card_radius = 120
    
    card_box = [card_margin_x, card_margin_y, size - card_margin_x, size - card_margin_y]
    
    # Card shadow
    card_shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cs_draw = ImageDraw.Draw(card_shadow)
    cs_draw.rounded_rectangle(
        [card_box[0], card_box[1] + 15, card_box[2], card_box[3] + 25],
        radius=card_radius,
        fill=(255, 0, 50, 70)
    )
    card_shadow = card_shadow.filter(ImageFilter.GaussianBlur(radius=20))
    img.alpha_composite(card_shadow)
    
    # Card Gradient: Bright Red #FF0033 to Deep Burgundy #99001A
    card_mask = Image.new("L", (size, size), 0)
    cm_draw = ImageDraw.Draw(card_mask)
    cm_draw.rounded_rectangle(card_box, radius=card_radius, fill=255)
    
    card_grad = Image.new("RGBA", (size, size))
    for y in range(card_box[1], card_box[3] + 1):
        ratio = (y - card_box[1]) / max(1, (card_box[3] - card_box[1]))
        r = int(255 - ratio * 75)   # 255 -> 180
        g = int(25 - ratio * 20)    # 25 -> 5
        b = int(55 - ratio * 40)    # 55 -> 15
        for x in range(card_box[0], card_box[2] + 1):
            card_grad.putpixel((x, y), (r, g, b, 255))
            
    img.paste(card_grad, (0, 0), card_mask)
    
    # Specular glass reflection overlay on top half of card
    spec_mask = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sp_draw = ImageDraw.Draw(spec_mask)
    sp_draw.ellipse(
        [card_box[0] - 100, card_box[1] - 150, card_box[2] + 100, card_box[1] + 240],
        fill=(255, 255, 255, 45)
    )
    # Clip reflection to card
    spec_clipped = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    spec_clipped.paste(spec_mask, (0, 0), card_mask)
    img.alpha_composite(spec_clipped)

    # 4. Central Emblem: Modern Play Button + Download Arrow Combination
    # We create a crisp stylized icon:
    # A sleek download arrow with bold geometry, resting above an elegant download arc/bar,
    # OR: A centered play triangle with a dynamic download arrow cut or overlay.
    # Let's create an iconic, high-end design:
    # Top: Play triangle contour / symbol
    # Center-Down: Bold descending download arrow with glowing tip and an arched tray.
    
    center_x = size // 2
    center_y = size // 2 - 10
    
    emblem = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    e_draw = ImageDraw.Draw(emblem)
    
    # Download Arrow:
    # Arrow Stem
    stem_width = 54
    stem_top = center_y - 120
    stem_bottom = center_y + 40
    
    # Arrow Head
    head_top = center_y + 10
    head_bottom = center_y + 120
    head_width = 160
    
    # Draw Arrow Shaft (rounded top)
    e_draw.rounded_rectangle(
        [center_x - stem_width // 2, stem_top, center_x + stem_width // 2, stem_bottom],
        radius=14,
        fill=(255, 255, 255, 255)
    )
    
    # Draw Arrow Point (Triangle)
    arrow_points = [
        (center_x, head_bottom),  # Tip pointing down
        (center_x - head_width // 2, head_top),  # Left wing
        (center_x + head_width // 2, head_top),  # Right wing
    ]
    e_draw.polygon(arrow_points, fill=(255, 255, 255, 255))
    
    # Tray / Bar underneath the arrow
    tray_y = center_y + 160
    tray_width = 190
    tray_thick = 36
    tray_radius = 18
    e_draw.rounded_rectangle(
        [center_x - tray_width // 2, tray_y, center_x + tray_width // 2, tray_y + tray_thick],
        radius=tray_radius,
        fill=(255, 255, 255, 255)
    )
    
    # Add subtle soft shadow to emblem
    emblem_shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    es_draw = ImageDraw.Draw(emblem_shadow)
    es_draw.rounded_rectangle(
        [center_x - stem_width // 2, stem_top + 8, center_x + stem_width // 2, stem_bottom + 8],
        radius=14, fill=(0, 0, 0, 100)
    )
    es_draw.polygon(
        [(p[0], p[1] + 8) for p in arrow_points],
        fill=(0, 0, 0, 100)
    )
    es_draw.rounded_rectangle(
        [center_x - tray_width // 2, tray_y + 8, center_x + tray_width // 2, tray_y + tray_thick + 8],
        radius=tray_radius, fill=(0, 0, 0, 100)
    )
    emblem_shadow = emblem_shadow.filter(ImageFilter.GaussianBlur(radius=8))
    
    img.alpha_composite(emblem_shadow)
    img.alpha_composite(emblem)
    
    # 5. Top-Right "4K / PRO" Badge
    badge_x = size - margin - 150
    badge_y = margin + 45
    badge_w = 120
    badge_h = 44
    pro_badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pb_draw = ImageDraw.Draw(pro_badge)
    pb_draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=22,
        fill=(255, 45, 85, 240),
        outline=(255, 255, 255, 180),
        width=3
    )
    img.alpha_composite(pro_badge)
    
    # Add text "PRO" on badge using clean geometric rendering
    # Draw simple crisp PRO letters
    # P:
    px = badge_x + 30
    py = badge_y + 12
    pb_draw_t = ImageDraw.Draw(img)
    # Draw P
    pb_draw_t.line([(px, py), (px, py + 20)], fill=(255, 255, 255, 255), width=4)
    pb_draw_t.arc([px - 2, py, px + 14, py + 12], start=-90, end=90, fill=(255, 255, 255, 255), width=4)
    # Draw R
    rx = px + 22
    pb_draw_t.line([(rx, py), (rx, py + 20)], fill=(255, 255, 255, 255), width=4)
    pb_draw_t.arc([rx - 2, py, rx + 14, py + 12], start=-90, end=90, fill=(255, 255, 255, 255), width=4)
    pb_draw_t.line([(rx + 5, py + 10), (rx + 14, py + 20)], fill=(255, 255, 255, 255), width=4)
    # Draw O
    ox = rx + 24
    pb_draw_t.ellipse([ox, py, ox + 14, py + 20], outline=(255, 255, 255, 255), width=4)

    # Save high-res PNG
    png_path = os.path.join(output_dir, "icon.png")
    img.save(png_path, "PNG")
    print(f"[OK] Saved high-res icon PNG: {png_path}")
    
    # Generate multi-resolution .ico file
    ico_path = os.path.join(output_dir, "icon.ico")
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=icon_sizes)
    print(f"[OK] Saved multi-resolution icon ICO: {ico_path}")


if __name__ == "__main__":
    create_premium_icon()
