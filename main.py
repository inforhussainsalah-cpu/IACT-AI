import os
import base64
import requests
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.responses import HTMLResponse

app = FastAPI()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

EVIDENCE_MAP = {"E0": 0, "E1": 1, "E2": 2, "E3": 3}
PERMISSION_CLAIM_MAP = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}


def build_full_prompt(prompt: str, sender_info: str = "") -> str:
    clean_prompt = prompt.strip()
    clean_info = sender_info.strip()

    base_instruction = (
        "ތިބާއަކީ IACT-AI (އަދި އަލްދިގްރަމް ފަދަ އަމިއްލަ އޭއައި އެސިސްޓެންޓް) ސިސްޓަމެވެ. "
        "ސުވާލުކުރާ ފަރާތަށް ސާފު، ފުރިހަމަ އަދި ރަސްމީ ދިވެހި ބަހުން/އިނގިރޭސި ބަހުން ޖަވާބުދޭށެވެ. "
        "އެއްވެސް ސިޓީއެއް ނުވަތަ ލިޔުމެއް ލިޔާއިރު ތިރީގައި ދީފައިވާ ފޮނުވާ ފަރާތުގެ މަޢުލޫމާތު ބޭނުންކުރާށެވެ."
    )

    if clean_info:
        return f"{base_instruction}\n\n[ފޮނުވާ ފަރާތުގެ މަޢުލޫމާތު]:\n{clean_info}\n\n[މައިގަނޑު ސުވާލު / ކޮމާންޑް]:\n{clean_prompt}"
    return f"{base_instruction}\n\n[މައިގަނޑު ސުވާލު / ކޮމާންޑް]:\n{clean_prompt}"


def call_gemini(full_prompt: str, file_bytes: bytes = None, mime_type: str = None):
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY ސެޓްކުރެވިފައެއް ނެތެވެ."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    parts = [{"text": full_prompt}]

    if file_bytes and mime_type:
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": encoded
            }
        })

    payload = {"contents": [{"parts": parts}]}

    try:
        res = requests.post(url, json=payload, timeout=45)
        data = res.json()
        if res.status_code == 200 and "candidates" in data:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text, None
        return None, f"Gemini Error ({res.status_code}): {data.get('error', {}).get('message', 'Unknown error')}"
    except Exception as e:
        return None, f"Gemini Exception: {str(e)}"


def call_groq(full_prompt: str):
    if not GROQ_API_KEY:
        return None, "GROQ_API_KEY ސެޓްކުރެވިފައެއް ނެތެވެ."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": 0.4
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        data = res.json()
        if res.status_code == 200 and "choices" in data:
            return data["choices"][0]["message"]["content"], None
        return None, f"Groq Error ({res.status_code}): {data.get('error', {}).get('message', 'Unknown error')}"
    except Exception as e:
        return None, f"Groq Exception: {str(e)}"


@app.get("/", response_class=HTMLResponse)
def home():
    return render_page()


@app.post("/run", response_class=HTMLResponse)
async def run_iact(
    prompt: str = Form(""),
    sender_info: str = Form(""),
    provider: str = Form("auto"),
    evidence: str = Form("E0"),
    permission: str = Form("L0"),
    upload_file: UploadFile = File(None)
):
    ev_rank = EVIDENCE_MAP.get(evidence, 0)
    perm_rank = PERMISSION_CLAIM_MAP.get(permission, 0)

    if perm_rank > ev_rank:
        return render_page(
            prompt=prompt,
            sender_info=sender_info,
            provider=provider,
            evidence=evidence,
            permission=permission,
            output=f"⚠️ ހުއްދަ މަނާކުރެވިއްޖެ: {permission} ހިންގުމަށް މަދުވެގެން {permission.replace('L', 'E')} ފެންވަރުގެ ހެކި ބޭނުންވެއެވެ.",
            status="BLOCKED"
        )

    file_bytes = None
    mime_type = None
    file_note = ""

    if upload_file and upload_file.filename:
        file_bytes = await upload_file.read()
        mime_type = upload_file.content_type or "application/octet-stream"
        file_note = f"\n📎 އަޕްލޯޑްކުރެވުނު ފައިލް: {upload_file.filename}"

    if not prompt.strip() and not file_bytes:
        return render_page(
            prompt=prompt,
            sender_info=sender_info,
            provider=provider,
            evidence=evidence,
            permission=permission,
            output="⚠️ ސުވާލެއް ލިޔުއްވާ، އަޑުން ވާހަކަދައްކަވާ، ނުވަތަ ފޮޓޯއެއް/PDF އެއް އަޕްލޯޑްކުރައްވާށެވެ.",
            status="WARNING"
        )

    effective_prompt = prompt.strip() if prompt.strip() else "މި ފައިލްގައިވާ މަޢުލޫމާތު ތަފްޞީލުކޮށް ދިވެހި ބަހުން ކިޔައިދީ، މުހިންމު ނުކުތާތައް ފާހަގަކޮށްދޭށެވެ."
    full_prompt = build_full_prompt(effective_prompt, sender_info)

    ai_text = None
    engine_used = "Error"

    if provider == "groq":
        if file_bytes:
            ai_text = "⚠️ Groq (Llama-3.3) އިން ސީދާ ފައިލް/ފޮޓޯ ކިޔުމުގެ ބަދަލުގައި ލިޔުން/ސުވާލު ބޭނުންކުރައްވާ، ނުވަތަ Gemini ޚިޔާރުކުރައްވާށެވެ."
            engine_used = "Groq Llama-3.3"
        else:
            groq_text, groq_err = call_groq(full_prompt)
            if groq_text:
                ai_text = groq_text
                engine_used = "Groq Llama-3.3"
            else:
                ai_text = f"❌ Groq މައްސަލަ: {groq_err}"
                engine_used = "Error"

    elif provider == "gemini":
        gem_text, gem_err = call_gemini(full_prompt, file_bytes, mime_type)
        if gem_text:
            ai_text = gem_text
            engine_used = "Gemini 2.5 Flash"
        else:
            ai_text = f"❌ Gemini މައްސަލަ: {gem_err}"
            engine_used = "Error"

    else:  # auto (Gemini first, Groq backup for text)
        gem_text, gem_err = call_gemini(full_prompt, file_bytes, mime_type)
        if gem_text:
            ai_text = gem_text
            engine_used = "Gemini 2.5 Flash"
        elif file_bytes:
            ai_text = f"❌ ފައިލް ކިޔުމުގައި މައްސަލައެއް ދިމާވެއްޖެ: {gem_err}"
            engine_used = "Error"
        else:
            groq_text, groq_err = call_groq(full_prompt)
            if groq_text:
                ai_text = groq_text
                engine_used = "Groq Llama-3.3 (Backup)"
            else:
                ai_text = f"❌ ސިސްޓަމް މައްސަލަ:\nGemini: {gem_err}\nGroq: {groq_err}"
                engine_used = "Error"

    header_info = f"✅ ސްޓޭޓަސް: ALLOWED ({evidence} / {permission}) | އިންޖީނު: {engine_used}{file_note}\n" + ("—" * 32) + "\n\n"
    return render_page(
        prompt=prompt,
        sender_info=sender_info,
        provider=provider,
        evidence=evidence,
        permission=permission,
        output=header_info + ai_text,
        raw_reply=ai_text,
        status="SUCCESS"
    )


def render_page(
    prompt: str = "",
    sender_info: str = "",
    provider: str = "auto",
    evidence: str = "E0",
    permission: str = "L0",
    output: str = "",
    raw_reply: str = "",
    status: str = ""
):
    safe_prompt = prompt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_sender = sender_info.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_output = output.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_raw = raw_reply.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return f"""<!DOCTYPE html>
<html lang="dv" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IACT-AI + Gemini &amp; Groq (ދިވެހި އިންޓެލިޖެންސް)</title>
    <style>
        body {{
            background-color: #0b1120;
            color: #f8fafc;
            font-family: 'Faruma', 'MV Waheed', system-ui, -apple-system, sans-serif;
            margin: 0;
            padding: 16px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            width: 100%;
            max-width: 680px;
            background: #131c31;
            border: 1px solid #263554;
            border-radius: 18px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.45);
        }}
        h1 {{
            text-align: center;
            font-size: 1.4rem;
            margin-top: 0;
            color: #ffffff;
        }}
        label {{
            display: block;
            margin-top: 14px;
            margin-bottom: 6px;
            font-weight: bold;
            color: #cbd5e1;
            font-size: 0.95rem;
        }}
        textarea, select, input[type="file"], input[type="text"], input[type="email"] {{
            width: 100%;
            box-sizing: border-box;
            background: #0b1120;
            color: #f8fafc;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 12px;
            font-size: 1rem;
            font-family: inherit;
        }}
        textarea:focus, select:focus, input:focus {{
            outline: none;
            border-color: #3b82f6;
        }}
        .voice-bar {{
            display: flex;
            gap: 8px;
            margin-top: 10px;
            flex-wrap: wrap;
        }}
        .btn {{
            border: none;
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 0.98rem;
            font-weight: bold;
            cursor: pointer;
            font-family: inherit;
            transition: 0.2s;
            text-align: center;
            text-decoration: none;
            display: inline-block;
        }}
        .btn-primary {{
            width: 100%;
            background: #1d63ed;
            color: #ffffff;
            margin-top: 18px;
            font-size: 1.08rem;
            padding: 14px;
        }}
        .btn-primary:hover {{ background: #1550c6; }}
        .btn-voice {{
            flex: 1;
            background: #0f766e;
            color: #ffffff;
        }}
        .btn-voice.recording {{
            background: #dc2626;
            animation: pulse 1.2s infinite;
        }}
        .btn-clear {{
            background: #334155;
            color: #e2e8f0;
        }}
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.65; }}
            100% {{ opacity: 1; }}
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        @media (max-width: 500px) {{
            .grid-2 {{ grid-template-columns: 1fr; }}
        }}
        .output-box {{
            margin-top: 20px;
            background: #080d1a;
            border: 1px solid #2b3d63;
            border-radius: 14px;
            padding: 16px;
            white-space: pre-wrap;
            line-height: 1.75;
            font-size: 1rem;
        }}
        .send-panel {{
            margin-top: 16px;
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 14px;
            padding: 14px;
        }}
        .send-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-top: 10px;
        }}
        .btn-wa {{ background: #16a34a; color: white; }}
        .btn-vb {{ background: #7c3aed; color: white; }}
        .btn-tg {{ background: #0284c7; color: white; }}
        .btn-em {{ background: #ea580c; color: white; }}
        .btn-cp {{ background: #475569; color: white; grid-column: span 2; }}
        .status-msg {{
            font-size: 0.85rem;
            color: #38bdf8;
            margin-top: 6px;
        }}
        details {{
            margin-top: 14px;
            background: #0f172a;
            border: 1px solid #263554;
            border-radius: 12px;
            padding: 10px 14px;
        }}
        summary {{
            cursor: pointer;
            font-weight: bold;
            color: #93c5fd;
        }}
    </style>
</head>
<body>
<div class="container">
    <h1>🧠 IACT-AI + Gemini &amp; Groq</h1>

    <form action="/run" method="post" enctype="multipart/form-data">
        <label for="provider">🤖 އޭއައި އިންޖީނު ޚިޔާރުކުރައްވާ:</label>
        <select id="provider" name="provider">
            <option value="auto" {"selected" if provider=="auto" else ""}>Auto (Gemini + Groq Backup)</option>
            <option value="gemini" {"selected" if provider=="gemini" else ""}>Gemini 2.5 Flash</option>
            <option value="groq" {"selected" if provider=="groq" else ""}>Groq (Llama 3.3 70B)</option>
        </select>

        <label for="prompt">ސުވާލު ނުވަތަ ދިރާސާ މައުޟޫޢު ލިޔުއްވާ:</label>
        <textarea id="prompt" name="prompt" rows="4" placeholder="މިތަނުގައި ތާނައިން ނުވަތަ އިނގިރޭސިން ލިޔުއްވާ...">{safe_prompt}</textarea>

        <div class="voice-bar">
            <button type="button" id="voiceBtn" class="btn btn-voice" onclick="toggleVoice()">🎙️ އަޑު ރެކޯޑްކުރަން ފަށާ</button>
            <button type="button" class="btn btn-clear" onclick="document.getElementById('prompt').value=''">🗑️ ފޮހެލާ</button>
        </div>
        <div id="voiceStatus" class="status-msg"></div>

        <label for="upload_file">📎 ފޮޓޯ، ސްކްރީންޝޮޓް، ނުވަތަ PDF އަޕްލޯޑްކުރައްވާ:</label>
        <input type="file" id="upload_file" name="upload_file" accept="image/*,.pdf">

        <details>
            <summary>👤 ފޮނުވާ ފަރާތުގެ މަޢުލޫމާތު (ފޯނުގައި ސޭވްވާނެ)</summary>
            <label for="sender_info">ނަން، އެޑްރެސް، އައިޑީ/ޕާސްޕޯޓް، ފޯނު، އީމެއިލް، ވެބްސައިޓް:</label>
            <textarea id="sender_info" name="sender_info" rows="3" oninput="saveSenderInfo()" placeholder="މިސާލު: ޙުސައިން ޞަލާޙް، ގ. ޗާންދު، މާލެ | ފޯނު: 7570082 | އީމެއިލް: ...">{safe_sender}</textarea>
        </details>

        <div class="grid-2">
            <div>
                <label for="evidence">ހެކީގެ ފެންވަރު (Evidence Level):</label>
                <select id="evidence" name="evidence">
                    <option value="E0" {"selected" if evidence=="E0" else ""}>E0 = ޚިޔާލީ ހުށަހެޅުން (Conceptual)</option>
                    <option value="E1" {"selected" if evidence=="E1" else ""}>E1 = ތަޖުރިބާ / އޮބްޒަވޭޝަން (Observed)</option>
                    <option value="E2" {"selected" if evidence=="E2" else ""}>E2 = ސާބިތު ހެކި (Verified)</option>
                    <option value="E3" {"selected" if evidence=="E3" else ""}>E3 = ކަށަވަރު ޑޭޓާ (Confirmed)</option>
                </select>
            </div>
            <div>
                <label for="permission">ހުއްދައިގެ ފެންވަރު (Permission Level):</label>
                <select id="permission" name="permission">
                    <option value="L0" {"selected" if permission=="L0" else ""}>L0 = READ (ކިޔުން)</option>
                    <option value="L1" {"selected" if permission=="L1" else ""}>L1 = DRAFT (ޑްރާފްޓްކުރުން)</option>
                    <option value="L2" {"selected" if permission=="L2" else ""}>L2 = EXECUTE (ހިންގުން)</option>
                    <option value="L3" {"selected" if permission=="L3" else ""}>L3 = AUTONOMOUS (އަމިއްލައަށް)</option>
                </select>
            </div>
        </div>

        <button type="submit" class="btn btn-primary">🚀 IACT-AI ހިންގާލާ</button>
    </form>

    {f'''
    <div class="output-box" id="outputBox">{safe_output}</div>
    <textarea id="rawReply" style="display:none;">{safe_raw}</textarea>

    <div class="send-panel">
        <label style="margin-top:0;">📤 ޖަވާބު / ސިޓީ ވަގުތުން ފޮނުވާލާ:</label>
        <div class="grid-2">
            <input type="email" id="targetEmail" placeholder="ފޮނުވާ އީމެއިލް އެޑްރެސް...">
            <input type="text" id="targetPhone" placeholder="ފޯނު ނަންބަރު (މިސާލު: 9607570082)">
        </div>
        <div class="send-grid">
            <button type="button" class="btn btn-wa" onclick="sendWhatsApp()">💬 WhatsApp</button>
            <button type="button" class="btn btn-vb" onclick="sendViber()">🟣 Viber</button>
            <button type="button" class="btn btn-tg" onclick="sendTelegram()">✈️ Telegram</button>
            <button type="button" class="btn btn-em" onclick="sendEmail()">✉️ Email</button>
            <button type="button" class="btn btn-cp" onclick="copyText()">📋 ލިޔުން ކޮޕީކުރޭ</button>
        </div>
    </div>
    ''' if output else ''}
</div>

<script>
    window.onload = function() {{
        const savedInfo = localStorage.getItem('iact_sender_info');
        const infoBox = document.getElementById('sender_info');
        if (savedInfo && !infoBox.value.trim()) {{
            infoBox.value = savedInfo;
        }}
    }};

    function saveSenderInfo() {{
        const val = document.getElementById('sender_info').value;
        localStorage.setItem('iact_sender_info', val);
    }}

    let recognition = null;
    let isRecording = false;

    function toggleVoice() {{
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const statusEl = document.getElementById('voiceStatus');
        const btn = document.getElementById('voiceBtn');

        if (!SpeechRecognition) {{
            statusEl.innerText = "⚠️ މި ބްރައުޒާއިން ސީދާ ވޮއިސް ޓައިޕިންގ ސަޕޯޓެއް ނުކުރެއެވެ. ކީބޯޑުގެ މައިކް ބޭނުންކުރައްވާށެވެ.";
            return;
        }}

        if (isRecording && recognition) {{
            recognition.stop();
            return;
        }}

        recognition = new SpeechRecognition();
        recognition.lang = 'dv-MV';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = function() {{
            isRecording = true;
            btn.classList.add('recording');
            btn.innerText = "⏹️ އަޑު ރެކޯޑްވަމުންދޭ... (ހުއްޓާލަން ފިތާ)";
            statusEl.innerText = "🎙️ ވާހަކަދައްކަވާ...";
        }};

        recognition.onresult = function(event) {{
            const transcript = event.results[0][0].transcript;
            const promptBox = document.getElementById('prompt');
            promptBox.value = (promptBox.value + " " + transcript).trim();
            statusEl.innerText = "✅ އަޑު ލިޔުމަށް ބަދަލުކުރެވިއްޖެ!";
        }};

        recognition.onerror = function(event) {{
            statusEl.innerText = "⚠️ މައިކްރޯފޯން މައްސަލައެއް: " + event.error + " (ކީބޯޑުގެ މައިކް ބޭނުންކުރެވޭނެ)";
        }};

        recognition.onend = function() {{
            isRecording = false;
            btn.classList.remove('recording');
            btn.innerText = "🎙️ އަޑު ރެކޯޑްކުރަން ފަށާ";
        }};

        recognition.start();
    }}

    function getReplyText() {{
        const raw = document.getElementById('rawReply');
        if (raw && raw.value.trim()) return raw.value.trim();
        const box = document.getElementById('outputBox');
        return box ? box.innerText.trim() : "";
    }}

    function sendWhatsApp() {{
        const text = encodeURIComponent(getReplyText());
        const phone = document.getElementById('targetPhone').value.replace(/[^0-9]/g, '');
        const url = phone ? `https://wa.me/${{phone}}?text=${{text}}` : `https://wa.me/?text=${{text}}`;
        window.open(url, '_blank');
    }}

    function sendViber() {{
        const text = encodeURIComponent(getReplyText());
        window.open(`viber://forward?text=${{text}}`, '_blank');
    }}

    function sendTelegram() {{
        const text = encodeURIComponent(getReplyText());
        window.open(`https://t.me/share/url?url=&text=${{text}}`, '_blank');
    }}

    function sendEmail() {{
        const text = encodeURIComponent(getReplyText());
        const email = document.getElementById('targetEmail').value.trim();
        const subject = encodeURIComponent("IACT-AI ލިޔުން / ސިޓީ");
        window.location.href = `mailto:${{email}}?subject=${{subject}}&body=${{text}}`;
    }}

    function copyText() {{
        const text = getReplyText();
        navigator.clipboard.writeText(text).then(() => {{
            alert("✅ ލިޔުން ކޮޕީކުރެވިއްޖެ!");
        }});
    }}
</script>
</body>
</html>
"""
