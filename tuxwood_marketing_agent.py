"""
TUXWOOD — Rishad (Marketing Agent) — CLOUD VERSION
====================================================
Creates daily social media content using Claude AI.
Sends platform-specific captions + content to owner via WhatsApp.

Platforms: Instagram, Facebook, TikTok, WhatsApp Status
Content: Product promotions, offers, new arrivals, weekly campaigns

Railway Cron: 0 5 * * *  (5:00 AM UTC = 9:00 AM UAE)
Command: python tuxwood_marketing_agent.py
"""

import os
import requests
import random
from datetime import datetime
from anthropic import Anthropic

# ============================================================
# CONFIG
# ============================================================
WHATSAPP_TOKEN    = os.environ.get("WHATSAPP_TOKEN",  "")
PHONE_NUMBER_ID   = os.environ.get("PHONE_NUMBER_ID", "1127995510386994")
OWNER_NUMBER      = os.environ.get("OWNER_NUMBER",    "971569394846")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# ============================================================

client = Anthropic(api_key=ANTHROPIC_API_KEY)

PRODUCTS = [
    {"name": "Mountain Fresh", "price": 89, "size": "65ml", "notes": "Fresh, clean, energizing woody scent", "gender": "Unisex"},
    {"name": "Ligero Tobacco", "price": 89, "size": "65ml", "notes": "Bold smoky tobacco + oud, rich and masculine", "gender": "Masculine"},
    {"name": "Oud Al Dahab",   "price": 89, "size": "65ml", "notes": "Pure luxury oud with leather warmth", "gender": "Masculine"},
    {"name": "Royal Velvet",   "price": 89, "size": "65ml", "notes": "Sweet, smooth, elegant cotton candy warmth", "gender": "Unisex"},
    {"name": "Green Desert",   "price": 89, "size": "65ml", "notes": "Fresh green + floral + light oud", "gender": "Unisex"},
    {"name": "Holysmells",     "price": 89, "size": "65ml", "notes": "Spiritual, calming, floral warmth", "gender": "Unisex"},
    {"name": "Rosy Magic",     "price": 89, "size": "65ml", "notes": "Fresh rose with green and leathery elegance", "gender": "Unisex"},
    {"name": "Sulthan",        "price": 89, "size": "65ml", "notes": "Fresh royal citrus with musky woody base", "gender": "Unisex"},
    {"name": "Enigma",         "price": 89, "size": "65ml", "notes": "Mysterious, seductive, slowly unfolds", "gender": "Unisex"},
    {"name": "Manly",          "price": 89, "size": "65ml", "notes": "Bold, dark, intensely masculine warm spices", "gender": "Masculine"},
    {"name": "Force",          "price": 69, "size": "50ml", "notes": "Powerful oud leather, hero product", "gender": "Masculine"},
    {"name": "Queen",          "price": 69, "size": "50ml", "notes": "Elegant royal, special occasions", "gender": "Feminine"},
    {"name": "Vintage",        "price": 69, "size": "50ml", "notes": "Office, subtle elegance", "gender": "Unisex"},
    {"name": "Desire",         "price": 49, "size": "50ml", "notes": "Sweet warm addictive, perfect for dates", "gender": "Unisex"},
    {"name": "Midnight",       "price": 49, "size": "50ml", "notes": "Dark mysterious bold, night wear", "gender": "Masculine"},
    {"name": "Softness",       "price": 49, "size": "50ml", "notes": "Gentle smooth comforting, daily wear", "gender": "Feminine"},
]

WEEKLY_CAMPAIGNS = {
    "Monday":    "New Week New Scent — motivational + product push",
    "Tuesday":   "Top Seller Tuesday — highlight best sellers",
    "Wednesday": "Mid-Week Mood — match scent to mood/occasion",
    "Thursday":  "Throwback scent story — brand story + heritage",
    "Friday":    "Friday Feels — weekend fragrance picks",
    "Saturday":  "Weekend Special — combo deal or offer",
    "Sunday":    "Self Care Sunday — soft, calming fragrances",
}


def send_whatsapp(message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": OWNER_NUMBER, "type": "text", "text": {"body": message}})
    return r.status_code, r.json()


def generate_content(product, weekday, campaign):
    prompt = f"""You are Rishad — the marketing agent for Tuxwood Perfumes, a premium UAE perfume brand.

Today is {weekday}. Campaign theme: {campaign}

Product to feature today:
- Name: {product['name']}
- Price: AED {product['price']} | Size: {product['size']}
- Scent profile: {product['notes']}
- Gender: {product['gender']}

Brand info:
- UAE-based, premium quality at affordable prices
- Free delivery on combo packs, AED 15 for single items
- COD available, next day delivery across UAE

Create 4 separate posts. Format exactly like this:

📸 *INSTAGRAM*
[Caption — engaging, 3-4 lines, storytelling tone, emojis, 5-8 hashtags]

📘 *FACEBOOK*
[Caption — warm and friendly, 4-5 lines, include price and delivery info, 3-4 hashtags]

🎵 *TIKTOK*
[Short punchy hook, trendy, 2-3 lines, 5-6 trending hashtags]

💬 *WHATSAPP STATUS*
[1-2 lines max, direct, include price]

Tone: confident, luxury feel, human, not salesy. English only."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"❌ Claude error: {e}")
        return None


def main():
    today   = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")

    print("=" * 60)
    print("  TUXWOOD — Rishad (Marketing Agent) — CLOUD")
    print(f"  Date: {today} | Day: {weekday}")
    print("=" * 60)

    product  = random.choice(PRODUCTS)
    campaign = WEEKLY_CAMPAIGNS.get(weekday, "Product Spotlight")

    print(f"\n🎯 Today's product: {product['name']}")
    print(f"📅 Campaign: {campaign}")

    print("\n🤖 Generating content with Claude AI...")
    content = generate_content(product, weekday, campaign)

    if not content:
        send_whatsapp("❌ Rishad: Could not generate content today. Claude API issue.")
        return

    header = (
        f"🎨 *Rishad — Daily Marketing Content*\n"
        f"📅 {today} | {weekday}\n"
        f"{'━'*30}\n"
        f"🌿 *Featured: {product['name']}* — AED {product['price']}\n"
        f"🎯 *Theme: {campaign}*\n"
        f"{'━'*30}\n\n"
    )

    full_message = header + content + f"\n\n{'━'*30}\n🤖 Rishad — Marketing Agent"

    if len(full_message) > 3800:
        part1 = header + content[:1800] + "\n\n_(continued...)_"
        part2 = content[1800:] + f"\n\n{'━'*30}\n🤖 Rishad — Marketing Agent"
        print("\n📤 Sending Part 1...")
        send_whatsapp(part1)
        print("📤 Sending Part 2...")
        code, resp = send_whatsapp(part2)
    else:
        print("\n📤 Sending to owner...")
        code, resp = send_whatsapp(full_message)

    if code == 200:
        print("✅ Marketing content sent!")
    else:
        print(f"❌ Failed: {resp}")


if __name__ == "__main__":
    main()
