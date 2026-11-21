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


def build_full_prompt(prompt: str, sender_info: str, has_attachment: bool = False) -> str:
    clean_prompt = prompt.strip()
    clean_info = sender_info.strip()

    base_instruction = (
        "ތިރީގައިވާ މަޢުލޫމާތަށް (އަދި އެޓޭޗްކޮށްފައިވާ ފައިލް ނުވަތަ އަޑުގެ ރެކޯޑިންގ އަށް) ބިނާކޮށް "
        "ސާފު ތާނައިން، ފުރިހަމަ އަދި ތަފްޞީލީ ޖަވާބެއް/ލިޔުމެއް ތައްޔާރުކޮށްދޭށެވެ.\n"
        "އަޑުގެ ރެކޯޑިންގ އެއް ހިމެނޭނަމަ، އެ ރެކޯޑިންގ ގައި ދައްކާފައިވާ ވާހަކައާއި ދީފައިވާ ކޮމާންޑް ދެނެގަނެ ސީދާ އެއަށް ޢަމަލުކުރާށެވެ.\n"
    )

    if clean_info:
        base_instruction += (
            "މިއީ ސިޓީއެއް ނުވަތަ ރަސްމީ ހުށަހެޅުމެއް ނަމަ، ފޮނުވާ ފަރާތުގެ މަޢުލޫމާތުގެ ގޮތުގައި "
            "ތިރީގައިވާ މަޢުލޫމާތު ސިޓީގައި ރަނގަޅަށް ހިމަނާށެވެ:\n\n"
            f"--- ފޮނުވާ ފަރާތުގެ މަޢުލޫމާތު ---\n{clean_info}\n\n"
        )

    if clean_prompt:
        base_instruction += f"--- ސުވާލު / ކޮމާންޑް / މަޢުޟޫޢު ---\n{clean_prompt}"
    elif has_attachment:
        base_instruction += "--- ކޮމާންޑް ---\nއެޓޭޗްކޮށްފައިވާ ފައިލް ނުވަތަ އަޑުގެ ރެކޯޑިންގ ގައިވާ މަޢުލޫމާތު ދެނެގަނެ، އޭގެ ތަފްޞީލާއި ބޭނުންވާ ޖަވާބު ތާނައިން ތައްޔާރުކޮށްދޭށެވެ."

    return base_instruction


def ask_gemini_multimodal(
    prompt: str,
    sender_info: str,
    file_bytes: bytes | None = None,
    file_mime: str = "",
    audio_b64: str = "",
    audio_mime: str = "audio/webm"
) -> tuple[bool, str]:
    if not GEMINI_API_KEY:
        return False, "GEMINI_API_KEY ސެޓްކުރެވިފައެއް ނުވެއެވެ."

    has_attachment = bool(file_bytes or audio_b64)
    parts = [{"text": build_full_prompt(prompt, sender_info, has_attachment)}]

    if file_bytes and file_mime:
        encoded_file = base64.b64encode(file_bytes).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": file_mime,
                "data": encoded_file
            }
        })

    if audio_b64:
        clean_audio = audio_b64.split(",")[-1] if "," in audio_b64 else audio_b64
        parts.append({
            "inline_data": {
                "mime_type": audio_mime or "audio/webm",
                "data": clean_audio
            }
        })

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": parts}]}

    try:
        res = requests.post(url, json=payload, timeout=60)
        if res.status_code == 200:
            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return True, text
        return False, f"Gemini Error ({res.status_code}): {res.text[:220]}"
    except Exception as e:
        return False, f"Gemini Connection Error: {str(e)}"


def ask_groq_text(prompt: str, sender_info: str) -> tuple[bool, str]:
    if not GROQ_API_KEY:
        return False, "GROQ_API_KEY ސެޓްކުރެވިފައެއް ނުވެއެވެ."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are IACT-AI assistant. Always reply clearly, thoroughly, and accurately in Dhivehi (Thaana script). Include sender details properly when provided."
            },
            {
                "role": "user",
                "content": build_full_prompt(prompt, sender_info, False)
            }
        ],
        "temperature": 0.5,
        "max_tokens": 4096
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=45)
        if res.status_code == 200:
            data = res.json()
            text = data["choices"][0]["message"]["content"]
            return True, text
        return False, f"Groq Error ({res.status_code}): {res.text[:200]}"
    except Exception as e:
        return False, f"Groq Connection Error: {str(e)}"


def render_page(prompt="", sender_info="", evidence="E0", permission="L0", status="", reason="", detail="", ai_output="", engine_used=""):
    result_block = ""
    if status:
        badge_color = "#16a34a" if status == "PASS" else "#d97706"
        result_block = f"""
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <span style="background:{badge_color}; color:#fff; padding:4px 12px; border-radius:6px; font-weight:bold;">{status}</span>
                <strong>ގަވަރނަންސް ނަތީޖާ ({engine_used}):</strong>
            </div>
            <p><strong>އުޞޫލު:</strong> {reason}</p>
            <p style="color:#cbd5e1;">{detail}</p>

            <div class="output-box">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <strong>AI ގެ ޖަވާބު / ސިޓީ / މަޒުމޫނު:</strong>
                    <button type="button" onclick="copyLetter()" style="width:auto; padding:6px 14px; margin:0; background:#334155; font-size:14px;">ކޮޕީކުރޭ (Copy)</button>
                </div>
                <textarea id="letterBody" rows="14" style="min-height:300px; line-height:1.9;">{ai_output}</textarea>
            </div>

            <hr style="border-color:#334155; margin:20px 0;">
            <h3 style="color:#38bdf8; margin-top:0;">1. އީމެއިލް އިން ފޮނުވާލާ (Email)</h3>
            <label>ފޮނުވަންވީ އީމެއިލް އެޑްރެސް (To):</label>
            <input type="email" id="toEmail" placeholder="example@gmail.com" dir="ltr">

            <label>ސިޓީގެ ސުރުޚީ (Subject):</label>
            <input type="text" id="emailSubject" placeholder="މިސާލަކަށް: ރަސްމީ ސިޓީ">

            <button type="button" onclick="openMailApp()" style="background:#2563eb;">Send via Email App (އީމެއިލް އެޕުން ފޮނުވާ)</button>

            <hr style="border-color:#334155; margin:22px 0;">
            <h3 style="color:#4ade80; margin-top:0;">2. WhatsApp އަދި SMS އިން ފޮނުވާލާ</h3>
            <label>ފޮނުވަންވީ ފޯނު ނަންބަރު (މިސާލަކަށް: 7570082 ނުވަތަ 9607570082):</label>
            <input type="tel" id="phoneNumber" placeholder="7XXXXXX" dir="ltr">

            <div class="btn-grid">
                <button type="button" onclick="sendWhatsApp()" style="background:#16a34a; margin-top:10px;">WhatsApp އިން ފޮނުވާ</button>
                <button type="button" onclick="sendSMS()" style="background:#0284c7; margin-top:10px;">SMS އިން ފޮނުވާ</button>
            </div>

            <hr style="border-color:#334155; margin:22px 0;">
            <h3 style="color:#c084fc; margin-top:0;">3. އެހެނިހެން އެޕްތަކަށް ފޮނުވާލާ</h3>
            <div class="btn-grid">
                <button type="button" onclick="sendViber()" style="background:#7c3aed; margin-top:8px;">Viber އިން ފޮނުވާ</button>
                <button type="button" onclick="sendTelegram()" style="background:#0ea5e9; margin-top:8px;">Telegram އިން ފޮނުވާ</button>
            </div>
            <button type="button" onclick="shareAnyApp()" style="background:#475569; margin-top:10px;">އެހެން ހުރިހާ އެޕްތަކަށް ޝެއަރ ކުރޭ (Share)</button>
        </div>

        <script>
            function copyLetter() {{
                const text = document.getElementById("letterBody").value;
                navigator.clipboard.writeText(text).then(() => {{
                    alert("ލިޔުން ކޮޕީކުރެވިއްޖެއެވެ!");
                }});
            }}

            function openMailApp() {{
                const to = document.getElementById("toEmail").value.trim();
                const subject = encodeURIComponent(document.getElementById("emailSubject").value.trim());
                const body = encodeURIComponent(document.getElementById("letterBody").value);
                window.location.href = `mailto:${{to}}?subject=${{subject}}&body=${{body}}`;
            }}

            function formatPhone() {{
                let phone = document.getElementById("phoneNumber").value.replace(/[^0-9]/g, "");
                if (phone.length === 7) {{
                    phone = "960" + phone;
                }}
                return phone;
            }}

            function sendWhatsApp() {{
                const phone = formatPhone();
                const body = encodeURIComponent(document.getElementById("letterBody").value);
                const url = phone ? `https://wa.me/${{phone}}?text=${{body}}` : `https://wa.me/?text=${{body}}`;
                window.open(url, "_blank");
            }}

            function sendSMS() {{
                const phone = document.getElementById("phoneNumber").value.trim();
                const body = encodeURIComponent(document.getElementById("letterBody").value);
                window.location.href = `sms:${{phone}}?body=${{body}}`;
            }}

            function sendViber() {{
                const body = encodeURIComponent(document.getElementById("letterBody").value);
                window.location.href = `viber://forward?text=${{body}}`;
            }}

            function sendTelegram() {{
                const body = encodeURIComponent(document.getElementById("letterBody").value);
                window.open(`https://t.me/share/url?url=&text=${{body}}`, "_blank");
            }}

            async function shareAnyApp() {{
                const text = document.getElementById("letterBody").value;
                const title = document.getElementById("emailSubject").value.trim() || "IACT-AI ލިޔުން";
                if (navigator.share) {{
                    try {{
                        await navigator.share({{ title: title, text: text }});
                    }} catch (err) {{}}
                }} else {{
                    copyLetter();
                }}
            }}
        </script>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="dv" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IACT-AI Multimodal Governance Studio</title>
        <style>
            body {{ font-family: 'Faruma', sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 14px; }}
            .container {{ max-width: 760px; margin: auto; }}
            .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 18px; margin-bottom: 16px; }}
            textarea, select, input, button {{ width: 100%; padding: 14px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #fff; font-size: 16px; margin-top: 8px; box-sizing: border-box; }}
            textarea.prompt-box {{ min-height: 240px; line-height: 1.9; resize: vertical; }}
            textarea.sender-box {{ min-height: 135px; line-height: 1.8; resize: vertical; border-color: #0284c7; }}
            button {{ background: #2563eb; border: none; font-weight: bold; cursor: pointer; margin-top: 16px; font-size: 16px; }}
            button:hover {{ opacity: 0.92; }}
            .btn-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
            .voice-box {{ background: #0f172a; border: 1px dashed #38bdf8; border-radius: 10px; padding: 12px; margin-top: 14px; }}
            .file-box {{ background: #0f172a; border: 1px dashed #4ade80; border-radius: 10px; padding: 12px; margin-top: 14px; }}
            .output-box {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 14px; margin-top: 14px; }}
            label {{ display: block; margin-top: 14px; font-weight: bold; color: #cbd5e1; }}
            .hint {{ font-size: 13px; color: #94a3b8; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2 style="text-align:center; color:#38bdf8;">IACT-AI (ދިވެހި އިންޓެލިޖެންސް)</h2>
            <div class="card">
                <form id="mainForm" method="post" action="/run" enctype="multipart/form-data">
                    <label>ސުވާލު ނުވަތަ ދިރާސާ މަޢުލޫމާތު ލިޔުއްވާ (ދިގު ލިޔުންތަކަށް ޚާއްޞަ):</label>
                    <div class="hint">މި ގޮޅީގައި ސިޓީ، މަޒުމޫނު، ނުވަތަ ދިރާސާގެ ހުރިހާ ތަފްޞީލެއް ލިޔެވޭނެއެވެ (ނުވަތަ ތިރިން އަޑުން ކިޔައިދީ / ފައިލް އަޕްލޯޑްކުރޭ).</div>
                    <textarea id="promptBox" class="prompt-box" name="prompt" rows="10" oninput="autoExpand(this, 240)" placeholder="މިތާނގައި ތަފްޞީލުކޮށް ލިޔުއްވާ...">{prompt}</textarea>

                    <!-- Voice Recording & Command Section -->
                    <div class="voice-box">
                        <strong style="color:#38bdf8;">އަޑުން ވާހަކަދެއްކުމާއި ކޮމާންޑް ދިނުން (Voice Command):</strong>
                        <div class="hint">މައިކްރޯފޯނަށް ފިތާފައި ދިވެހި ބަހުން ސިޓީގެ މަޢުލޫމާތު ނުވަތަ ކޮމާންޑް ކިޔައިދެއްވާ!</div>
                        <div class="btn-grid">
                            <button type="button" id="recordBtn" onclick="toggleVoiceRecord()" style="background:#dc2626; margin-top:8px;">އަޑު ރެކޯޑްކުރަން ފަށާ</button>
                            <button type="button" onclick="clearVoiceAudio()" style="background:#475569; margin-top:8px;">ރެކޯޑިންގ ފޮހެލާ</button>
                        </div>
                        <div id="voiceStatus" style="margin-top:8px; font-size:14px; color:#fbbf24;"></div>
                        <input type="hidden" id="audioBase64" name="audio_b64">
                        <input type="hidden" id="audioMime" name="audio_mime">
                    </div>

                    <!-- Photo / Screenshot / PDF Upload Section -->
                    <div class="file-box">
                        <strong style="color:#4ade80;">ފޮޓޯ، ސްކްރީންޝޮޓް، ނުވަތަ PDF އަޕްލޯޑްކުރުން:</strong>
                        <div class="hint">ލިޔުމެއްގެ ފޮޓޯއެއް ނުވަތަ PDF ފައިލެއް ހޮވާލުމުން އޭގައިވާ މަޢުލޫމާތު ދެނެގަންނާނެއެވެ.</div>
                        <input type="file" name="upload_file" accept="image/*,application/pdf">
                    </div>

                    <!-- Sender Information Section -->
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:16px;">
                        <label style="margin:0; color:#38bdf8;">ފޮނުވާ ފަރާތުގެ މަޢުލޫމާތު (ނަން، އެޑްރެސް، އައިޑީ/ޕާސްޕޯޓް، ފޯނު، އީމެއިލް/URL):</label>
                        <button type="button" onclick="clearSenderInfo()" style="width:auto; padding:4px 10px; margin:0; background:#475569; font-size:12px;">ފޮހެލާ</button>
                    </div>
                    <div class="hint">އެއްފަހަރު ޖެހުމުން ތިބާގެ ފޯނުގައި ސޭވްވެފައި ހުންނާނެއެވެ (ސިޓީގައި އޮޓޮމެޓިކުން ހިމަނައިދޭނެއެވެ).</div>
                    <textarea id="senderInfoBox" class="sender-box" name="sender_info" rows="5" oninput="saveSenderInfo()" placeholder="ނަން: &#10;އެޑްރެސް: &#10;އައިޑީ ކާޑު / ޕާސްޕޯޓް ނަންބަރު: &#10;ފޯނު ނަންބަރު: &#10;އީމެއިލް / ޔޫއާރުއެލް: ">{sender_info}</textarea>

                    <label>ހެކީގެ ފެންވަރު (Evidence Level):</label>
                    <select name="evidence">
                        <option value="E0" {"selected" if evidence=="E0" else ""}>E0 = ޚިޔާލީ ހުށަހެޅުން (Conceptual)</option>
                        <option value="E1" {"selected" if evidence=="E1" else ""}>E1 = އަމިއްލަ ހުށަހެޅުން / ހެކި މަދު</option>
                        <option value="E2" {"selected" if evidence=="E2" else ""}>E2 = ޢިލްމީ / އިތުބާރުހުރި ހެކި</option>
                        <option value="E3" {"selected" if evidence=="E3" else ""}>E3 = ކަށަވަރުކުރެވިފައިވާ ފުރިހަމަ ހެކި</option>
                    </select>

                    <label>ހުއްދައިގެ ފެންވަރު (Permission Level):</label>
                    <select name="permission">
                        <option value="L0" {"selected" if permission=="L0" else ""}>L0 = READ (ކިޔުން)</option>
                        <option value="L1" {"selected" if permission=="L1" else ""}>L1 = CREATE (އުފެއްދުން)</option>
                        <option value="L2" {"selected" if permission=="L2" else ""}>L2 = PROPOSE (ހުށަހެޅުން)</option>
                        <option value="L3" {"selected" if permission=="L3" else ""}>L3 = VERIFY (ކަށަވަރުކުރުން)</option>
                    </select>

                    <button type="submit" id="submitBtn">IACT-AI ހިންގާލާ</button>
                </form>
            </div>
            {result_block}
        </div>

        <script>
            let mediaRecorder = null;
            let audioChunks = [];
            let isRecording = false;

            async function toggleVoiceRecord() {{
                const btn = document.getElementById("recordBtn");
                const status = document.getElementById("voiceStatus");

                if (!isRecording) {{
                    try {{
                        const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];

                        mediaRecorder.ondataavailable = (event) => {{
                            if (event.data.size > 0) audioChunks.push(event.data);
                        }};

                        mediaRecorder.onstop = () => {{
                            const mimeType = mediaRecorder.mimeType || "audio/webm";
                            const audioBlob = new Blob(audioChunks, {{ type: mimeType }});
                            const reader = new FileReader();
                            reader.onloadend = () => {{
                                document.getElementById("audioBase64").value = reader.result;
                                document.getElementById("audioMime").value = mimeType;
                                status.innerText = "އަޑު ރެކޯޑްކުރެވިއްޖެއެވެ! ދެން 'IACT-AI ހިންގާލާ' އަށް ފިތާލާށެވެ.";
                            }};
                            reader.readAsDataURL(audioBlob);
                            stream.getTracks().forEach(track => track.stop());
                        }};

                        mediaRecorder.start();
                        isRecording = true;
                        btn.innerText = "ރެކޯޑިންގ ހުއްޓާލާ (Stop)";
                        btn.style.background = "#eab308";
                        btn.style.color = "#000";
                        status.innerText = "އަޑު ރެކޯޑްވަނީ... ވާހަކަދައްކަވާ!";
                    }} catch (err) {{
                        alert("މައިކްރޯފޯން ހުއްދަ ދެއްވާށެވެ: " + err.message);
                    }}
                }} else {{
                    mediaRecorder.stop();
                    isRecording = false;
                    btn.innerText = "އަޑު ރެކޯޑްކުރަން ފަށާ";
                    btn.style.background = "#dc2626";
                    btn.style.color = "#fff";
                }}
            }}

            function clearVoiceAudio() {{
                document.getElementById("audioBase64").value = "";
                document.getElementById("audioMime").value = "";
                document.getElementById("voiceStatus").innerText = "އަޑުގެ ރެކޯޑިންގ ފޮހެލެވިއްޖެއެވެ.";
            }}

            function autoExpand(field, minHeight) {{
                field.style.height = 'inherit';
                field.style.height = Math.max(minHeight, field.scrollHeight) + 'px';
            }}

            function saveSenderInfo() {{
                const val = document.getElementById("senderInfoBox").value;
                localStorage.setItem("iact_sender_info", val);
            }}

            function clearSenderInfo() {{
                document.getElementById("senderInfoBox").value = "";
                localStorage.removeItem("iact_sender_info");
            }}

            window.addEventListener('load', () => {{
                const promptBox = document.getElementById('promptBox');
                if (promptBox && promptBox.value) autoExpand(promptBox, 240);

                const senderBox = document.getElementById('senderInfoBox');
                const saved = localStorage.getItem("iact_sender_info");
                if (senderBox && !senderBox.value && saved) {{
                    senderBox.value = saved;
                }}
            }});
        </script>
    </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
def home():
    return render_page()


@app.post("/run", response_class=HTMLResponse)
async def run_ai(
    prompt: str = Form(""),
    sender_info: str = Form(""),
    evidence: str = Form("E0"),
    permission: str = Form("L0"),
    audio_b64: str = Form(""),
    audio_mime: str = Form("audio/webm"),
    upload_file: UploadFile | None = File(None)
):
    file_bytes = None
    file_mime = ""
    if upload_file and upload_file.filename:
        content = await upload_file.read()
        if content:
            file_bytes = content
            file_mime = upload_file.content_type or "application/octet-stream"

    if not prompt.strip() and not file_bytes and not audio_b64:
        return render_page(
            prompt=prompt,
            sender_info=sender_info,
            evidence=evidence,
            permission=permission,
            status="REVIEW",
            reason="INPUT REQUIRED",
            detail="ކުރިއަށް ދިއުމަށް ސުވާލެއް ލިޔުއްވާ، ނުވަތަ އަޑު ރެކޯޑްކުރައްވާ، ނުވަތަ ފޮޓޯ/PDF އެއް އަޕްލޯޑްކުރައްވާށެވެ.",
            ai_output="",
            engine_used="None"
        )

    ev_score = EVIDENCE_MAP.get(evidence, 0)
    cl_score = PERMISSION_CLAIM_MAP.get(permission, 0)

    if cl_score <= ev_score:
        status = "PASS"
        detail = f"ޙާލަތު: ހެކީގެ ފެންވަރު ({evidence}) އަދި ހުއްދަ ({permission}) ޝަރުޠު ހަމަވެއެވެ."
    else:
        status = "REVIEW"
        detail = f"ޙާލަތު: ހެކީގެ ފެންވަރު ({evidence}) ދަށްވުމުން އިތުރު ރިވިއު ބޭނުންވެއެވެ."

    reason = "CLAIM STRENGTH <= EVIDENCE STRENGTH"

    ok, reply = ask_gemini_multimodal(
        prompt=prompt,
        sender_info=sender_info,
        file_bytes=file_bytes,
        file_mime=file_mime,
        audio_b64=audio_b64,
        audio_mime=audio_mime
    )
    engine_used = "Gemini 2.5 Flash"

    if not ok:
        if not file_bytes and not audio_b64:
            ok_groq, reply_groq = ask_groq_text(prompt, sender_info)
            if ok_groq:
                reply = reply_groq
                engine_used = "Groq Llama 3.3 70B"
            else:
                reply = f"{reply}\n\n---\n{reply_groq}"
                engine_used = "Error"
        else:
            reply = f"{reply}\n\n(ނޯޓު: ފޮޓޯ، PDF އަދި އަޑުގެ ފައިލްތައް ދެނެގަތުމަށް Gemini 2.5 Flash ގެ ކޯޓާ ހުސްވެފައިވާނަމަ، ކޯޓާ އާވުމުން އަލުން މަސައްކަތްކުރާނެއެވެ)."
            engine_used = "Gemini Quota Limit"

    return render_page(prompt, sender_info, evidence, permission, status, reason, detail, reply, engine_used)
