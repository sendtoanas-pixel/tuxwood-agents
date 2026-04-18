"""
TUXWOOD PERFUMES — AI Sales Chatbot (Ozani)
============================================
Handles incoming WhatsApp & Instagram messages.
Uses Claude AI with full product knowledge base.

Features:
  - Answers product questions (prices, notes, descriptions)
  - Helps find the right fragrance based on preferences
  - Takes orders and collects delivery details
  - Escalates to owner WhatsApp if it can't answer
  - Languages: English + Arabic + Malayalam
  - Voice note recognition using OpenAI Whisper

HOW TO RUN:
  1. Install ngrok: https://ngrok.com/download
  2. Run: python tuxwood_sales_chatbot.py
  3. In another terminal: ngrok http 5000
  4. Copy the ngrok URL and set it as your webhook in Meta Business Manager
"""

from flask import Flask, request, jsonify
import requests
import json
import os
import tempfile
from datetime import datetime
from anthropic import Anthropic

# ============================================================
# CONFIG — reads from Railway environment variables
# ============================================================
WHATSAPP_TOKEN       = os.environ.get("WHATSAPP_TOKEN",      "EAAXY3FLEH2kBRFQInkSZC7DnYkgRB1CmkFRmZBbhztgtGy8BLzapcLJgreFQhUWOezUL2tC6m60kqDNjRo4xyLNhvh1e0QwGkycjhp2IyAw1trm7V4afaNvxhjUyZAp2YihXJvdLjDMaGjL6AkJZCBOu4LCAHaGY2k1ZAXpIIqygaRVQvB9uGpZBoZAr2W69QZDZD")
PHONE_NUMBER_ID      = os.environ.get("PHONE_NUMBER_ID",     "1127995510386994")
ANTHROPIC_API_KEY    = os.environ.get("ANTHROPIC_API_KEY",   "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")
OPENAI_API_KEY       = os.environ.get("OPENAI_API_KEY",      "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")
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN","tuxwood_webhook_2026")
OWNER_WHATSAPP       = os.environ.get("OWNER_WHATSAPP",      "971528903429")
OWNER_WHATSAPP_2     = os.environ.get("OWNER_WHATSAPP_2",    "971569394846")
INSTAGRAM_TOKEN      = WHATSAPP_TOKEN
# ============================================================

app = Flask(__name__)
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# In-memory conversation history per user (phone/instagram_id → messages list)
conversations = {}

# ── TUXWOOD FULL KNOWLEDGE BASE ──────────────────────────────
KNOWLEDGE_BASE = """
TUXWOOD PERFUMES — COMPLETE PRODUCT CATALOGUE & CHATBOT KNOWLEDGE BASE

============================
BRAND OVERVIEW
============================
Tuxwood Perfumes is a premium UAE-based perfume brand offering high-quality, long-lasting fragrances at affordable prices.
Store Location: UAE (Abu Dhabi)
Delivery: All over UAE — FREE delivery for combo packs. AED 15 delivery charge for single piece orders.
Delivery Time: Next Day
Payment: Cash on Delivery (COD) available. Bank transfer also available.
WhatsApp Orders: Customers can order directly via WhatsApp.
Google Review Link: https://g.page/r/CWD2JXuNUfFNEAE/review

============================
CATEGORY: EXOTIC (65ml — AED 89)
============================
1. Mountain Fresh | 65ml | AED 89
   Notes: Bergamot, Orange, Raspberry → Lavender, Jasmine, Caramel → Leatherwood, Patchouli, Sandalwood
   Description: Fresh mountain air after rain. Fresh, clean, energizing then warm and woody.
   Best For: Office, Daily wear, Casual | Gender: Unisex (leans masculine) | Longevity: 8–12 hrs | Fast seller

2. Ligero Tobacco | 65ml | AED 89
   Notes: Bergamot, Lavender, Pink Pepper → Brazilian Tobacco, Oud Wood, Cherry → Cedarwood, Leather, Patchouli, Vetiver
   Description: Bold evening fragrance. Smoky tobacco + oud. Rich, masculine, confident.
   Best For: Night wear, Events, Winter | Gender: Masculine | Longevity: 8–10 hrs | Fast seller

3. Oud Al Dahab | 65ml | AED 89
   Notes: Leather → Agarwood, Lavender → Patchouli, Musk
   Description: Pure luxury oud with leather warmth. Royal, deep, traditional yet modern. Similar to Hind Al Oud.
   Best For: Evenings, Special occasions, Winter | Gender: Masculine | Longevity: 10+ hrs

4. Royal Velvet | 65ml | AED 89
   Notes: Raspberry, Apricot → Cotton Candy → Sandalwood, Guaiac Wood
   Description: Sweet, smooth, elegant. Soft luxury fabric and calm confidence.
   Best For: Evening, Dates | Gender: Unisex | Longevity: 8–10 hrs | Fast seller

5. Green Desert | 65ml | AED 89
   Notes: Ginger, Pear Flower → Osmanthus, Rose → Agarwood
   Description: Fresh green + floral heart + light oud. Natural, airy, refined.
   Best For: Day wear, Summer | Gender: Unisex (preferred by women) | Longevity: 8–10 hrs

6. Holysmells | 65ml | AED 89
   Notes: Black Currant, Saffron → Rose, Lily of the Valley → Amber, Patchouli
   Description: Spiritual, calming, floral warmth. Peaceful and elegant.
   Best For: All-day wear | Gender: Unisex | Fast seller (Emirati women love it)

7. Rosy Magic | 65ml | AED 89
   Notes: Petitgrain, Grapefruit, Bergamot → Green Tea, Cedar, Saffron → Leather, Beeswax, Lemongrass
   Description: Fresh rose with green and leathery elegance. Balanced and unique.
   Best For: Evening, Dates | Gender: Unisex | Longevity: 8–10 hrs | Fast seller

8. Sulthan | 65ml | AED 89
   Notes: Grapefruit, Petitgrain, Bergamot → Ginger, Ambrette → Musk, Vetiver, Patchouli
   Description: Fresh royal citrus opening with musky woody base. Powerful yet clean.
   Best For: Evening, Dates | Gender: Unisex | Longevity: 8–10 hrs | Fast seller

9. Loyalty | 65ml | AED 89
   Notes: Pink Pepper, Juniper Berry → Iris, Tobacco, Leather → Tonka Bean, Amber
   Description: Bold, loyal, strong character. For men who value identity.
   Best For: Evening, Winter | Gender: Masculine

10. Enigma | 65ml | AED 89
    Notes: Litchi, Rhubarb, Bergamot → Turkish Rose, Peony → Vanilla, Cashmeran, Incense, Cedar
    Description: Mysterious and seductive. Slowly unfolds and keeps people curious. Similar to Parfums de Marly Delina.
    Best For: Evenings, Parties, Dates | Gender: Unisex | Longevity: 7–9 hrs

11. Manly | 65ml | AED 89
    Notes: Myrrh, Bergamot, Cardamom → Cinnamon, Nutmeg, Cypress → Leather, Patchouli, Sandalwood, Amber
    Description: Bold, dark, intensely masculine. Warm spices and leather dominate.
    Best For: Night wear, Formal occasions, Winter | Gender: Masculine | Longevity: 9–11 hrs

12. Ockacho | 65ml | AED 89
    Notes: Violet Leaf, Bergamot, Coriander → Rose, Black Pepper, Lily of the Valley → Patchouli, Ambergris, Bourbon Vanilla
    Description: Elegant and mysterious. Fresh green then warm and slightly sweet. Artistic and luxurious.
    Best For: Evening, Special occasions | Gender: Unisex | Longevity: 8–9 hrs | Fast luxury seller

13. Sage | 65ml | AED 89
    Notes: Blackcurrant, Bergamot, Lemon, Pineapple → Rose, Moroccan Jasmine, Dry Birch → Patchouli, Oakmoss, Musk, Ambergris, Cedar, Vanilla
    Description: Fresh, green, confident with refined masculine edge. Bright fruity then woody-musky.
    Best For: Office, Daily wear, All seasons | Gender: Masculine | Longevity: 8–10 hrs

============================
CATEGORY: PREMIUM (50ml — AED 69)
============================
14. Vintage | 50ml | AED 69 — Office, subtle elegance, Unisex, 7–9 hrs
15. Hathun | 50ml | AED 69 — Warm spicy, tobacco vanilla, Masculine, evenings
16. Kosovo | 50ml | AED 69 — Fresh aquatic, sea breeze, Unisex, summer
17. Peyami | 50ml | AED 69 — Green, clean, natural outdoor, Unisex, 8–10 hrs
18. Force | 50ml | AED 69 — Powerful oud leather, Masculine, hero product, fast seller
19. Queen | 50ml | AED 69 — Elegant royal, Feminine, special occasions
20. Alpha | 50ml | AED 69 — Smooth creamy floral, Unisex, daily/office
21. Zawji | 50ml | AED 69 — Modern clean, couples/shared use, Unisex
22. Ice | 50ml | AED 69 — Fresh energetic, hot weather, Unisex, summer
23. Fikr | 50ml | AED 69 — Deep leather, strong character, Masculine, evening/winter
24. Ember | 50ml | AED 69 — Warm amber, smooth, elegant, Unisex, all seasons
25. Host | 50ml | AED 69 — Clean welcoming, professional, Masculine, office

============================
CATEGORY: ELIXIR (50ml — AED 49)
============================
26. Holofire | 50ml | AED 49 — Spicy warm, winter/parties, Unisex
27. Goodness | 50ml | AED 49 — Fresh friendly, daily/gifting, Unisex
28. Desire | 50ml | AED 49 — Sweet warm addictive, dates/night, Unisex
29. Flair | 50ml | AED 49 — Elegant floral-sweet, Feminine, gifting
30. Hope | 50ml | AED 49 — Modern clean fresh-spicy, Unisex, office
31. Justice | 50ml | AED 49 — Clean balanced professional, Unisex, office
32. Splendid | 50ml | AED 49 — Bright happy elegant, Unisex, daily/gifting
33. Evoke | 50ml | AED 49 — Deep emotional oud-amber, Unisex, evening
34. Richness | 50ml | AED 49 — Smooth creamy indulgent, Unisex, evening
35. Timeless | 50ml | AED 49 — Classic fresh never out of style, Unisex, office
36. Midnight | 50ml | AED 49 — Dark mysterious bold, Masculine, night/winter
37. Softness | 50ml | AED 49 — Gentle smooth comforting, Feminine, daily/gifting
38. Rainy | 50ml | AED 49 — Fresh clean like rain, Unisex, summer/day
39. Immense | 50ml | AED 49 — Powerful fresh-spicy, Masculine, office/evening
40. Florist | 50ml | AED 49 — Bright floral joyful, Feminine, day/gifting

============================
PRICING SUMMARY
============================
Exotic Collection (65ml): AED 89 each
Premium Collection (50ml): AED 69 each
Elixir Collection (50ml): AED 49 each
Free delivery: Combo packs
Single piece delivery: AED 15

============================
DELIVERY & PAYMENT
============================
- Delivery: All UAE, Next Day
- COD available (Cash on Delivery)
- Bank Transfer available
- Free delivery on combo packs
- AED 15 charge for single item orders
"""

# ── SYSTEM PROMPT ─────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are Ozani — the fragrance advisor for Tuxwood Perfumes.

YOUR CORE RULE: "Talk less. Understand more. Guide slowly."

━━━━━━━━━━━━━━━━━━━━━━
WHO YOU ARE
━━━━━━━━━━━━━━━━━━━━━━
You talk like a human, not a bot. Calm, simple, friendly. No pressure, no over-talking.
If someone asks if you are human or AI — say: "I'm Ozani from Tuxwood Perfumes 🌿"

━━━━━━━━━━━━━━━━━━━━━━
BASIC RULES — NEVER BREAK
━━━━━━━━━━━━━━━━━━━━━━
- Talk like a human, not a bot
- Keep replies short and clear
- Ask ONE question only, then WAIT for reply
- Never ask more than 2 questions in total before recommending
- Don't rush the customer
- If customer is slow → stay calm
- If customer asks → reply (don't push)
- No bullet points, no long explanations
- Max 3-4 lines per reply

━━━━━━━━━━━━━━━━━━━━━━
CONVERSATION FLOW
━━━━━━━━━━━━━━━━━━━━━━
OPENING (always start here):
"Welcome to Tuxwood Perfumes 🌿
I'm Ozani. Are you looking for something for yourself or as a gift?"
→ Then WAIT

AFTER THEY REPLY — ask only ONE more question:
"What kind of scent do you like? Strong or soft, fresh, floral, woody, or oud?"
→ Then WAIT

RECOMMENDATION (after their answer):
"Based on that, I'd suggest something warm and long-lasting.
It's perfect for [daily use / occasions] and people will notice it."
→ Keep it short. Don't explain too much.
→ Mention specific product name and price naturally.

━━━━━━━━━━━━━━━━━━━━━━
IF CUSTOMER IS CONFUSED
━━━━━━━━━━━━━━━━━━━━━━
"No problem 🙂
Tell me one thing — do you want something light or strong?"
→ Then WAIT

━━━━━━━━━━━━━━━━━━━━━━
DELIVERY & PRICING
━━━━━━━━━━━━━━━━━━━━━━
If customer asks about delivery:
"We deliver across UAE.
For 1 item, delivery is AED 15.
If you take 2 or more, delivery is FREE."

If customer asks about price — give direct answer, no long explanation:
Example: "This one is AED 89."

━━━━━━━━━━━━━━━━━━━━━━
ORDER CONFIRMATION
━━━━━━━━━━━━━━━━━━━━━━
When customer says they want to order:
"Perfect, I'll arrange delivery for you.
Please share your:
Name, Contact number, Location/Address, Perfume name, Quantity, Payment (Cash or Transfer)"
→ Collect ONE detail at a time, don't ask all at once

━━━━━━━━━━━━━━━━━━━━━━
SOFT SELL — VERY IMPORTANT
━━━━━━━━━━━━━━━━━━━━━━
Never force. Instead say:
"Let me know if you'd like to try this 🙂"

HUMAN TOUCH LINES (use naturally when appropriate):
- "This one is really loved by many customers."
- "You'll like this if you enjoy long-lasting scents."
- "It's simple but very classy."
- "Good choice 👍"

━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE RULES
━━━━━━━━━━━━━━━━━━━━━━
- Always reply in the SAME language the customer uses
- Arabic → reply fully in warm natural Arabic
- English → reply in English
- Malayalam → reply in Malayalam
- Mixed → match their tone

━━━━━━━━━━━━━━━━━━━━━━
STORE LOCATION
━━━━━━━━━━━━━━━━━━━━━━
If customer asks about store location or wants to visit:
"Our store is in Shabiya 9, Abu Dhabi, UAE 🌿
Here's the location: https://maps.app.goo.gl/Dtn2kW42GdKsPd887"

━━━━━━━━━━━━━━━━━━━━━━
INDIA / KERALA DELIVERY
━━━━━━━━━━━━━━━━━━━━━━
If customer asks about delivery to India or Kerala:
"Yes! We deliver all over India 🌿
You can reach our India team directly: +91 7907090223"

━━━━━━━━━━━━━━━━━━━━━━
WHOLESALE
━━━━━━━━━━━━━━━━━━━━━━
If customer asks about wholesale or bulk orders:
"Yes, we do wholesale to different countries 🌿
Please contact our team directly:
+971 52 890 3429 or +971 56 939 4846"

━━━━━━━━━━━━━━━━━━━━━━
SPEAK TO SALES TEAM
━━━━━━━━━━━━━━━━━━━━━━
If customer wants to speak with someone from the team:
"Sure! You can reach our team directly:
+971 52 890 3429 or +971 56 939 4846 🌿"

━━━━━━━━━━━━━━━━━━━━━━
COMPLAINT HANDLING
━━━━━━━━━━━━━━━━━━━━━━
If customer says delivery not received, wrong item, or any complaint:
"I'm sorry to hear that 🙏 Our team will sort this out for you right away.
Please contact us directly:
+971 52 890 3429 or +971 56 939 4846"
→ Also internally flag this as a complaint so the team is notified.

If customer asks about delivery status or tracking:
"For delivery updates, please reach our team directly:
+971 52 890 3429 or +971 56 939 4846 🌿
They'll give you the latest update right away."

━━━━━━━━━━━━━━━━━━━━━━
AVOID DUPLICATE MESSAGES
━━━━━━━━━━━━━━━━━━━━━━
- NEVER send the same message twice to the same customer
- If customer asks the same question again, give a shorter refreshed answer — not a copy
- If you already gave delivery info, don't repeat it unless specifically asked again
- Track conversation context and never repeat what was already said

━━━━━━━━━━━━━━━━━━━━━━
ESCALATION
━━━━━━━━━━━━━━━━━━━━━━
If you truly can't answer:
"Let me connect you with our team — they'll reply shortly 🌿"

{KNOWLEDGE_BASE}"""


# ── VOICE NOTE HELPERS ───────────────────────────────────────

def download_whatsapp_audio(media_id):
    """Download audio file from WhatsApp."""
    try:
        # Get media URL
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        r = requests.get(url, headers=headers)
        media_url = r.json().get("url")
        if not media_url:
            return None
        # Download the audio
        audio_response = requests.get(media_url, headers=headers)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        tmp.write(audio_response.content)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"❌ Audio download error: {e}")
        return None


def transcribe_audio(audio_path):
    """Transcribe audio using OpenAI Whisper — supports English, Arabic, Malayalam."""
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        os.unlink(audio_path)  # Clean up temp file
        return transcript.text
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return None


# ── MESSAGE HELPERS ───────────────────────────────────────────

def get_ai_response(user_id, user_message):
    """Get Claude AI response with conversation history."""
    if user_id not in conversations:
        conversations[user_id] = []

    # Add user message to history
    conversations[user_id].append({"role": "user", "content": user_message})

    # Keep last 20 messages only
    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=conversations[user_id]
        )
        reply = response.content[0].text.strip()

        # Add assistant reply to history
        conversations[user_id].append({"role": "assistant", "content": reply})

        return reply
    except Exception as e:
        print(f"Claude API error: {e}")
        return "Sorry, I'm having a small technical issue. Please try again in a moment! 🙏"


def send_whatsapp(to, message):
    """Send WhatsApp message."""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    r = requests.post(url, headers=headers, json=payload)
    return r.status_code


def send_instagram_reply(recipient_id, message):
    """Send Instagram DM reply."""
    url = f"https://graph.facebook.com/v18.0/me/messages"
    headers = {"Authorization": f"Bearer {INSTAGRAM_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message}
    }
    r = requests.post(url, headers=headers, json=payload)
    return r.status_code


def notify_owner(customer_id, customer_message, platform):
    """Notify owner on WhatsApp when escalation is needed."""
    alert = (
        f"⚠️ TUXWOOD CHATBOT ESCALATION\n\n"
        f"Platform: {platform}\n"
        f"Customer ID: {customer_id}\n"
        f"Message: {customer_message}\n\n"
        f"Please reply to this customer directly."
    )
    send_whatsapp(OWNER_WHATSAPP, alert)
    send_whatsapp(OWNER_WHATSAPP_2, alert)


# ── WEBHOOK ROUTES ────────────────────────────────────────────

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Meta webhook verification."""
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        print("✅ Webhook verified!")
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Handle incoming WhatsApp & Instagram messages."""
    data = request.get_json()
    print(f"\n📨 Incoming webhook: {json.dumps(data, indent=2)[:500]}")

    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        # ── WhatsApp Message ──────────────────────────────────
        if "messages" in value:
            message = value["messages"][0]
            from_number = message.get("from")
            msg_type    = message.get("type")

            user_text = None

            # ── Text message ─────────────────────────────
            if msg_type == "text":
                user_text = message["text"]["body"]
                print(f"💬 WhatsApp from {from_number}: {user_text}")

            # ── Voice note ───────────────────────────────
            elif msg_type in ["audio", "voice"]:
                media_id = message.get("audio", message.get("voice", {})).get("id")
                print(f"🎤 Voice note from {from_number} — transcribing...")
                if media_id and OPENAI_API_KEY != "PASTE_YOUR_OPENAI_API_KEY_HERE":
                    audio_path = download_whatsapp_audio(media_id)
                    if audio_path:
                        user_text = transcribe_audio(audio_path)
                        if user_text:
                            print(f"📝 Transcribed: {user_text}")
                            # Let customer know we heard them
                            send_whatsapp(from_number, "🎤 Got your voice note!")
                        else:
                            send_whatsapp(from_number, "Sorry, I couldn't hear that clearly. Could you type your message? 🙏")
                    else:
                        send_whatsapp(from_number, "Sorry, I had trouble with your voice note. Could you type it? 🙏")
                else:
                    send_whatsapp(from_number, "Sorry, voice notes aren't set up yet. Please type your message 🙏")

            # ── Catalogue request keywords ────────────────
            catalogue_keywords = ["catalogue", "catalog", "catalog", "products", "all perfumes",
                                  "product list", "كتالوج", "منتجات", "കാറ്റലോഗ്", "പ്രൊഡക്ട്"]

            if user_text:
                # Check for catalogue request
                if any(k in user_text.lower() for k in catalogue_keywords):
                    send_whatsapp(from_number,
                        "Here's our full Tuxwood Perfumes catalogue 🌿\n\n"
                        "https://drive.google.com/file/d/1fkJ2UWe_UY0ctS9W6_HNNCzQl2zYbv8F/view?usp=sharing\n\n"
                        "Take your time browsing — let me know if anything catches your eye!"
                    )
                    return jsonify({"status": "ok"}), 200

                # Get AI response
                reply = get_ai_response(f"wa_{from_number}", user_text)

                # Check if complaint — notify owner immediately
                complaint_keywords = ["not received", "didn't receive", "where is my order",
                                      "delivery problem", "wrong item", "complaint", "refund",
                                      "not delivered", "لم يصل", "شكوى", "مشكلة", "തിരികെ",
                                      "കിട്ടിയില്ല", "delivery status", "track", "tracking"]
                if any(k in user_text.lower() for k in complaint_keywords):
                    notify_owner(from_number, f"⚠️ COMPLAINT: {user_text}", "WhatsApp")

                # Check if escalation needed
                escalate_keywords = ["connect me", "speak to human", "real person", "manager",
                                     "call me", "i need help", "not helpful", "تواصل", "مدير",
                                     "മനുഷ്യൻ", "ആളെ വിളിക്കൂ"]
                if any(k in user_text.lower() for k in escalate_keywords):
                    notify_owner(from_number, user_text, "WhatsApp")

                # Send reply
                send_whatsapp(from_number, reply)
                print(f"✅ Replied to {from_number}")

        # ── Instagram Message ─────────────────────────────────
        elif "messaging" in entry:
            messaging = entry["messaging"][0]
            sender_id  = messaging["sender"]["id"]
            msg_text   = messaging.get("message", {}).get("text", "")

            if msg_text:
                print(f"💬 Instagram from {sender_id}: {msg_text}")

                # Get AI response
                reply = get_ai_response(f"ig_{sender_id}", msg_text)

                # Check if escalation needed
                escalate_keywords = ["connect me", "speak to human", "real person",
                                     "manager", "call me", "تواصل", "مدير"]
                if any(k in msg_text.lower() for k in escalate_keywords):
                    notify_owner(sender_id, msg_text, "Instagram")

                # Send Instagram reply
                send_instagram_reply(sender_id, reply)
                print(f"✅ Replied to Instagram {sender_id}")

    except Exception as e:
        print(f"❌ Error processing webhook: {e}")

    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "Tuxwood Chatbot is running! 🌿", "time": datetime.now().isoformat()})


# ── MAIN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  TUXWOOD PERFUMES — AI Sales Chatbot")
    print("  Platforms: WhatsApp + Instagram")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("\n📋 SETUP CHECKLIST:")
    print("  1. ✅ Script running on port 5000")
    print("  2. ⏳ Run ngrok: ngrok http 5000")
    print("  3. ⏳ Set webhook URL in Meta Business Manager:")
    print("     https://YOUR-NGROK-URL/webhook")
    print(f"  4. ⏳ Verify Token: {WEBHOOK_VERIFY_TOKEN}")
    print("\n🌐 Health check: http://localhost:5000/health")
    print("=" * 60)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
