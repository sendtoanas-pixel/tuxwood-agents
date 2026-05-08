"""
TUXWOOD PERFUMES — AI Sales Chatbot (Ozani)
Dashboard available at /dashboard
"""

from flask import Flask, request, jsonify, render_template_string
import requests, json, os, tempfile
from datetime import datetime
# anthropic SDK replaced with direct HTTP

WHATSAPP_TOKEN      = "EAAXY3FLEH2kBRFQInkSZC7DnYkgRB1CmkFRmZBbhztgtGy8BLzapcLJgreFQhUWOezUL2tC6m60kqDNjRo4xyLNhvh1e0QwGkycjhp2IyAw1trm7V4afaNvxhjUyZAp2YihXJvdLjDMaGjL6AkJZCBOu4LCAHaGY2k1ZAXpIIqygaRVQvB9uGpZBoZAr2W69QZDZD"
PHONE_NUMBER_ID     = "1127995510386994"
ANTHROPIC_API_KEY   = "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"
OPENAI_API_KEY      = "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"
WEBHOOK_VERIFY_TOKEN = "tuxwood_webhook_2026"
OWNER_WHATSAPP      = "971528903429"
OWNER_WHATSAPP_2    = "971569394846"
INSTAGRAM_TOKEN     = WHATSAPP_TOKEN
CHAT_LOG_FILE       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ozani_chat_log.json")

app    = Flask(__name__)
# client removed - using direct HTTP requests
conversations = {}
chat_log = {}

def load_chat_log():
    global chat_log
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                chat_log = json.load(f)
        except Exception:
            chat_log = {}

def save_chat_log():
    try:
        with open(CHAT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(chat_log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Could not save chat log: {e}")

def log_message(user_id, role, text, platform="WhatsApp", phone=None):
    if user_id not in chat_log:
        chat_log[user_id] = {"phone": phone or user_id, "platform": platform, "messages": [], "last_active": ""}
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chat_log[user_id]["messages"].append({"role": role, "text": text, "time": ts})
    chat_log[user_id]["last_active"] = ts
    if len(chat_log[user_id]["messages"]) > 200:
        chat_log[user_id]["messages"] = chat_log[user_id]["messages"][-200:]
    save_chat_log()

load_chat_log()

KNOWLEDGE_BASE = """
TUXWOOD PERFUMES CATALOGUE

Store: Shabiya 9, Abu Dhabi. Delivery: All UAE next day. Free for combos, AED 15 single. COD + Bank Transfer.

EXOTIC 65ml AED 89: Mountain Fresh, Ligero Tobacco, Oud Al Dahab, Royal Velvet, Green Desert, Holysmells, Rosy Magic, Sulthan, Loyalty, Enigma, Manly, Ockacho, Sage.
PREMIUM 50ml AED 69: Vintage, Hathun, Kosovo, Peyami, Force, Queen, Alpha, Zawji, Ice, Fikr, Ember, Host.
ELIXIR 50ml AED 49: Holofire, Goodness, Desire, Flair, Hope, Justice, Splendid, Evoke, Richness, Timeless, Midnight, Softness, Rainy, Immense, Florist.

Fast sellers: Mountain Fresh, Ligero Tobacco, Royal Velvet, Holysmells, Rosy Magic, Sulthan, Ockacho, Force.
India delivery: +91 7907090223. Wholesale: +971528903429.
Catalogue: https://drive.google.com/file/d/1fkJ2UWe_UY0ctS9W6_HNNCzQl2zYbv8F/view?usp=sharing
Location: https://maps.app.goo.gl/Dtn2kW42GdKsPd887
Review: https://g.page/r/CWD2JXuNUfFNEAE/review
"""

SYSTEM_PROMPT = """You are Ozani, fragrance advisor for Tuxwood Perfumes.
RULE: Talk less, understand more, guide slowly. Max 3-4 lines per reply.
- Human tone, not bot. Ask ONE question, wait for reply.
- Reply in customer language (Arabic/English/Malayalam).
- If asked if human: "I am Ozani from Tuxwood Perfumes"
OPENING: "Welcome to Tuxwood Perfumes! I am Ozani. Are you shopping for yourself or as a gift?"
ORDER: Collect Name, Number, Address, Perfume, Quantity, Payment one at a time.
DELIVERY: 1 item AED 15. 2+ items FREE.
COMPLAINTS/TRACKING/WHOLESALE: Refer to +971528903429.
""" + KNOWLEDGE_BASE

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ozani Monitor</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:sans-serif;background:#0f0f0f;color:#ddd;height:100vh;display:flex;flex-direction:column}
.top{background:#1a1a1a;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2a2a2a}
.top h1{font-size:15px;color:#c9a84c}
.dot{width:8px;height:8px;background:#4caf50;border-radius:50%;display:inline-block;margin-right:5px;animation:p 1.5s infinite}
@keyframes p{0%,100%{opacity:1}50%{opacity:.3}}
.stats{background:#141414;padding:8px 16px;display:flex;gap:20px;border-bottom:1px solid #222;font-size:12px}
.stat b{color:#c9a84c;font-size:18px;margin-right:3px}
.main{display:flex;flex:1;overflow:hidden}
.sb{width:270px;border-right:1px solid #222;overflow-y:auto;background:#111;flex-shrink:0}
.si{padding:11px 12px;border-bottom:1px solid #1a1a1a;cursor:pointer}
.si:hover{background:#1a1a1a}.si.active{background:#1e1a0e;border-left:3px solid #c9a84c}
.si .ph{font-size:13px;font-weight:600;color:#ddd;display:flex;justify-content:space-between;align-items:center}
.si .pr{font-size:11px;color:#555;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;margin:3px 0}
.si .tm{font-size:10px;color:#444}
.badge{font-size:9px;padding:2px 5px;border-radius:8px}
.wa{background:#1a3a1a;color:#4caf50}.ig{background:#2a1a2a;color:#e040fb}
.cnt{background:#c9a84c;color:#000;font-size:10px;font-weight:700;padding:1px 5px;border-radius:8px}
.cp{flex:1;display:flex;flex-direction:column;overflow:hidden}
.ch{padding:11px 16px;border-bottom:1px solid #222;background:#141414}
.ch .title{font-size:14px;font-weight:600}
.ch .info{font-size:11px;color:#555;margin-top:2px}
.msgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:9px}
.msg{max-width:72%}.msg.c{align-self:flex-start}.msg.o{align-self:flex-end}
.lbl{font-size:10px;color:#444;margin-bottom:2px}.msg.o .lbl{text-align:right}
.bbl{padding:9px 12px;border-radius:12px;font-size:12px;line-height:1.5;word-wrap:break-word;white-space:pre-wrap}
.msg.c .bbl{background:#1e1e1e;border-radius:12px 12px 12px 2px}
.msg.o .bbl{background:#2a2010;color:#e8d5a0;border:1px solid #3a3010;border-radius:12px 12px 2px 12px}
.tm2{font-size:9px;color:#333;margin-top:2px}.msg.o .tm2{text-align:right}
.empty{display:flex;align-items:center;justify-content:center;flex:1;color:#333;flex-direction:column;gap:8px;font-size:13px}
.foot{font-size:10px;color:#333;padding:5px 14px;border-top:1px solid #1a1a1a;text-align:right}
::-webkit-scrollbar{width:3px}::-webkit-scrollbar-thumb{background:#2a2a2a}
</style>
</head>
<body>
<div class="top">
  <h1>🌿 Ozani — Live Chat Monitor</h1>
  <div><span class="dot"></span><span style="font-size:11px;color:#4caf50">LIVE</span></div>
</div>
<div class="stats">
  <div><b id="tc">0</b>Customers</div>
  <div><b id="tm">0</b>Messages</div>
  <div><b id="ta">0</b>Active Today</div>
</div>
<div class="main">
  <div class="sb" id="sb"><div class="empty" style="padding:30px">No chats yet 🌿</div></div>
  <div class="cp" id="cp"><div class="empty"><div style="font-size:34px">💬</div>Select a conversation</div></div>
</div>
<div class="foot" id="ft">Auto-refreshing every 10s</div>
<script>
var chats={},active=null,today=new Date().toISOString().slice(0,10);
function ago(t){if(!t)return'';var d=Math.floor((Date.now()-new Date(t.replace(' ','T')))/1000);return d<60?'just now':d<3600?Math.floor(d/60)+'m ago':d<86400?Math.floor(d/3600)+'h ago':Math.floor(d/86400)+'d ago';}
function ph(p){return String(p||'').replace('wa_','').replace('ig_','').replace(/^971/,'+971')||'Unknown';}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function renderSb(){
  var sb=document.getElementById('sb');
  var users=Object.entries(chats).sort(function(a,b){return(b[1].last_active||'').localeCompare(a[1].last_active||'');});
  if(!users.length){sb.innerHTML='<div class="empty" style="padding:30px">No chats yet</div>';return;}
  sb.innerHTML=users.map(function(e){
    var uid=e[0],d=e[1],m=d.messages||[],last=m.length?m[m.length-1]:{};
    var pr=last.text?(last.text.length>38?last.text.slice(0,38)+'...':last.text):'';
    var pl=d.platform||'WhatsApp';
    return '<div class="si'+(uid===active?' active':'')+'" onclick="sel(\''+uid+'\')">'
      +'<div class="ph"><span>'+ph(d.phone||uid)+'</span><div><span class="badge '+(pl==='Instagram'?'ig':'wa')+'">'+pl+'</span> <span class="cnt">'+m.length+'</span></div></div>'
      +'<div class="pr">'+esc(pr)+'</div><div class="tm">'+ago(d.last_active)+'</div></div>';
  }).join('');
}
function renderChat(uid){
  var d=chats[uid];if(!d)return;
  var m=d.messages||[],pl=d.platform||'WhatsApp';
  document.getElementById('cp').innerHTML=
    '<div class="ch"><div class="title">'+ph(d.phone||uid)+'</div><div class="info">'+pl+' &middot; '+m.length+' messages &middot; '+ago(d.last_active)+'</div></div>'
    +'<div class="msgs" id="mc">'+m.map(function(msg){
      var c=msg.role==='customer';
      return '<div class="msg '+(c?'c':'o')+'"><div class="lbl">'+(c?'👤 Customer':'🌿 Ozani')+'</div><div class="bbl">'+esc(msg.text)+'</div><div class="tm2">'+(msg.time||'')+'</div></div>';
    }).join('')+'</div>';
  var mc=document.getElementById('mc');if(mc)mc.scrollTop=mc.scrollHeight;
}
function sel(uid){active=uid;renderSb();renderChat(uid);}
function updateStats(){
  var u=Object.values(chats);
  document.getElementById('tc').textContent=u.length;
  document.getElementById('tm').textContent=u.reduce(function(s,x){return s+(x.messages||[]).length;},0);
  document.getElementById('ta').textContent=u.filter(function(x){return(x.last_active||'').startsWith(today);}).length;
}
function doFetch(){
  fetch('/api/chats').then(function(r){return r.json();}).then(function(d){
    chats=d;renderSb();updateStats();
    if(active&&chats[active])renderChat(active);
    document.getElementById('ft').textContent='Updated: '+new Date().toLocaleTimeString()+' | Auto-refreshing every 10s';
  }).catch(function(){document.getElementById('ft').textContent='Connection error — retrying...';});
}
doFetch();setInterval(doFetch,10000);
</script>
</body>
</html>"""

def download_whatsapp_audio(media_id):
    try:
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        r = requests.get(f"https://graph.facebook.com/v18.0/{media_id}", headers=headers)
        url = r.json().get("url")
        if not url: return None
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        tmp.write(requests.get(url, headers=headers).content); tmp.close()
        return tmp.name
    except Exception as e:
        print(f"Audio error: {e}"); return None

def transcribe_audio(path):
    try:
        from openai import OpenAI
        c = OpenAI(api_key=OPENAI_API_KEY)
        with open(path, "rb") as f:
            t = c.audio.transcriptions.create(model="whisper-1", file=f)
        os.unlink(path); return t.text
    except Exception as e:
        print(f"Transcribe error: {e}"); return None

def get_ai_response(user_id, user_message, platform="WhatsApp", phone=None):
    if user_id not in conversations: conversations[user_id] = []
    log_message(user_id, "customer", user_message, platform=platform, phone=phone or user_id)
    conversations[user_id].append({"role": "user", "content": user_message})
    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]
    try:
        api_resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 600,
                "system": SYSTEM_PROMPT,
                "messages": conversations[user_id]
            },
            timeout=30
        )
        api_resp.raise_for_status()
        reply = api_resp.json()["content"][0]["text"].strip()
        conversations[user_id].append({"role": "assistant", "content": reply})
        log_message(user_id, "ozani", reply, platform=platform, phone=phone or user_id)
        return reply
    except Exception as e:
        print(f"Claude error: {e}")
        return "Sorry, small technical issue. Please try again! 🙏"

def send_whatsapp(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    return requests.post(url, headers=headers, json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}).status_code

def send_instagram_reply(recipient_id, message):
    headers = {"Authorization": f"Bearer {INSTAGRAM_TOKEN}", "Content-Type": "application/json"}
    return requests.post("https://graph.facebook.com/v18.0/me/messages", headers=headers, json={"recipient": {"id": recipient_id}, "message": {"text": message}}).status_code

def notify_owner(cid, msg, platform):
    alert = f"TUXWOOD ALERT\nPlatform: {platform}\nCustomer: {cid}\nMsg: {msg}\n\nPlease reply directly."
    send_whatsapp(OWNER_WHATSAPP, alert)
    send_whatsapp(OWNER_WHATSAPP_2, alert)

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == WEBHOOK_VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.get_json()
    CATALOGUE_KW = ["catalogue","catalog","products","all perfumes","product list","كتالوج","منتجات"]
    COMPLAINT_KW = ["not received","didn't receive","wrong item","complaint","refund","لم يصل","شكوى","delivery status","track"]
    ESCALATE_KW  = ["connect me","speak to human","real person","manager","call me","not helpful","تواصل","مدير"]
    try:
        entry   = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value   = changes.get("value", {})

        if "messages" in value:
            msg = value["messages"][0]
            from_number = msg.get("from")
            msg_type    = msg.get("type")
            user_text   = None

            if msg_type == "text":
                user_text = msg["text"]["body"]
            elif msg_type in ["audio", "voice"]:
                media_id = msg.get("audio", msg.get("voice", {})).get("id")
                if media_id:
                    path = download_whatsapp_audio(media_id)
                    user_text = transcribe_audio(path) if path else None
                    if user_text:
                        send_whatsapp(from_number, "Got your voice note!")
                    else:
                        send_whatsapp(from_number, "Sorry, couldn't hear. Please type? 🙏")

            if user_text:
                if any(k in user_text.lower() for k in CATALOGUE_KW):
                    reply = "Here is our full Tuxwood Perfumes catalogue:\n\nhttps://drive.google.com/file/d/1fkJ2UWe_UY0ctS9W6_HNNCzQl2zYbv8F/view?usp=sharing\n\nLet me know if anything catches your eye!"
                    log_message(f"wa_{from_number}", "customer", user_text, "WhatsApp", from_number)
                    log_message(f"wa_{from_number}", "ozani", reply, "WhatsApp", from_number)
                    send_whatsapp(from_number, reply)
                    return jsonify({"status": "ok"}), 200
                reply = get_ai_response(f"wa_{from_number}", user_text, "WhatsApp", from_number)
                if any(k in user_text.lower() for k in COMPLAINT_KW):
                    notify_owner(from_number, f"COMPLAINT: {user_text}", "WhatsApp")
                if any(k in user_text.lower() for k in ESCALATE_KW):
                    notify_owner(from_number, user_text, "WhatsApp")
                send_whatsapp(from_number, reply)

        elif "messaging" in entry:
            messaging = entry["messaging"][0]
            sender_id = messaging["sender"]["id"]
            msg_text  = messaging.get("message", {}).get("text", "")
            if msg_text:
                reply = get_ai_response(f"ig_{sender_id}", msg_text, "Instagram", sender_id)
                if any(k in msg_text.lower() for k in ESCALATE_KW):
                    notify_owner(sender_id, msg_text, "Instagram")
                send_instagram_reply(sender_id, reply)
    except Exception as e:
        print(f"Webhook error: {e}")
    return jsonify({"status": "ok"}), 200

@app.route("/dashboard")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route("/api/chats")
def api_chats():
    return jsonify(chat_log)

@app.route("/health")
def health():
    return jsonify({"status": "Ozani running", "conversations": len(chat_log)})

if __name__ == "__main__":
    print(f"Ozani started. Dashboard: http://localhost:5000/dashboard")
    app.run(host="0.0.0.0", port=5000, debug=False)
