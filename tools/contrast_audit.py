#!/usr/bin/env python3
"""Audit the dashboard's core text palette against WCAG AA contrast targets."""

PALETTE = {
    "primary text": "#263548",
    "secondary text": "#52647A",
    "brand navy": "#174A78",
    "green status text": "#426653",
    "amber status text": "#805B20",
    "red status text": "#914848",
}


def luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    rgb = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    failed = False
    print("Vana dashboard text contrast audit (white surface)")
    for name, color in PALETTE.items():
        ratio = contrast_ratio(color, "#FFFFFF")
        status = "PASS" if ratio >= 4.5 else "FAIL"
        print(f"{status:4}  {name:22} {color}  {ratio:.2f}:1")
        failed |= ratio < 4.5
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
